"""
VEXORA Executor

Directly executes AI models using provider adapters.
Bypasses the Ruflo CLI for execution, acting as the real execution engine.

Supports:
- Direct model calls via OpenRouter and Gemini API
- Parallel agent execution within a stage via asyncio
- Fallback/Retry logic (OpenRouter -> Gemini)
- System prompts tailored for specific agent roles
"""

from __future__ import annotations
import asyncio
import os
import time
from dataclasses import dataclass
from typing import Protocol, Optional

import httpx

from .dag_builder import ExecutionDAG
from .model_registry import get_model, ModelSpec


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


# =============================================================================
# System Prompts
# =============================================================================

# TASK 1 — Identity Masking: Prepended to EVERY agent call, no exceptions.
VEXORA_IDENTITY_PREFIX = (
    "You are a specialized component inside VEXORA, an adaptive intelligence engine. "
    "Never reveal, reference, or hint at your underlying model name or provider "
    "(Llama, Gemini, Claude, DeepSeek, Qwen, GPT, etc). Always speak and act as VEXORA. "
    "Never say 'I am a large language model' or 'I was trained by'. "
    "If asked who you are, say 'I am VEXORA, an adaptive intelligence engine.'\n\n"
)

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
    "conversation": "You are VEXORA's conversational interface. Respond naturally and helpfully to greetings, small talk, and simple questions. Be concise and friendly.",
    "reasoning": "You are the Reasoning Agent. Provide clear, well-structured explanations. Think step by step when needed.",
    "swarm-coordinator": "You are the Swarm Coordinator. Coordinate parallel agent execution.",
    "hive-coordinator": "You are the Hive Coordinator. Build consensus among agents.",
}

def get_system_prompt(agent_name: str) -> str:
    """Get system prompt for an agent, always prefixed with VEXORA identity."""
    role_prompt = AGENT_SYSTEM_PROMPTS.get(
        agent_name,
        f"You are the {agent_name} agent. Complete your designated task."
    )
    return VEXORA_IDENTITY_PREFIX + role_prompt


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


