"""
VEXORA Adaptive Planner — V2

The Planner is the brain. It NEVER answers the user.
It ONLY generates execution plans as structured JSON.

Uses Groq (Llama 3.3 70B) for sub-second JSON generation.
Replaces the static keyword-based capability_analyzer for complex tasks.
Falls back to fast-path rules for Level 0 (greetings/small talk).

Flow:
    User Request → Planner LLM → JSON Plan → Plan Validator → Execution
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

from .agent_registry import AGENTS, get_agent
from .model_registry import MODELS


@dataclass
class ExecutionPlan:
    """Structured execution plan from the Planner."""
    intent: str
    complexity: int               # 0-4
    confidence: float             # 0.0-1.0
    reasoning: str
    capabilities: list[str]
    agents: list[str]             # Agent names from registry
    models: dict[str, str]        # agent_name → model_id
    tools: list[str]
    parallel_groups: list[list[str]]  # Groups of agents that can run in parallel
    verification: bool
    humanizer: bool
    estimated_latency_ms: int
    estimated_cost: float
    planner_latency_ms: int
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
    # Very short prompts that match greeting patterns
    if len(lower.split()) <= 8:
        for pattern in GREETING_PATTERNS:
            if pattern in lower:
                return True
    return False


def _fast_path_plan(prompt: str) -> ExecutionPlan:
    """Generate a Level 0 plan without any LLM call."""
    is_identity = any(p in prompt.lower() for p in IDENTITY_PATTERNS)

    return ExecutionPlan(
        intent="Identity" if is_identity else "Conversation",
        complexity=0,
        confidence=0.99,
        reasoning="Simple greeting/identity — fast path, no orchestration needed",
        capabilities=["conversation"],
        agents=["conversation"],
        models={"conversation": "llama-3.3-70b-versatile"},
        tools=[],
        parallel_groups=[["conversation"]],
        verification=False,
        humanizer=False,
        estimated_latency_ms=500,
        estimated_cost=0.0001,
        planner_latency_ms=0,
        planning_path="fast_path",
    )


# =============================================================================
# LLM-Based Planning (Level 1-4)
# =============================================================================

PLANNER_SYSTEM_PROMPT = """You are the VEXORA Planning Intelligence Engine.
You NEVER answer the user's question. You ONLY generate execution plans as JSON.

Your job: Analyze the user's request and decide:
1. What capabilities are needed
2. Which specialist agents should handle it
3. What models to use
4. Which agents can run in parallel
5. Whether verification is needed
6. Whether humanization is needed

Available agents (use ONLY these names):
{agents_list}

Available model IDs (use ONLY these):
{models_list}

Complexity levels:
0 = Greeting/small talk (already handled, you won't see these)
1 = Simple explanation/definition (1 agent)
2 = Coding task (2-4 agents)
3 = Research task (2-3 agents)
4 = Enterprise/complex system (5+ agents)

Rules:
- Select the MINIMUM effective team. Never use unnecessary agents.
- For Level 1: Use only "reasoning" or "coder" agent.
- For Level 2: Use domain agents + "reviewer". Add "verifier" only if code is complex.
- For Level 3: Use "researcher" + "reasoning" + "reviewer".
- For Level 4: Use "architect" + domain agents + "reviewer" + "verifier".
- Never include "humanizer" as an agent — it runs separately.
- Agents in the same parallel_group run concurrently.
- Agents that depend on others' output must be in a LATER group.
- "reviewer" always runs AFTER implementation agents.
- "verifier" always runs AFTER "reviewer".
- Choose models based on task needs: reasoning models for architecture, coding models for implementation, fast models for simple tasks.
- For research tasks, recommend the "researcher" agent.

You MUST return ONLY valid JSON matching this exact schema:
{{
  "intent": "string",
  "complexity": 0,
  "confidence": 0.0,
  "reasoning": "why this plan",
  "capabilities": ["list"],
  "agents": ["agent_names"],
  "models": {{"agent_name": "model_id"}},
  "tools": ["tool_names"],
  "parallel_groups": [["group1_agents"], ["group2_agents"]],
  "verification": true,
  "humanizer": true,
  "estimated_latency_ms": 5000,
  "estimated_cost": 0.01
}}

Return ONLY the JSON object. No markdown, no explanation, no code fences."""


async def generate_plan(prompt: str) -> ExecutionPlan:
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
        print(f"[PLANNER ERROR] All LLM fallbacks failed: {e}. Degrading to deterministic capability analyzer.")
        # TERTIARY FALLBACK: Deterministic keyword analyzer
        from .capability_analyzer import analyze
        analysis = analyze(prompt)
        plan_json = {
            "intent": analysis.intent,
            "complexity": 2 if analysis.complexity in ["Medium", "Low"] else 3,
            "confidence": 0.4,
            "reasoning": "Deterministic fallback used due to LLM planning outage.",
            "capabilities": analysis.capabilities,
            "agents": ["coder", "researcher"] if "research" in analysis.capabilities else ["coder"],
            "models": {"coder": "gemini-flash"},
            "tools": [],
            "parallel_groups": [["coder"]],
            "verification": analysis.requires_verification,
            "humanizer": analysis.requires_humanization,
            "estimated_latency_ms": 3000,
            "estimated_cost": 0.0
        }
        planning_path = "deterministic"
        
    planner_latency = int((time.monotonic() - start) * 1000)

    # Parse and validate
    plan = _parse_plan(plan_json, planner_latency)
    plan.planning_path = planning_path
    plan = _validate_plan(plan)

    return plan


async def _call_planner_llm(prompt: str) -> tuple[dict, str]:
    """Call Groq API to generate the execution plan, with OpenRouter and Gemini fallbacks."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not configured for planner")

    # Build context about available agents and models
    agents_list = "\n".join(
        f"  - {name}: {a.display_name} (capabilities: {', '.join(a.capabilities)})"
        for name, a in AGENTS.items()
        if "orchestration" not in a.tags and "internal" not in a.tags
    )
    models_list = "\n".join(
        f"  - {mid}: {m.name} (provider: {m.provider}, capabilities: {', '.join(m.capabilities)})"
        for mid, m in MODELS.items()
        if m.is_available
    )

    from .executor import VEXORA_IDENTITY_PREFIX
    system = VEXORA_IDENTITY_PREFIX + PLANNER_SYSTEM_PROMPT.format(
        agents_list=agents_list,
        models_list=models_list,
    )
    
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
                        {"role": "user", "content": f"Generate an execution plan for this user request:\n\n{prompt}"},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                }
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
    except Exception as e:
        # Check if it's a rate limit or timeout on primary
        planning_path = "secondary"
        print(f"[PLANNER WARN] Groq failed ({e}). Falling back to OpenRouter Gemini.")
        
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
                            {"role": "user", "content": f"Generate an execution plan for this user request:\n\n{prompt}"}
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
                            "parts": [{"text": f"Generate an execution plan for this user request:\n\n{prompt}"}]
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
        # Try to extract JSON from markdown code blocks
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", content, re.DOTALL)
        if match:
            return json.loads(match.group(1)), planning_path
        raise ValueError(f"Planner returned invalid JSON: {content[:200]}")


