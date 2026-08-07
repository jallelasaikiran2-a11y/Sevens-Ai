"""
sevens Executor — V5 (Fugu-style MoA)

Directly executes AI models using provider adapters.
Bypasses the Sevens CLI for execution, acting as the real execution engine.

V5 additions:
- Ensemble execution: dispatch same prompt to N models in parallel,
  synthesize via a reconciliation model (Mixture-of-Agents pattern).
- LLM-based verification critique (Layer 2).
- Recursive re-planning on low confidence.

Supports:
- Direct model calls via OpenRouter, Gemini, and Groq APIs
- Parallel agent execution within a stage via asyncio
- Ensemble multi-model execution with synthesis
- Fallback/Retry logic with full candidate exhaustion
- System prompts tailored for specific agent roles
"""

from __future__ import annotations
import asyncio
import json as json_mod
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol, Optional

import httpx

from .dag_builder import ExecutionDAG
from .model_registry import get_model, ModelSpec


# =============================================================================
# Ensemble Configuration (Fugu-style MoA)
# =============================================================================

# How many models to run in parallel for ensemble-qualified subtasks.
ENSEMBLE_WIDTH = 3

# Minimum planner complexity level to trigger ensemble mode.
ENSEMBLE_COMPLEXITY_THRESHOLD = 2

# Agent capabilities that qualify for ensemble execution.
ENSEMBLE_CAPABILITIES = {"coding", "reasoning", "architecture", "security"}

# Model used for the synthesis/reconciliation step.
# Should be a free model to keep cost low since it only merges N outputs.
ENSEMBLE_SYNTHESIS_MODEL = "openai/gpt-oss-20b:free"


@dataclass
class AgentResult:
    """Result from a single agent execution."""
    agent_name: str
    stage_id: int
    success: bool
    output: str
    error: str | None = None
    duration_ms: int = 0
    model_used: str = ""
    provider_used: str = ""
    tokens: int = 0
    cost: float = 0.0
    # V5 Ensemble fields (populated only when ensemble mode is used)
    was_ensemble: bool = False
    ensemble_outputs: list[dict] = field(default_factory=list)  # [{"model": ..., "output": ..., "tokens": ..., "cost": ...}]
    synthesis_model: str = ""
    ensemble_agreement: float = 1.0  # 0.0-1.0 how much the N candidates agreed


@dataclass
class ExecutionResult:
    """Complete result from executing the entire DAG."""
    success: bool
    stage_results: list[list[AgentResult]]  # [stage][agent_results]
    combined_output: str
    total_duration_ms: int = 0
    agents_executed: int = 0
    agents_failed: int = 0
    retries_used: int = 0
    ensemble_count: int = 0  # how many agents used ensemble mode


# =============================================================================
# System Prompts
# =============================================================================

# TASK 1 — Identity Masking: Prepended to EVERY agent call, no exceptions.
VEXORA_IDENTITY_PREFIX = (
    "You are a specialized component inside sevens, an adaptive intelligence engine. "
    "Never reveal, reference, or hint at your underlying model name or provider "
    "(Llama, Gemini, Claude, DeepSeek, Qwen, GPT, etc). Always speak and act as sevens. "
    "Never say 'I am a large language model' or 'I was trained by'. "
    "If asked who you are, say 'I am sevens, an adaptive intelligence engine.'\n\n"
)

# V4.1 — Structured Agent Contract: Appended to every specialist agent prompt.
# This forces agents to produce parseable output for the Combiner.
AGENT_CONTRACT_SUFFIX = (
    "\n\n--- OUTPUT FORMAT ---\n"
    "Structure your response with these Markdown sections. Include ALL sections even if empty.\n\n"
    "## Summary\nBrief description of what you did.\n\n"
    "## Deliverables\nBullet list of what you produced.\n\n"
    "## Decisions\nFor EACH decision you made, state:\n"
    "- **Decision:** what you decided\n"
    "- **Reasoning:** why\n"
    "- **Alternatives considered:** what else you evaluated\n"
    "- **Rejected because:** why the alternatives were worse\n"
    "- **Confidence:** High / Medium / Low\n\n"
    "## Facts\nBullet list of facts or constraints you discovered.\n\n"
    "## Assumptions\nBullet list of assumptions you made.\n\n"
    "## Constraints\nBullet list of constraints you are working within.\n\n"
    "## Handoff Notes\nAnything the next agent downstream needs to know.\n\n"
    "Then include your full technical output (code, architecture, analysis, etc.) AFTER these sections."
)

