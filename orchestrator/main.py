"""
sevens Orchestrator — FastAPI Entry Point (V3)

The brain of Sevens ai — Adaptive Intelligence Engine.

V3 Architecture:
    User → Planner → Capability Resolver → Registries → Execution Context Builder
        → DAG Builder → Executor (with Memory) → Combiner → Verifier
        → Humanizer → Trust Engine → Metrics → Response

Endpoints:
    POST /api/orchestrate       — Full execution (JSON response)
    POST /api/orchestrate/stream — SSE streaming execution
    POST /api/plan              — Dry-run: returns only the execution plan
    GET  /api/agents            — Lists all available Sevens agents
    GET  /api/models            — Lists all registered models
    GET  /api/health            — Health check
"""

from __future__ import annotations

import json
import os
import time
import uuid
import asyncio
from typing import Optional, Any
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Load shared .env from workspace root
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

# V3 imports
from brain.planner import generate_plan, PlanOutput
from brain.capability_resolver import resolve_capabilities, ResolvedRequirements
from brain.execution_context_builder import build_execution_context, ExecutionContext
from brain.dag_builder import build_dag_from_plan, ExecutionDAG
from brain.executor import execute_dag, dry_run_dag, ExecutionResult, AgentResult
from brain.combiner import combine_contracts, parse_agent_output, AgentContract, CombinedDraft
from brain.verifier import verify, VerificationResult
from brain.humanizer import humanize, humanize_plan, HumanizedOutput
from brain.confidence_engine import compute_trust, TrustAssessment
from brain.metrics_engine import PipelineMetrics, AgentMetric, PhaseTimer
from brain.memory_manager import ExecutionMemory, get_or_create_session
from brain.research_engine import search_web, format_sources_for_prompt
from brain.agent_registry import list_all_agents, AGENTS, get_agent
from brain.model_registry import MODELS, list_all_capabilities

# =============================================================================
# FastAPI App
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    from verify_keys import verify_providers
    try:
        await verify_providers()
    except Exception as e:
        print(f"[FATAL STARTUP ERROR] Verification failed: {e}")
        import sys
        sys.exit(1)
    yield