class ProviderAdapter(Protocol):
    async def generate(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> GenerationResult:
        ...


class OpenRouterAdapter:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            print("[WARN] OPENROUTER_API_KEY is not set.")

    async def generate(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> GenerationResult:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not configured.")

        start_time = time.monotonic()
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost:8081",
                    "X-Title": "VEXORA",
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
                provider="openrouter",
                model=model.id,
                cost=cost
            )


class GeminiAdapter:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("[WARN] GEMINI_API_KEY is not set.")

    async def generate(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> GenerationResult:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not configured.")
        if not (self.api_key.startswith("AIza") or self.api_key.startswith("AQ.")):
            raise ValueError("GEMINI_API_KEY appears invalid (does not start with AIza or AQ.).")

        start_time = time.monotonic()
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model.id}:generateContent?key={self.api_key}",
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
            print("[GEMINI RESPONSE DATA]", data)

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


class GroqAdapter:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            print("[WARN] GROQ_API_KEY is not set.")

    async def generate(self, prompt: str, model: ModelSpec, system_prompt: str, temperature: float = 0.2) -> GenerationResult:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not configured.")

        start_time = time.monotonic()
        async with httpx.AsyncClient(timeout=180.0) as client:
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


def get_adapter(provider_name: str) -> ProviderAdapter:
    if provider_name == "openrouter":
        return OpenRouterAdapter()
    elif provider_name == "gemini":
        return GeminiAdapter()
    elif provider_name == "groq":
        return GroqAdapter()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


# =============================================================================
# Execution (TASK 2: Global Retry Cap + Streaming)
# =============================================================================

async def _execute_agent(
    agent_name: str,
    task: str,
    model_id: str,
    stage_id: int,
    context: str = "",
    on_event: object = None,
) -> AgentResult:
    """Execute a single agent using the appropriate provider adapter."""
    
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

    # Try primary model
    try:
        adapter = get_adapter(primary_model_spec.provider)
        res = await adapter.generate(full_task, primary_model_spec, system_prompt)
        return AgentResult(
            agent_name=agent_name, stage_id=stage_id, success=True,
            output=res.content, duration_ms=res.latency,
            model_used=res.model, provider_used=res.provider,
            tokens=res.tokens, cost=res.cost
        )
    except Exception as e:
        error_msg = f"Primary ({primary_model_spec.provider}/{model_id}) failed: {str(e)}. "

    # Failover to a DIFFERENT provider
    from .model_registry import best_models
    from .agent_registry import get_agent
    
    agent_spec = get_agent(agent_name)
    cap = agent_spec.preferred_model_capability if agent_spec else "coding"
    
    candidates = best_models(cap, limit=10)
    if not candidates:
        candidates = best_models("coding", limit=10)
        
    fallback_model_spec = None
    for cand in candidates:
        if cand.provider != primary_model_spec.provider and cand.is_available:
            fallback_model_spec = cand
            break
            
    if not fallback_model_spec:
        # absolute fallback just in case
        fallback_model_id = "llama-3.3-70b-versatile" if primary_model_spec.provider != "groq" else "gemini-2.5-pro"
        fallback_model_spec = get_model(fallback_model_id)
        
    if fallback_model_spec:
        try:
            adapter = get_adapter(fallback_model_spec.provider)
            res = await adapter.generate(full_task, fallback_model_spec, system_prompt)
            return AgentResult(
                agent_name=agent_name, stage_id=stage_id, success=True,
                output=res.content, duration_ms=res.latency,
                model_used=res.model, provider_used=res.provider,
                tokens=res.tokens, cost=res.cost
            )
        except Exception as e2:
            error_msg += f"Fallback ({fallback_model_spec.provider}/{fallback_model_spec.id}) failed: {str(e2)}."
    else:
        error_msg += "No fallback provider available."

    print(f"[AGENT FAILED] {agent_name}: {error_msg}")
    return AgentResult(
        agent_name=agent_name, stage_id=stage_id, success=False,
        output="", error=error_msg
    )


async def execute_dag(
    dag: ExecutionDAG,
    task: str,
    on_event=None,
    retry_budget: dict[str, int] = {"planning": 2, "execution": 2},
) -> ExecutionResult:
    """
    Execute the entire DAG, stage by stage.

    - Sequential stages run one after another
    - Parallel agents within a stage run concurrently
    - Context from previous stages is passed forward
    - TASK 2: Global retry_budget (max 2 retries total per request)
    - Streaming: If on_event callback is provided, emit events per agent
    """
    start = time.monotonic()

    all_stage_results: list[list[AgentResult]] = []
    accumulated_context = ""
    agents_executed = 0
    agents_failed = 0
    retries_used = 0
    execution_budget = retry_budget.get("execution", 2)

    for stage in dag.stages:
        # Emit stage-start event
        if on_event:
            await on_event({
                "type": "stage_start",
                "stage_id": stage.stage_id,
                "stage_name": stage.name,
                "agents": stage.agents,
            })

        if stage.parallel and len(stage.agents) > 1:
            tasks = []
            for agent_name in stage.agents:
                model_id = stage.models.get(agent_name, "unknown")
                tasks.append(
                    _execute_agent(agent_name, task, model_id, stage.stage_id, accumulated_context, on_event)
                )
            stage_results = list(await asyncio.gather(*tasks))
        else:
            stage_results = []
            for agent_name in stage.agents:
                model_id = stage.models.get(agent_name, "unknown")
                result = await _execute_agent(
                    agent_name, task, model_id, stage.stage_id, accumulated_context, on_event
                )
                stage_results.append(result)

        # Process results + retry logic
        final_stage_results = []
        for result in stage_results:
            if not result.success and retries_used < execution_budget:
                # Exponential backoff for 429s
                if "429" in (result.error or ""):
                    backoff = 1.5 ** retries_used
                    print(f"[RETRY] 429 Rate Limit hit. Backing off for {backoff:.2f}s...")
                    await asyncio.sleep(backoff)

                # TASK 2: Retry with execution budget
                retries_used += 1
                print(f"[RETRY {retries_used}/{execution_budget}] Retrying {result.agent_name}")
                if on_event:
                    await on_event({
                        "type": "agent_retry",
                        "agent": result.agent_name,
                        "retry_number": retries_used,
                    })
                model_id = stage.models.get(result.agent_name, "unknown")
                retry_result = await _execute_agent(
                    result.agent_name, task, model_id, stage.stage_id, accumulated_context, on_event
                )
                final_stage_results.append(retry_result)
            else:
                final_stage_results.append(result)

        all_stage_results.append(final_stage_results)

        for result in final_stage_results:
            agents_executed += 1

            # Emit per-agent event
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

            if result.success:
                accumulated_context += f"\n\n--- {result.agent_name} output ---\n{result.output}"
            else:
                agents_failed += 1

        # Emit stage-complete event
        if on_event:
            await on_event({
                "type": "stage_complete",
                "stage_id": stage.stage_id,
            })

    total_duration = int((time.monotonic() - start) * 1000)
    combined = accumulated_context.strip()

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