def _parse_plan(raw: dict, planner_latency_ms: int) -> ExecutionPlan:
    """Parse raw JSON into ExecutionPlan dataclass."""
    return ExecutionPlan(
        intent=raw.get("intent", "Unknown"),
        complexity=int(raw.get("complexity", 2)),
        confidence=float(raw.get("confidence", 0.7)),
        reasoning=raw.get("reasoning", ""),
        capabilities=raw.get("capabilities", []),
        agents=raw.get("agents", []),
        models=raw.get("models", {}),
        tools=raw.get("tools", []),
        parallel_groups=raw.get("parallel_groups", []),
        verification=raw.get("verification", True),
        humanizer=raw.get("humanizer", False),
        estimated_latency_ms=raw.get("estimated_latency_ms", 5000),
        estimated_cost=raw.get("estimated_cost", 0.01),
        planner_latency_ms=planner_latency_ms,
    )


def _validate_plan(plan: ExecutionPlan) -> ExecutionPlan:
    """
    Validate the plan against registries.
    Auto-repair hallucinated agents/models.
    """
    # Validate agents exist
    valid_agents = []
    for agent_name in plan.agents:
        if get_agent(agent_name):
            valid_agents.append(agent_name)
        else:
            print(f"[PLANNER WARN] Agent '{agent_name}' not in registry — skipped")
    plan.agents = valid_agents if valid_agents else ["coder"]

    # Validate models exist
    valid_models = {}
    for agent_name, model_id in plan.models.items():
        if agent_name in plan.agents:
            if model_id in MODELS:
                valid_models[agent_name] = model_id
            else:
                # Fallback to Groq Llama
                valid_models[agent_name] = "llama-3.3-70b-versatile"
                print(f"[PLANNER WARN] Model '{model_id}' not in registry — using fallback")
    # Ensure every agent has a model
    for agent_name in plan.agents:
        if agent_name not in valid_models:
            valid_models[agent_name] = "llama-3.3-70b-versatile"
    plan.models = valid_models

    # Validate parallel groups — only include valid agents
    valid_groups = []
    assigned = set()
    for group in plan.parallel_groups:
        valid_group = [a for a in group if a in plan.agents and a not in assigned]
        if valid_group:
            valid_groups.append(valid_group)
            assigned.update(valid_group)
    # Add any unassigned agents as a final sequential group
    unassigned = [a for a in plan.agents if a not in assigned]
    if unassigned:
        valid_groups.append(unassigned)
    plan.parallel_groups = valid_groups if valid_groups else [plan.agents]

    # Clamp complexity
    plan.complexity = max(0, min(4, plan.complexity))

    return plan