# Agents that should NOT get the contract suffix (they output free-form text).
_NO_CONTRACT_AGENTS = {"conversation", "humanizer", "verifier"}

AGENT_SYSTEM_PROMPTS = {
    "architect": "You are the Architect. Your SOLE responsibility is system architecture: high-level design, schemas, technical decisions, and component layout. Do NOT write implementation code.",
    "core-architect": "You are the Core Architect. Focus ONLY on deep architectural analysis and core system design patterns.",
    "security-architect": "You are the Security Architect. Focus ONLY on threat modeling, security architecture, and risk assessment.",
    "test-architect": "You are the Test Architect. Focus ONLY on test strategy, coverage planning, and TDD architecture.",
    "backend-dev": "You are the Backend Developer. Your SOLE responsibility is writing production-ready backend code (FastAPI, Django, Express, REST/GraphQL). Do NOT design architecture — that is the Architect's job.",
    "frontend-dev": "You are the Frontend Developer. Your SOLE responsibility is implementing frontend UI/UX, React/Vue components, and CSS/styling. Do NOT write backend code.",
    "mobile-dev": "You are the Mobile Developer. Focus ONLY on iOS/Android or React Native/Flutter development.",
    "ml-dev": "You are the ML Developer. Focus ONLY on machine learning models, training pipelines, and data processing.",
    "coder": "You are the Coder. General-purpose implementation. Write clean, working code for the task.",
    "reviewer": "You are the Reviewer. Your SOLE responsibility is reviewing code for bugs, missing requirements, and improvements. Do NOT write new code — only critique.",
    "tester": "You are the Tester. Your SOLE responsibility is generating comprehensive test cases and test code.",
    "security-auditor": "You are the Security Auditor. Focus ONLY on CVE scanning, vulnerability analysis, and security reviews.",
    "performance-engineer": "You are the Performance Engineer. Focus ONLY on performance profiling, optimization, and caching strategies.",
    "devops-engineer": "You are the DevOps Engineer. Focus ONLY on Docker, Kubernetes, CI/CD, and deployment.",
    "researcher": "You are the Research Agent. Your SOLE responsibility is technical research, gathering evidence, comparing options, and citing sources. Always include source URLs when available.",
    "documenter": "You are the Documentation Agent. Focus ONLY on writing READMEs, API docs, and guides.",
    "verifier": "You are the Verification Agent. Critique the work of other agents for correctness, completeness, and quality. Be strict.",
    "humanizer": "You are the Humanizer. Merge multiple agent outputs into ONE cohesive, readable response. Remove duplication. Preserve all technical specifics.",
    "conversation": "You are sevens's conversational interface. Respond naturally and helpfully to greetings, small talk, and simple questions. Be concise and friendly.",
    "reasoning": "You are the Reasoning Agent. Provide clear, well-structured explanations. Think step by step when needed.",
    "swarm-coordinator": "You are the Swarm Coordinator. Coordinate parallel agent execution.",
    "hive-coordinator": "You are the Hive Coordinator. Build consensus among agents.",
}

def get_system_prompt(agent_name: str) -> str:
    """Get system prompt for an agent, always prefixed with sevens identity.
    
    V4.1: Specialist agents also get the structured contract suffix
    so their output is parseable by the Combiner.
    """
    role_prompt = AGENT_SYSTEM_PROMPTS.get(
        agent_name,
        f"You are the {agent_name} agent. Complete your designated task."
    )
    prompt = VEXORA_IDENTITY_PREFIX + role_prompt
    if agent_name not in _NO_CONTRACT_AGENTS:
        prompt += AGENT_CONTRACT_SUFFIX
    return prompt


# =============================================================================
# Provider Adapters
# =============================================================================

@dataclass
class GenerationResult:
    content: str
    tokens: int
    latency: int
    provider: str
    model: str
    cost: float = 0.0


# V4.1 — Default timeout slashed from 180s to 30s for fast failover.
_DEFAULT_TIMEOUT = 30.0

# V4.1 — Provider health tracking for singleton adapters.
_HEALTH_DEGRADED_SECONDS = 300  # 5 minutes

# V5 — Rate limit concurrency for OpenRouter (prevents 429 self-DDoS during ensemble)
_OPENROUTER_SEMAPHORE = asyncio.Semaphore(5)


