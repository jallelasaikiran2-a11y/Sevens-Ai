"""
VEXORA Adaptive Planner — V3

The Planner is a pure intent analyzer. It is completely model-agnostic
and agent-agnostic. It NEVER references specific agents, models, or tools.

V3 changes:
- Outputs only: Intent, Complexity, Capabilities, Constraints,
  Required Outputs, Missing Information, Confidence
- Adds a Clarification Loop: if critical info is missing, returns
  a clarification request instead of guessing
- Strips all agent/model awareness from the system prompt
- The Capability Resolver (downstream) handles agent/model mapping

Flow:
    User Request → Planner LLM → Plan Output → Plan Validator
                                                     ↓
                                           Capability Resolver
"""

from __future__ import annotations
import json
import os
import re
import time
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()


@dataclass
class PlanOutput:
    """
    V3 Planner output — pure intent analysis.
    Contains NO agent names, model names, or tool names.
    """
    intent: str
    complexity: int                   # 0-4
    confidence: float                 # 0.0-1.0
    reasoning: str
    capabilities: list[str]           # e.g. ["architecture", "backend", "security"]
    constraints: list[str]            # e.g. ["must use PostgreSQL", "REST only"]
    required_outputs: list[str]       # e.g. ["code", "schema", "documentation"]
    missing_information: list[str]    # e.g. ["database preference not specified"]
    needs_clarification: bool         # If True, orchestrator should ask user
    clarification_questions: list[str]  # Questions to ask the user
    planner_latency_ms: int = 0
    planning_path: str = "primary"


# =============================================================================
# Fast-Path Detection (Level 0 — No LLM call needed)
# =============================================================================

GREETING_PATTERNS = [
    "hello", "hi", "hey", "how are you", "what's up", "good morning",
    "good evening", "good afternoon", "thanks", "thank you", "bye",
    "goodbye", "help", "who are you", "what are you", "what can you do",
]

IDENTITY_PATTERNS = [
    "who are you", "what are you", "your name", "what is vexora",
    "tell me about yourself", "introduce yourself",
]


def _is_fast_path(prompt: str) -> bool:
    """Check if prompt is Level 0 (greeting/small talk/identity)."""
    lower = prompt.lower().strip()
    if len(lower.split()) <= 8:
        for pattern in GREETING_PATTERNS:
            if pattern in lower:
                return True
    return False


def _fast_path_plan(prompt: str) -> PlanOutput:
    """Generate a Level 0 plan without any LLM call."""
    is_identity = any(p in prompt.lower() for p in IDENTITY_PATTERNS)

    return PlanOutput(
        intent="Identity" if is_identity else "Conversation",
        complexity=0,
        confidence=0.99,
        reasoning="Simple greeting/identity — fast path, no orchestration needed",
        capabilities=["conversation"],
        constraints=[],
        required_outputs=["text"],
        missing_information=[],
        needs_clarification=False,
        clarification_questions=[],
        planner_latency_ms=0,
        planning_path="fast_path",
    )


# =============================================================================
# LLM-Based Planning (Level 1-4)
# =============================================================================

PLANNER_SYSTEM_PROMPT = """You are the VEXORA Planning Intelligence Engine.
You NEVER answer the user's question. You ONLY analyze intent and output a plan as JSON.

Your job: Analyze the user's request and determine:
1. What is the user's intent?
2. How complex is this task? (0=greeting, 1=simple, 2=moderate, 3=complex, 4=enterprise)
3. What capabilities are needed? (from: architecture, backend, frontend, database, security, testing, devops, documentation, ml, mobile, performance, refactoring, research, review, reasoning, conversation)
4. What constraints does the user specify? (technology preferences, requirements)
5. What outputs are expected? (code, schema, documentation, analysis, comparison)
6. Is any critical information missing that would change the plan?
7. How confident are you in this analysis?

IMPORTANT RULES:
- Do NOT reference specific agent names, model names, or provider names.
- Do NOT decide which agents or models to use — that is handled downstream.
- Focus ONLY on understanding WHAT the user needs, not HOW to execute it.
- If the request is ambiguous and could go in very different directions,
  set needs_clarification=true and provide specific questions.
- Only set needs_clarification=true for genuinely ambiguous requests,
  NOT for simple or moderately clear tasks.

You MUST return ONLY valid JSON matching this schema:
{{
  "intent": "string describing what the user wants",
  "complexity": 0,
  "confidence": 0.0,
  "reasoning": "why this analysis",
  "capabilities": ["list of required capabilities"],
  "constraints": ["list of user-specified constraints"],
  "required_outputs": ["code", "schema", "documentation", etc.],
  "missing_information": ["list of missing but important details"],
  "needs_clarification": false,
  "clarification_questions": []
}}

Return ONLY the JSON object. No markdown, no explanation, no code fences."""