app = FastAPI(
    title="Sevens ai Orchestrator",
    lifespan=lifespan,
    description="The brain of Sevens ai — Adaptive Intelligence Engine V3",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:8081", "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Request / Response models
# =============================================================================

class PromptRequest(BaseModel):
    prompt: str
    dry_run: bool = False
    expert_mode: bool = False
    session_id: str | None = None


class OrchestrateResponse(BaseModel):
    success: bool
    answer: str
    response: str                      # Legacy compat
    execution: list[dict] = []
    verification: dict | None = None
    confidence: int | None = None
    planning_path: str = "primary"
    trust_factors: list[dict] = []
    memory_stats: dict | None = None
    metrics: dict | None = None

    # Compat
    plan: dict | None = None
    agents_used: list[dict] = []
    duration_ms: int = 0


# =============================================================================
# V3 Core Orchestration Pipeline
# =============================================================================

async def _run_orchestration(prompt: str, on_event=None, session_id: str | None = None) -> dict:
    """
    V3 Orchestration Pipeline:
    Planner → Capability Resolver → Execution Context Builder →
    DAG → Executor (with Memory) → Combiner → Verifier →
    Humanizer → Trust Engine → Metrics → Response
    """
    metrics = PipelineMetrics()
    total_start = time.monotonic()

    # --- Session Memory ---
    session = get_or_create_session(session_id)

    # =========================================================================
    # 1. PLANNING — Pure intent analysis
    # =========================================================================
    if on_event:
        await on_event({"type": "phase", "phase": "planning", "message": "Analyzing request..."})

    with PhaseTimer() as plan_timer:
        plan = await generate_plan(prompt)
    metrics.planning_latency_ms = plan_timer.elapsed_ms
    metrics.planning_path = plan.planning_path

    # Handle clarification loop
    if plan.needs_clarification and plan.clarification_questions:
        return {
            "success": True,
            "answer": "I need a bit more information to give you the best answer:\n\n" +
                      "\n".join(f"- {q}" for q in plan.clarification_questions),
            "response": "",
            "execution": [],
            "verification_footer": {"layer1": "skipped", "layer2": "skipped"},
            "confidence_score": 50,
            "planning_path": plan.planning_path,
            "trust_factors": [],
            "memory_stats": None,
            "metrics": None,
            "plan": {"intent": plan.intent, "complexity": plan.complexity, "capabilities": plan.capabilities},
            "agents_used": [],
            "duration_ms": plan_timer.elapsed_ms,
            "needs_clarification": True,
            "clarification_questions": plan.clarification_questions,
        }

    if on_event:
        await on_event({
            "type": "plan_ready",
            "intent": plan.intent,
            "complexity": plan.complexity,
            "capabilities": plan.capabilities,
            "confidence": plan.confidence,
            "reasoning": plan.reasoning,
        })

    is_simple_chat = plan.complexity == 0

    # =========================================================================
    # 2. CAPABILITY RESOLUTION
    # =========================================================================
    if on_event:
        await on_event({"type": "phase", "phase": "resolving", "message": "Resolving capabilities..."})

    with PhaseTimer() as resolve_timer:
        requirements = resolve_capabilities(plan.capabilities, plan.complexity)
    metrics.resolution_latency_ms = resolve_timer.elapsed_ms

    # =========================================================================
    # 3. EXECUTION CONTEXT BUILDING
    # =========================================================================
    exec_context = build_execution_context(
        task=prompt,
        intent=plan.intent,
        complexity=plan.complexity,
        requirements=requirements,
        conversation_memory=session,
        planning_path=plan.planning_path,
    )

    # Inject user constraints into execution memory
    for constraint in plan.constraints:
        exec_context.execution_memory.add_fact(
            agent="planner",
            statement=constraint,
            source="user",
        )

    # =========================================================================
    # 4. RESEARCH (if needed)
    # =========================================================================
    research_data = None
    has_research = "research" in plan.capabilities and not is_simple_chat

    if has_research:
        if on_event:
            await on_event({"type": "phase", "phase": "research", "message": "Searching the web..."})
        research_data = await search_web(prompt)
        if research_data.get("success") and research_data.get("results"):
            for r in research_data["results"]:
                exec_context.execution_memory.add_fact(
                    agent="researcher",
                    statement=f"{r['title']}: {r['snippet'][:150]}",
                    source="research",
                    confidence=0.8,
                )
        if on_event:
            await on_event({
                "type": "research_complete",
                "sources_count": len(research_data.get("results", [])),
                "success": research_data.get("success", False),
            })

    # =========================================================================
    # 5. BUILD DAG from Execution Context
    # =========================================================================
    dag = _build_dag_from_context(exec_context)

    # =========================================================================
    # 6. EXECUTE DAG
    # =========================================================================
    if on_event:
        await on_event({"type": "phase", "phase": "executing", "message": "Executing agents..."})

    execution_task = prompt
    if research_data:
        execution_task = prompt + "\n\n" + format_sources_for_prompt(research_data)

    # Inject shared memory context
    memory_context = exec_context.execution_memory.to_context_prompt()
    if memory_context:
        execution_task = execution_task + "\n\n" + memory_context

    with PhaseTimer() as exec_timer:
        execution_result = await execute_dag(
            dag, execution_task, on_event=on_event,
            retry_budget={"planning": 2, "execution": 2}
        )
    metrics.execution_latency_ms = exec_timer.elapsed_ms
    metrics.agents_executed = execution_result.agents_executed
    metrics.agents_failed = execution_result.agents_failed
    metrics.retries_used = execution_result.retries_used

    # Record per-agent metrics
    for stage_results in execution_result.stage_results:
        for r in stage_results:
            agent_metric = AgentMetric(
                agent_name=r.agent_name,
                model_used=r.model_used,
                provider_used=r.provider_used,
                latency_ms=r.duration_ms,
                tokens_used=r.tokens,
                cost=r.cost,
                success=r.success,
            )
            metrics.add_agent_metric(0, agent_metric)
            metrics.update_provider_stats(r.provider_used, r.duration_ms, r.success)

    # =========================================================================
    # 7. COMBINE — Structured agent contract merging
    # =========================================================================
    if on_event:
        await on_event({"type": "phase", "phase": "combining", "message": "Combining agent outputs..."})

    with PhaseTimer() as combine_timer:
        contracts: list[AgentContract] = []
        for stage_results in execution_result.stage_results:
            for r in stage_results:
                if r.success and r.output:
                    contract = parse_agent_output(r.agent_name, r.output)
                    contracts.append(contract)

        combined_draft = combine_contracts(contracts, prompt)
    metrics.combination_latency_ms = combine_timer.elapsed_ms

    # =========================================================================
    # 7.5 RESPONSE PLANNER (V4.1)
    # =========================================================================
    if not is_simple_chat and len(contracts) > 1:
        if on_event:
            await on_event({"type": "phase", "phase": "response_planning", "message": "Planning response structure..."})
        from brain.response_planner import plan_response
        agent_outputs_dict = {c.agent_name: c.raw_output for c in contracts if c.raw_output}
        response_outline = await plan_response(prompt, agent_outputs_dict)
        if on_event and response_outline.raw_outline:
            await on_event({"type": "response_plan", "outline": response_outline.raw_outline})

    # =========================================================================
    # 8. VERIFY
    # =========================================================================
    if not is_simple_chat and requirements.requires_verification:
        if on_event:
            await on_event({"type": "phase", "phase": "verifying", "message": "Verifying output..."})

        with PhaseTimer() as verify_timer:
            agent_outputs = [c.raw_output for c in contracts if c.raw_output]
            verification = verify(
                combined_draft.content,
                prompt,
                plan.capabilities,
                agent_outputs=agent_outputs,
                complexity=str(plan.complexity),
            )
        metrics.verification_latency_ms = verify_timer.elapsed_ms
    else:
        verification = VerificationResult(
            passed=True, score=1.0, signals=[], reasons=["Skipped"], layer=0,
        )

    # =========================================================================
    # 9. HUMANIZE & STREAM (V4.1)
    # =========================================================================
    if on_event:
        await on_event({"type": "phase", "phase": "humanizing", "message": "Preparing response..."})

    from brain.humanizer import humanize_stream, humanize

    with PhaseTimer() as human_timer:
        if is_simple_chat:
            final_response = execution_result.combined_output
            if "output ---" in final_response:
                final_response = final_response.split("output ---\n")[-1].strip()
            if on_event:
                await on_event({"type": "chunk", "text": final_response})
        else:
            # V4.1: If on_event is provided, stream tokens in real-time
            if on_event:
                chunks = []
                async for chunk in humanize_stream(combined_draft.content, prompt, agent_count=len(contracts)):
                    chunks.append(chunk)
                    await on_event({"type": "chunk", "text": chunk})
                final_response = "".join(chunks)
            else:
                humanized = await humanize(
                    combined_draft.content,
                    prompt,
                    agent_count=len(contracts),
                )
                final_response = humanized.content

    metrics.humanization_latency_ms = human_timer.elapsed_ms

    # =========================================================================
    # 10. TRUST ASSESSMENT
    # =========================================================================
    memory_stats = exec_context.execution_memory.summary_stats()

    # Aggregate ensemble metrics
    ensemble_used = False
    ensemble_agreements = []
    for stage_results in execution_result.stage_results:
        for r in stage_results:
            if getattr(r, "was_ensemble", False):
                ensemble_used = True
                ensemble_agreements.append(getattr(r, "ensemble_agreement", 1.0))
    avg_ensemble_agreement = sum(ensemble_agreements) / len(ensemble_agreements) if ensemble_agreements else 1.0

    trust = compute_trust(
        verification_passed=verification.passed,
        verification_score=verification.score,
        agents_executed=execution_result.agents_executed,
        agents_failed=execution_result.agents_failed,
        agent_contributions=combined_draft.agent_contributions,
        retries_used=execution_result.retries_used,
        max_retries=2,
        fallbacks_triggered=metrics.fallbacks_triggered,
        planning_path=plan.planning_path,
        has_research=has_research,
        research_sources_count=len(research_data["results"]) if research_data else 0,
        low_confidence_no_retrieval=research_data.get("low_confidence_no_retrieval", False) if research_data else False,
        execution_memory_decisions=memory_stats["decisions"],
        execution_memory_facts=memory_stats["facts"],
        cross_agent_agreement=combined_draft.cross_agent_agreement,
        conflicts_detected=len(combined_draft.conflicts_detected),
        conflicts_resolved=combined_draft.conflicts_resolved,
        is_simple_chat=is_simple_chat,
        complexity=plan.complexity,
        ensemble_used=ensemble_used,
        ensemble_agreement=avg_ensemble_agreement,
    )

    # =========================================================================
    # FINALIZE
    # =========================================================================
    total_duration = int((time.monotonic() - total_start) * 1000)
    metrics.total_latency_ms = total_duration
    metrics.finalize()

    # Record conversation turn
    session.add_turn("user", prompt, capabilities=plan.capabilities)
    session.add_turn("assistant", final_response[:500],
                     capabilities=plan.capabilities,
                     agents=requirements.agent_types)

    # Build agent details
    agents_used = []
    for stage_results in execution_result.stage_results:
        for r in stage_results:
            agent_spec = get_agent(r.agent_name)
            agent_dict = {
                "name": r.agent_name,
                "display_name": agent_spec.display_name if agent_spec else r.agent_name,
                "model": r.model_used,
                "provider": r.provider_used,
                "duration_ms": r.duration_ms,
                "tokens": r.tokens,
                "cost": r.cost,
                "success": r.success,
                "error": r.error,
            }
            if getattr(r, "was_ensemble", False):
                agent_dict["was_ensemble"] = True
                agent_dict["ensemble_outputs"] = r.ensemble_outputs
                agent_dict["synthesis_model"] = r.synthesis_model
                agent_dict["ensemble_agreement"] = r.ensemble_agreement
                
            agents_used.append(agent_dict)

    # Execution footer
    execution = []
    for r in agents_used:
        execution.append({
            "agent": r["display_name"],
            "model": r["model"],
            "provider": r["provider"],
            "status": "completed" if r["success"] else "failed",
        })

    verification_footer = {
        "layer1": "passed" if verification.passed else "failed",
        "layer2": "skipped",
    }

    # Trust factors for frontend
    trust_factors_payload = [
        {
            "name": f.name,
            "score": round(f.score, 2),
            "explanation": f.explanation,
            "severity": f.severity,
        }
        for f in trust.trust_factors
    ]

    if on_event:
        await on_event({"type": "phase", "phase": "complete", "message": "Done"})

    return {
        "success": verification.passed,
        "answer": final_response,
        "response": final_response,
        "execution": execution,
        "verification_footer": verification_footer,
        "confidence_score": trust.overall_confidence,
        "planning_path": plan.planning_path,
        "trust_factors": trust_factors_payload,
        "trust_summary": trust.summary,
        "trust_recommendation": trust.recommendation,
        "memory_stats": memory_stats,
        "metrics": metrics.to_telemetry(),

        # Detailed payloads
        "plan": {
            "intent": plan.intent,
            "complexity": plan.complexity,
            "confidence": plan.confidence,
            "reasoning": plan.reasoning,
            "capabilities": plan.capabilities,
            "constraints": plan.constraints,
            "required_outputs": plan.required_outputs,
            "planner_latency_ms": plan.planner_latency_ms,
        },
        "verification": {
            "passed": verification.passed,
            "score": verification.score,
            "layer": verification.layer,
            "reasons": verification.reasons,
            "signals": [
                {"name": s.name, "passed": s.passed, "severity": s.severity, "detail": s.detail}
                for s in verification.signals
            ],
        },
        "confidence": {
            "score": trust.overall_confidence,
            "summary": trust.summary,
            "recommendation": trust.recommendation,
            "agent_contributions": trust.agent_contributions,
        },
        "research": {
            "sources": research_data["results"] if research_data else [],
            "low_confidence": research_data.get("low_confidence_no_retrieval", False) if research_data else False,
        } if research_data else None,
        "agents_used": agents_used,
        "duration_ms": total_duration,
    }


def _build_dag_from_context(ctx: ExecutionContext) -> ExecutionDAG:
    """Build a DAG from the V3 ExecutionContext (bridging to existing dag_builder)."""
    from brain.dag_builder import DAGStage, ExecutionDAG

    stages: list[DAGStage] = []
    # Group assignments by stage_order
    groups: dict[int, list] = {}
    for assignment in ctx.assignments:
        order = assignment.stage_order
        if order not in groups:
            groups[order] = []
        groups[order].append(assignment)

    for i, order in enumerate(sorted(groups.keys())):
        group = groups[order]
        agent_names = [a.agent_name for a in group]
        models = {a.agent_name: a.model_spec.id for a in group}

        if len(group) == 1:
            name = group[0].agent_spec.display_name
        else:
            name = f"Stage {i}"

        stages.append(DAGStage(
            stage_id=i,
            name=name,
            agents=agent_names,
            models=models,
            parallel=len(group) > 1,
            depends_on=[i - 1] if i > 0 else [],
        ))

    total_agents = sum(len(s.agents) for s in stages)
    sequential_count = sum(1 for s in stages if not s.parallel)
    parallel_count = sum(1 for s in stages if s.parallel)
    estimated_duration = (sequential_count * 30) + (parallel_count * 30)

    return ExecutionDAG(
        stages=stages,
        total_stages=len(stages),
        total_agents=total_agents,
        has_parallel_stages=any(s.parallel for s in stages),
        estimated_duration_seconds=estimated_duration,
    )


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "sevens-orchestrator",
        "version": "3.0.0",
        "agents_registered": len(AGENTS),
        "models_registered": len(MODELS),
        "providers": list(set(m.provider for m in MODELS.values())),
    }