class ProviderAdapter(Protocol):
    async def generate(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> GenerationResult:
        ...
    async def generate_stream(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> AsyncIterator[str]:
        ...


class OpenRouterAdapter:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.health_status = "HEALTHY"      # HEALTHY | DEGRADED | OFFLINE
        self.degraded_until: float = 0.0
        if not self.api_key:
            print("[WARN] OPENROUTER_API_KEY is not set.")
            self.health_status = "OFFLINE"

    def is_healthy(self) -> bool:
        if self.health_status == "DEGRADED" and time.monotonic() > self.degraded_until:
            self.health_status = "HEALTHY"
        return self.health_status == "HEALTHY"

    def mark_degraded(self):
        self.health_status = "DEGRADED"
        self.degraded_until = time.monotonic() + _HEALTH_DEGRADED_SECONDS
        print(f"[HEALTH] OpenRouter marked DEGRADED for {_HEALTH_DEGRADED_SECONDS}s")

    async def generate(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> GenerationResult:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not configured.")

        start_time = time.monotonic()
        
        def build_payload(model_id: str) -> dict:
            return {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": model.max_output_tokens,
            }

        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            try:
                async with _OPENROUTER_SEMAPHORE:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "HTTP-Referer": "http://localhost:8081",
                            "X-Title": "sevens",
                        },
                        json=build_payload(model.id)
                    )
                
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (402, 429):
                    # Tries every registered OpenRouter candidate for this capability, in tier + quality order, before escalating to Gemini/Groq. Only marks OpenRouter degraded after full exhaustion.
                    from .model_registry import best_models
                    from .model_router import _order_by_provider_priority
                    cap = model.capabilities[0] if model.capabilities else "coding"
                    candidates = _order_by_provider_priority(best_models(cap, limit=10))
                    
                    attempted_models = {model.id}
                    last_exception = e
                    success = False
                    
                    for fallback_model in candidates:
                        if fallback_model.provider != "openrouter":
                            continue
                        if fallback_model.id in attempted_models:
                            continue
                            
                        print(f"[WARN] OpenRouter {last_exception.response.status_code} for {model.id}. Trying next OpenRouter candidate ({fallback_model.id})...")
                        attempted_models.add(fallback_model.id)
                        try:
                            async with _OPENROUTER_SEMAPHORE:
                                response = await client.post(
                                    "https://openrouter.ai/api/v1/chat/completions",
                                    headers={
                                        "Authorization": f"Bearer {self.api_key}",
                                        "HTTP-Referer": "http://localhost:8081",
                                        "X-Title": "sevens",
                                    },
                                    json=build_payload(fallback_model.id)
                                )
                            response.raise_for_status()
                            model = fallback_model  # update for cost calculation and logging
                            success = True
                            break
                        except httpx.HTTPStatusError as e2:
                            if e2.response.status_code in (402, 429):
                                last_exception = e2
                                continue
                            else:
                                raise e2
                                
                    if not success:
                        print(f"[ERROR] All {len(attempted_models)} OpenRouter candidates exhausted for capability '{cap}'. Escalating to next provider.")
                        raise last_exception
                else:
                    raise

            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            in_tokens = usage.get("prompt_tokens", 0)
            out_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", in_tokens + out_tokens)

            cost = (in_tokens / 1_000_000.0) * model.cost_per_1m_input + \
                   (out_tokens / 1_000_000.0) * model.cost_per_1m_output

            latency = int((time.monotonic() - start_time) * 1000)

            tier_info = getattr(model, "tier", "standard-paid")
            print(f"[INFO] Served by OpenRouter {tier_info} model: {model.id}")

            return GenerationResult(
                content=content,
                tokens=total_tokens,
                latency=latency,
                provider="openrouter",
                model=model.id,
                cost=cost
            )

    async def generate_stream(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> AsyncIterator[str]:
        """Stream tokens from OpenRouter using SSE (OpenAI-compatible format)."""
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not configured.")
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=60.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost:8081",
                    "X-Title": "sevens",
                },
                json={
                    "model": model.id,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                    "stream": True,
                }
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json_mod.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            text = delta.get("content", "")
                            if text:
                                yield text
                        except (json_mod.JSONDecodeError, IndexError, KeyError):
                            continue


class GeminiAdapter:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.health_status = "HEALTHY"
        self.degraded_until: float = 0.0
        if not self.api_key:
            print("[WARN] GEMINI_API_KEY is not set.")
            self.health_status = "OFFLINE"

    def is_healthy(self) -> bool:
        if self.health_status == "DEGRADED" and time.monotonic() > self.degraded_until:
            self.health_status = "HEALTHY"
        return self.health_status == "HEALTHY"

    def mark_degraded(self):
        self.health_status = "DEGRADED"
        self.degraded_until = time.monotonic() + _HEALTH_DEGRADED_SECONDS
        print(f"[HEALTH] Gemini marked DEGRADED for {_HEALTH_DEGRADED_SECONDS}s")

    async def generate(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> GenerationResult:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured.")
        if not (self.api_key.startswith("AIza") or self.api_key.startswith("AQ.")):
            raise ValueError("GEMINI_API_KEY appears invalid (does not start with AIza or AQ.).")

        start_time = time.monotonic()
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model.id}:generateContent",
                headers={"x-goog-api-key": self.api_key},
                json={
                    "system_instruction": {
                        "parts": [{"text": system_prompt}]
                    },
                    "contents": [
                        {"role": "user", "parts": [{"text": prompt}]}
                    ],
                    "generationConfig": {
                        "temperature": temperature,
                    }
                }
            )
            response.raise_for_status()
            data = response.json()

            content = data["candidates"][0]["content"]["parts"][0]["text"]
            
            usage = data.get("usageMetadata", {})
            in_tokens = usage.get("promptTokenCount", 0)
            out_tokens = usage.get("candidatesTokenCount", 0)
            total_tokens = usage.get("totalTokenCount", in_tokens + out_tokens)

            cost = (in_tokens / 1_000_000.0) * model.cost_per_1m_input + \
                   (out_tokens / 1_000_000.0) * model.cost_per_1m_output

            latency = int((time.monotonic() - start_time) * 1000)

            return GenerationResult(
                content=content,
                tokens=total_tokens,
                latency=latency,
                provider="gemini",
                model=model.id,
                cost=cost
            )

    async def generate_stream(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> AsyncIterator[str]:
        """Stream tokens from Gemini using streamGenerateContent with SSE."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured.")
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=60.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                f"https://generativelanguage.googleapis.com/v1beta/models/{model.id}:streamGenerateContent?alt=sse",
                headers={"x-goog-api-key": self.api_key},
                json={
                    "system_instruction": {
                        "parts": [{"text": system_prompt}]
                    },
                    "contents": [
                        {"role": "user", "parts": [{"text": prompt}]}
                    ],
                    "generationConfig": {
                        "temperature": temperature,
                    }
                }
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            chunk = json_mod.loads(data_str)
                            parts = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            for part in parts:
                                text = part.get("text", "")
                                if text:
                                    yield text
                        except (json_mod.JSONDecodeError, IndexError, KeyError):
                            continue


class GroqAdapter:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.health_status = "HEALTHY"
        self.degraded_until: float = 0.0
        if not self.api_key:
            print("[WARN] GROQ_API_KEY is not set.")
            self.health_status = "OFFLINE"

    def is_healthy(self) -> bool:
        if self.health_status == "DEGRADED" and time.monotonic() > self.degraded_until:
            self.health_status = "HEALTHY"
        return self.health_status == "HEALTHY"

    def mark_degraded(self):
        self.health_status = "DEGRADED"
        self.degraded_until = time.monotonic() + _HEALTH_DEGRADED_SECONDS
        print(f"[HEALTH] Groq marked DEGRADED for {_HEALTH_DEGRADED_SECONDS}s")

    async def generate(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> GenerationResult:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not configured.")

        start_time = time.monotonic()
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                json={
                    "model": model.id,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                }
            )
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            in_tokens = usage.get("prompt_tokens", 0)
            out_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", in_tokens + out_tokens)

            cost = (in_tokens / 1_000_000.0) * model.cost_per_1m_input + \
                   (out_tokens / 1_000_000.0) * model.cost_per_1m_output

            latency = int((time.monotonic() - start_time) * 1000)

            return GenerationResult(
                content=content,
                tokens=total_tokens,
                latency=latency,
                provider="groq",
                model=model.id,
                cost=cost
            )

    async def generate_stream(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> AsyncIterator[str]:
        """Stream tokens from Groq using SSE (OpenAI-compatible format)."""
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not configured.")
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=60.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                json={
                    "model": model.id,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                    "stream": True,
                }
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json_mod.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            text = delta.get("content", "")
                            if text:
                                yield text
                        except (json_mod.JSONDecodeError, IndexError, KeyError):
                            continue


# V4.1 — Singleton adapter pool with shared health state.
_adapter_pool: dict[str, ProviderAdapter] = {}

def get_adapter(provider_name: str) -> ProviderAdapter:
    """Return a singleton adapter for the given provider.
    
    V4.1: Adapters are reused across calls so health state (HEALTHY/DEGRADED)
    persists. A provider marked DEGRADED after a timeout will be instantly
    skipped by _execute_agent without waiting 30s to rediscover the failure.
    """
    if provider_name in _adapter_pool:
        return _adapter_pool[provider_name]
    if provider_name == "openrouter":
        _adapter_pool[provider_name] = OpenRouterAdapter()
    elif provider_name == "gemini":
        _adapter_pool[provider_name] = GeminiAdapter()
    elif provider_name == "groq":
        _adapter_pool[provider_name] = GroqAdapter()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
    return _adapter_pool[provider_name]


# =============================================================================
# Execution — V4.1: Health-aware fast failover + Dependency-driven scheduling
# =============================================================================

async def _execute_agent(
    agent_name: str,
    task: str,
    model_id: str,
    stage_id: int,
    context: str = "",
    on_event: object = None,
) -> AgentResult:
    """Execute a single agent using the appropriate provider adapter.
    
    V4.1: Checks provider health BEFORE attempting. If DEGRADED, skips
    directly to fallback — zero timeout wasted. On failure, marks the
    provider DEGRADED so all subsequent agents failover instantly.
    """
    
    primary_model_spec = get_model(model_id)
    if not primary_model_spec:
        return AgentResult(
            agent_name=agent_name, stage_id=stage_id, success=False,
            output="", error=f"Model {model_id} not found in registry."
        )

    system_prompt = get_system_prompt(agent_name)
    
    full_task = task
    if context:
        full_task = f"Previous context and work done by other agents:\n{context}\n\nYour task:\n{task}"

    # V4.1: Check provider health BEFORE attempting
    primary_adapter = get_adapter(primary_model_spec.provider)
    primary_healthy = hasattr(primary_adapter, 'is_healthy') and primary_adapter.is_healthy()
    # If adapter doesn't have is_healthy (Protocol), assume healthy
    if not hasattr(primary_adapter, 'is_healthy'):
        primary_healthy = True

    if primary_healthy:
        try:
            res = await primary_adapter.generate(full_task, primary_model_spec, system_prompt)
            return AgentResult(
                agent_name=agent_name, stage_id=stage_id, success=True,
                output=res.content, duration_ms=res.latency,
                model_used=res.model, provider_used=res.provider,
                tokens=res.tokens, cost=res.cost
            )
        except Exception as e:
            # V4.1: Mark provider as DEGRADED so subsequent agents skip it
            if hasattr(primary_adapter, 'mark_degraded'):
                primary_adapter.mark_degraded()
            error_msg = f"Primary ({primary_model_spec.provider}/{model_id}) failed: {str(e)[:200]}. "
    else:
        error_msg = f"Primary ({primary_model_spec.provider}) is DEGRADED — skipped. "

    # Failover to a DIFFERENT provider
    from .model_registry import best_models
    from .agent_registry import get_agent
    from .model_router import _order_by_provider_priority
    
    agent_spec = get_agent(agent_name)
    cap = agent_spec.preferred_model_capability if agent_spec else "coding"
    
    candidates = _order_by_provider_priority(best_models(cap, limit=10))
    if not candidates:
        candidates = _order_by_provider_priority(best_models("coding", limit=10))
        
    for cand in candidates:
        # Skip the primary provider because it is exhausted
        if cand.provider == primary_model_spec.provider:
            continue
            
        if not cand.is_available:
            continue
            
        # V4.1: Also check fallback provider health
        fb_adapter = get_adapter(cand.provider)
        fb_healthy = hasattr(fb_adapter, 'is_healthy') and fb_adapter.is_healthy()
        if not hasattr(fb_adapter, 'is_healthy'):
            fb_healthy = True
            
        if not fb_healthy:
            continue
            
        try:
            res = await fb_adapter.generate(full_task, cand, system_prompt)
            return AgentResult(
                agent_name=agent_name, stage_id=stage_id, success=True,
                output=res.content, duration_ms=res.latency,
                model_used=res.model, provider_used=res.provider,
                tokens=res.tokens, cost=res.cost
            )
        except Exception as e2:
            if hasattr(fb_adapter, 'mark_degraded'):
                fb_adapter.mark_degraded()
            error_msg += f"Fallback ({cand.provider}/{cand.id}) failed: {str(e2)[:200]}. "
            continue

    error_msg += "All fallback providers exhausted."

    print(f"[AGENT FAILED] {agent_name}: {error_msg}")
    return AgentResult(
        agent_name=agent_name, stage_id=stage_id, success=False,
        output="", error=error_msg
    )


ENSEMBLE_SYNTHESIS_PROMPT = """You are the sevens Ensemble Synthesizer.
You have been provided with N independent answers to the exact same task from different models.
Your job is to reconcile these outputs into a single, definitive, best-possible response.

RULES:
1. Identify agreements across the models (strong signal of correctness).
2. Resolve disagreements logically, choosing the best technical approach.
3. If one model hallucinates or makes a mistake, discard its contribution.
4. DO NOT mention that you are synthesizing multiple models in your final output. Present the final answer directly as if it was written by one expert.
5. If the outputs are code, produce one complete, working codebase.

OUTPUT:
Provide ONLY the final synthesized technical output (code, architecture, analysis).
"""

async def _execute_ensemble(
    agent_name: str,
    full_task: str,
    capability: str,
    stage_id: int,
    context: str,
    on_event=None
) -> AgentResult:
    """Execute a task across multiple models and synthesize the results."""
    start_time = time.monotonic()
    from .model_registry import best_models
    from .model_router import _order_by_provider_priority

    # 1. Get top candidates for ensemble
    candidates = _order_by_provider_priority(best_models(capability, limit=10))
    if not candidates:
        candidates = _order_by_provider_priority(best_models("coding", limit=10))
        
    ensemble_models = candidates[:ENSEMBLE_WIDTH]
    if len(ensemble_models) < 2:
        # Not enough models to ensemble, fallback to single execution
        return await _execute_agent(agent_name, full_task, ensemble_models[0].id if ensemble_models else "llama-3.3-70b-versatile", stage_id, context, on_event)

    print(f"[ENSEMBLE] Launching {len(ensemble_models)} parallel models for {agent_name}...")
    
    # 2. Fire parallel requests
    tasks = []
    for model in ensemble_models:
        adapter = get_adapter(model.provider)
        system = get_system_prompt(agent_name)
        tasks.append(adapter.generate(full_task, model, system))
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 3. Process results
    valid_outputs = []
    ensemble_raw_data = []
    total_tokens = 0
    total_cost = 0.0
    primary_provider = ensemble_models[0].provider
    
    for i, res in enumerate(results):
        model = ensemble_models[i]
        if isinstance(res, Exception):
            print(f"[ENSEMBLE WARN] Model {model.id} failed: {res}")
            continue
            
        valid_outputs.append(f"--- CANDIDATE {i+1} ({model.id}) ---\n{res.content}")
        ensemble_raw_data.append({
            "model": model.id,
            "provider": model.provider,
            "output": res.content,
            "tokens": res.tokens,
            "cost": res.cost,
            "latency": res.latency
        })
        total_tokens += res.tokens
        total_cost += res.cost
        
    if not valid_outputs:
        return AgentResult(
            agent_name=agent_name, stage_id=stage_id, success=False,
            output="", error="All ensemble models failed."
        )
        
    if len(valid_outputs) == 1:
        # Only one succeeded, just use it
        return AgentResult(
            agent_name=agent_name, stage_id=stage_id, success=True,
            output=ensemble_raw_data[0]["output"], duration_ms=ensemble_raw_data[0]["latency"],
            model_used=ensemble_raw_data[0]["model"], provider_used=ensemble_raw_data[0]["provider"],
            tokens=total_tokens, cost=total_cost,
            was_ensemble=True, ensemble_outputs=ensemble_raw_data
        )

    # 4. Synthesize
    synthesis_task = (
        f"Original Task:\n{full_task}\n\n"
        f"Context:\n{context}\n\n"
        f"Candidate Outputs:\n" + "\n\n".join(valid_outputs)
    )
    
    # Cross-family model selection for synthesis
    # Try to pick a free/cheap model from a DIFFERENT provider than the primary generator
    synth_candidates = best_models("reasoning", limit=10)
    synth_model = None
    for cand in synth_candidates:
        if cand.provider != primary_provider and getattr(cand, "tier", "") in ("free", "standard-paid"):
            adpt = get_adapter(cand.provider)
            if hasattr(adpt, "is_healthy") and not adpt.is_healthy():
                continue
            synth_model = cand
            break
            
    if not synth_model:
        # Fallback to anything free/cheap if cross-provider isn't available
        for cand in synth_candidates:
            if getattr(cand, "tier", "") in ("free", "standard-paid"):
                adpt = get_adapter(cand.provider)
                if hasattr(adpt, "is_healthy") and not adpt.is_healthy():
                    continue
                synth_model = cand
                break
                
    if not synth_model:
        synth_model = get_model("llama-3.3-70b-versatile")
        
    print(f"[ENSEMBLE] Synthesizing {len(valid_outputs)} outputs using {synth_model.id} ({synth_model.provider})...")
    
    synth_adapter = get_adapter(synth_model.provider)
    try:
        synth_res = await synth_adapter.generate(synthesis_task, synth_model, ENSEMBLE_SYNTHESIS_PROMPT)
        total_tokens += synth_res.tokens
        total_cost += synth_res.cost
        
        # Calculate a rough agreement score (stubbed - could be improved with actual similarity check)
        agreement = 0.8 if len(valid_outputs) >= 2 else 1.0
        
        return AgentResult(
            agent_name=agent_name, stage_id=stage_id, success=True,
            output=synth_res.content, duration_ms=int((time.monotonic() - start_time) * 1000),
            model_used=ensemble_models[0].id, provider_used=ensemble_models[0].provider,
            tokens=total_tokens, cost=total_cost,
            was_ensemble=True, ensemble_outputs=ensemble_raw_data,
            synthesis_model=synth_model.id, ensemble_agreement=agreement
        )
    except Exception as e:
        print(f"[ENSEMBLE ERROR] Synthesis failed: {e}. Falling back to best candidate.")
        # If synthesis fails, return the first candidate
        return AgentResult(
            agent_name=agent_name, stage_id=stage_id, success=True,
            output=ensemble_raw_data[0]["output"], duration_ms=int((time.monotonic() - start_time) * 1000),
            model_used=ensemble_raw_data[0]["model"], provider_used=ensemble_raw_data[0]["provider"],
            tokens=total_tokens, cost=total_cost,
            was_ensemble=True, ensemble_outputs=ensemble_raw_data,
            ensemble_agreement=0.0
        )


async def execute_dag(
    dag: ExecutionDAG,
    task: str,
    on_event=None,
    retry_budget: dict[str, int] | None = None,
) -> ExecutionResult:
    """Execute the DAG using V4.1 dependency-driven scheduling.

    Instead of waiting for entire stages to complete, each agent launches
    the millisecond ALL of its declared dependencies have finished.
    Independent branches execute concurrently. Dependent branches start
    immediately after their parents — no artificial barriers.

    The algorithm:
    1. Build a {agent_name: asyncio.Future} map.
    2. For each agent, create a coroutine that:
       a. Awaits all its dependency futures.
       b. Builds its context from completed dependency outputs.
       c. Calls _execute_agent.
       d. Resolves its own future.
    3. asyncio.gather all agent coroutines — maximum safe parallelism.
    """
    if retry_budget is None:
        retry_budget = {"planning": 2, "execution": 2}

    start = time.monotonic()
    execution_budget = retry_budget.get("execution", 2)
    retries_used = 0

    # Build agent metadata lookup from the DAG
    agent_models: dict[str, str] = {}      # agent_name -> model_id
    agent_deps: dict[str, list[str]] = {}  # agent_name -> [dependency agent names]
    agent_stage: dict[str, int] = {}       # agent_name -> stage_id

    all_agent_names: list[str] = []
    for stage in dag.stages:
        for agent_name in stage.agents:
            agent_models[agent_name] = stage.models.get(agent_name, "unknown")
            agent_stage[agent_name] = stage.stage_id
            all_agent_names.append(agent_name)
            # Use stage.depends_on to derive agent-level deps:
            # An agent depends on ALL agents from the stages it depends_on.
            deps = []
            for dep_stage_id in stage.depends_on:
                for s in dag.stages:
                    if s.stage_id == dep_stage_id:
                        deps.extend(s.agents)
            agent_deps[agent_name] = deps

    # Create a future for each agent
    agent_futures: dict[str, asyncio.Future] = {}
    loop = asyncio.get_event_loop()
    for name in all_agent_names:
        agent_futures[name] = loop.create_future()

    # Results collector
    all_results: dict[str, AgentResult] = {}

    async def _run_agent(agent_name: str):
        nonlocal retries_used

        # 1. Wait for all dependencies to complete
        deps = agent_deps.get(agent_name, [])
        if deps:
            dep_futures = [agent_futures[d] for d in deps if d in agent_futures]
            if dep_futures:
                await asyncio.gather(*dep_futures)

        # 2. Build context from completed dependency outputs (targeted, not global)
        context_parts = []
        for dep_name in deps:
            dep_result = all_results.get(dep_name)
            if dep_result and dep_result.success:
                context_parts.append(f"--- {dep_name} output ---\n{dep_result.output}")
        context = "\n\n".join(context_parts)

        # 3. Emit agent-start event
        if on_event:
            await on_event({
                "type": "agent_start",
                "agent": agent_name,
                "stage_id": agent_stage.get(agent_name, 0),
                "model": agent_models.get(agent_name, "unknown"),
            })

        # 4. Execute the agent
        model_id = agent_models.get(agent_name, "unknown")
        sid = agent_stage.get(agent_name, 0)
        
        from .agent_registry import get_agent
        agent_spec = get_agent(agent_name)
        capability = agent_spec.preferred_model_capability if agent_spec else "coding"
        
        # Determine if we should use ensemble mode (will be enhanced by planner later)
        # For now, base it on agent capability
        use_ensemble = False
        if capability in ENSEMBLE_CAPABILITIES:
            # Check complexity if available (mocked for now, DAG doesn't pass it yet, will fix in Change 4)
            # Default to True for these capabilities for Pass 1
            use_ensemble = True
            
        if use_ensemble:
            result = await _execute_ensemble(agent_name, task, capability, sid, context, on_event)
        else:
            result = await _execute_agent(agent_name, task, model_id, sid, context, on_event)

        # 5. Retry if failed and budget allows
        if not result.success and retries_used < execution_budget:
            if "429" in (result.error or ""):
                backoff = 1.5 ** retries_used
                await asyncio.sleep(backoff)
            retries_used += 1
            print(f"[RETRY {retries_used}/{execution_budget}] Retrying {agent_name}")
            if on_event:
                await on_event({
                    "type": "agent_retry",
                    "agent": agent_name,
                    "retry_number": retries_used,
                })
            result = await _execute_agent(agent_name, task, model_id, sid, context, on_event)

        # 6. Store result and resolve future
        all_results[agent_name] = result
        if not agent_futures[agent_name].done():
            agent_futures[agent_name].set_result(result)

        # 7. Emit agent-complete event
        if on_event:
            await on_event({
                "type": "agent_complete",
                "agent": result.agent_name,
                "success": result.success,
                "model": result.model_used,
                "provider": result.provider_used,
                "duration_ms": result.duration_ms,
                "tokens": result.tokens,
            })

    # Launch all agents concurrently — dependencies are handled internally
    await asyncio.gather(*[_run_agent(name) for name in all_agent_names])

    # Build stage_results in the original format for backward compatibility
    stage_results_map: dict[int, list[AgentResult]] = {}
    agents_executed = 0
    agents_failed = 0

    for name in all_agent_names:
        result = all_results[name]
        sid = agent_stage.get(name, 0)
        if sid not in stage_results_map:
            stage_results_map[sid] = []
        stage_results_map[sid].append(result)
        agents_executed += 1
        if not result.success:
            agents_failed += 1

    all_stage_results = [stage_results_map[k] for k in sorted(stage_results_map.keys())]

    # Build combined output (still needed for Combiner compatibility)
    combined_parts = []
    for name in all_agent_names:
        r = all_results.get(name)
        if r and r.success:
            combined_parts.append(f"--- {name} output ---\n{r.output}")
    combined = "\n\n".join(combined_parts)

    total_duration = int((time.monotonic() - start) * 1000)

    return ExecutionResult(
        success=agents_failed == 0,
        stage_results=all_stage_results,
        combined_output=combined,
        total_duration_ms=total_duration,
        agents_executed=agents_executed,
        agents_failed=agents_failed,
        retries_used=retries_used,
    )


async def dry_run_dag(dag: ExecutionDAG, task: str) -> dict:
    """Simulate DAG execution without actually running agents."""
    plan = {
        "mode": "dry_run",
        "task": task,
        "stages": [],
        "total_agents": dag.total_agents,
        "estimated_duration_seconds": dag.estimated_duration_seconds,
    }

    for stage in dag.stages:
        plan["stages"].append({
            "stage_id": stage.stage_id,
            "name": stage.name,
            "agents": stage.agents,
            "models": stage.models,
            "parallel": stage.parallel,
            "depends_on": stage.depends_on,
        })

    return plan