async def generate_plan(prompt: str) -> PlanOutput:
    """
    Generate an execution plan for the given prompt.
    Uses fast-path for Level 0, LLM planning for Level 1-4.
    """
    # Fast path for greetings
    if _is_fast_path(prompt):
        return _fast_path_plan(prompt)

    # LLM-based planning via Groq with fallbacks
    start = time.monotonic()

    try:
        plan_json, planning_path = await _call_planner_llm(prompt)
    except Exception as e:
        print(f"[PLANNER ERROR] All LLM fallbacks failed: {e}. Degrading to deterministic analyzer.")
        # DETERMINISTIC FALLBACK
        from .capability_analyzer import analyze
        analysis = analyze(prompt)
        plan_json = {
            "intent": analysis.intent,
            "complexity": 2 if analysis.complexity in ["Medium", "Low"] else 3,
            "confidence": 0.4,
            "reasoning": "Deterministic fallback used due to LLM planning outage.",
            "capabilities": analysis.capabilities,
            "constraints": [],
            "required_outputs": ["code"] if "coding" in analysis.capabilities else ["text"],
            "missing_information": ["LLM planner unavailable — using keyword analysis"],
            "needs_clarification": False,
            "clarification_questions": [],
        }
        planning_path = "deterministic"

    planner_latency = int((time.monotonic() - start) * 1000)

    # Parse and validate
    plan = _parse_plan(plan_json, planner_latency)
    plan.planning_path = planning_path
    plan = _validate_plan(plan)

    return plan


async def _call_planner_llm(prompt: str) -> tuple[dict, str]:
    """Call Groq API to generate the plan, with OpenRouter and Gemini fallbacks."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not configured for planner")

    from .executor import VEXORA_IDENTITY_PREFIX
    system = VEXORA_IDENTITY_PREFIX + PLANNER_SYSTEM_PROMPT

    planning_path = "primary"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": f"Analyze this user request and generate a plan:\n\n{prompt}"},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
    except Exception as e:
        planning_path = "secondary"
        print(f"[PLANNER WARN] Groq failed ({e}). Falling back to OpenRouter.")

        try:
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if not openrouter_key:
                raise ValueError("OPENROUTER_API_KEY not set.")
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {openrouter_key}"},
                    json={
                        "model": "google/gemini-2.5-pro",
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": f"Analyze this user request and generate a plan:\n\n{prompt}"}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1000,
                        "response_format": {"type": "json_object"},
                    }
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
        except Exception as e2:
            planning_path = "tertiary"
            print(f"[PLANNER WARN] OpenRouter fallback failed ({e2}). Falling back to Native Gemini.")
            gemini_key = os.getenv("GEMINI_API_KEY")
            if not gemini_key:
                raise ValueError("GEMINI_API_KEY not set.")
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={gemini_key}",
                    json={
                        "system_instruction": {
                            "parts": [{"text": system}]
                        },
                        "contents": [{
                            "parts": [{"text": f"Analyze this user request and generate a plan:\n\n{prompt}"}]
                        }],
                        "generationConfig": {
                            "temperature": 0.1,
                            "response_mime_type": "application/json",
                        }
                    }
                )
                response.raise_for_status()
                data = response.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]

    # Parse JSON from response
    try:
        return json.loads(content), planning_path
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", content, re.DOTALL)
        if match:
            return json.loads(match.group(1)), planning_path
        raise ValueError(f"Planner returned invalid JSON: {content[:200]}")


def _parse_plan(raw: dict, planner_latency_ms: int) -> PlanOutput:
    """Parse raw JSON into PlanOutput dataclass."""
    return PlanOutput(
        intent=raw.get("intent", "Unknown"),
        complexity=int(raw.get("complexity", 2)),
        confidence=float(raw.get("confidence", 0.7)),
        reasoning=raw.get("reasoning", ""),
        capabilities=raw.get("capabilities", []),
        constraints=raw.get("constraints", []),
        required_outputs=raw.get("required_outputs", []),
        missing_information=raw.get("missing_information", []),
        needs_clarification=raw.get("needs_clarification", False),
        clarification_questions=raw.get("clarification_questions", []),
        planner_latency_ms=planner_latency_ms,
    )


def _validate_plan(plan: PlanOutput) -> PlanOutput:
    """
    Validate the plan output.
    Clamp complexity, ensure at least one capability, etc.
    """
    # Clamp complexity
    plan.complexity = max(0, min(4, plan.complexity))

    # Ensure at least one capability
    if not plan.capabilities:
        plan.capabilities = ["conversation"]

    # Validate capability names against known set
    known_capabilities = {
        "architecture", "backend", "frontend", "database", "security",
        "testing", "devops", "documentation", "ml", "mobile",
        "performance", "refactoring", "research", "review",
        "reasoning", "conversation",
    }
    valid_caps = [c for c in plan.capabilities if c in known_capabilities]
    if not valid_caps:
        valid_caps = ["reasoning"]
    plan.capabilities = valid_caps

    return plan