@app.post("/api/orchestrate")
async def orchestrate(request: PromptRequest):
    """Full orchestration: plan → resolve → execute → combine → verify → humanize → trust."""
    result = await _run_orchestration(request.prompt, session_id=request.session_id)

    return OrchestrateResponse(
        success=result["success"],
        answer=result["answer"],
        response=result["response"],
        execution=result["execution"],
        verification=result["verification_footer"],
        confidence=result["confidence_score"],
        planning_path=result["planning_path"],
        trust_factors=result.get("trust_factors", []),
        memory_stats=result.get("memory_stats"),
        metrics=result.get("metrics") if request.expert_mode else None,
        plan=result.get("plan") if request.expert_mode else None,
        agents_used=result["agents_used"],
        duration_ms=result["duration_ms"],
    )


@app.post("/api/orchestrate/stream")
async def orchestrate_stream(request: PromptRequest):
    """V4.1 Real-time SSE streaming orchestration."""
    queue: asyncio.Queue = asyncio.Queue()

    async def collect_event(event: dict):
        await queue.put(event)

    async def run_pipeline():
        try:
            result = await _run_orchestration(
                request.prompt, on_event=collect_event, session_id=request.session_id
            )
            await queue.put({"type": "result", **result})
        except Exception as exc:
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)  # Sentinel to signal completion

    async def event_generator():
        asyncio.create_task(run_pipeline())
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/plan")
async def create_plan(request: PromptRequest):
    """Dry-run: returns the plan + resolved requirements without executing."""
    plan = await generate_plan(request.prompt)
    requirements = resolve_capabilities(plan.capabilities, plan.complexity)

    return {
        "success": True,
        "intent": plan.intent,
        "complexity": plan.complexity,
        "confidence": plan.confidence,
        "reasoning": plan.reasoning,
        "capabilities": plan.capabilities,
        "constraints": plan.constraints,
        "required_outputs": plan.required_outputs,
        "missing_information": plan.missing_information,
        "needs_clarification": plan.needs_clarification,
        "clarification_questions": plan.clarification_questions,
        "resolved_agents": requirements.agent_types,
        "resolved_tools": requirements.tool_types,
        "model_capabilities": requirements.model_capabilities,
        "parallel_groups": requirements.parallel_groups,
        "planner_latency_ms": plan.planner_latency_ms,
        "planning_path": plan.planning_path,
    }


@app.get("/api/agents")
async def list_agents_endpoint():
    """List all available Sevens agents and their capabilities."""
    agents = list_all_agents()
    return {
        "total": len(agents),
        "agents": [
            {
                "name": a.name,
                "display_name": a.display_name,
                "capabilities": a.capabilities,
                "preferred_model_capability": a.preferred_model_capability,
                "tier": a.tier,
                "description": a.description,
                "tags": a.tags,
            }
            for a in agents
        ],
    }


@app.get("/api/models")
async def list_models_endpoint():
    """List all registered models and their capabilities."""
    return {
        "total": len(MODELS),
        "capabilities": list_all_capabilities(),
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "provider": m.provider,
                "capabilities": m.capabilities,
                "quality_tier": m.quality_tier,
                "speed_tier": m.speed_tier,
                "cost_per_1m_input": m.cost_per_1m_input,
                "cost_per_1m_output": m.cost_per_1m_output,
                "is_available": m.is_available,
                "tags": m.tags,
            }
            for m in MODELS.values()
        ],
    }


# =============================================================================
# Run
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
