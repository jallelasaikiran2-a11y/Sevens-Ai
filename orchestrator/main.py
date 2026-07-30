"""
VEXORA Orchestrator — FastAPI Entry Point (V2)

The brain of VEXORA Intelligence.

V2 Architecture:
    User → Planner LLM → Plan Validator → DAG Builder → Executor → Verifier → Humanizer → Response

Endpoints:
    POST /api/orchestrate       — Full execution (JSON response)
    GET  /api/orchestrate/stream — SSE streaming execution
    POST /api/plan              — Dry-run: returns only the execution plan
    GET  /api/agents            — Lists all available Ruflo agents
    GET  /api/models            — Lists all registered models
    GET  /api/health            — Health check
"""

from __future__ import annotations

import json
import os
import time
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
    load_dotenv(env_path)
else:
    load_dotenv()

from brain.planner import generate_plan, ExecutionPlan
from brain.dag_builder import build_dag_from_plan, ExecutionDAG
from brain.executor import execute_dag, dry_run_dag, ExecutionResult, AgentResult
from brain.verifier import verify, VerificationResult
from brain.humanizer import humanize, humanize_plan, HumanizedOutput
from brain.confidence_engine import compute_confidence, ConfidenceResult
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
    title="VEXORA Intelligence Orchestrator", 
    lifespan=lifespan,
    description="The brain of VEXORA Intelligence — AI orchestration engine V2",
    version="2.0.0",
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


class OrchestrateResponse(BaseModel):
    success: bool
    answer: str                        # Humanized final text
    response: str                      # Legacy/raw (kept for backwards compat)
    execution: list[dict] = []         # Execution footer metadata
    verification: dict | None = None
    confidence: int | None = None      # 0-100 score
    planning_path: str = "primary"
    
    # Old fields for compat
    plan: dict | None = None
    agents_used: list[dict] = []
    duration_ms: int = 0


# =============================================================================
# Core Orchestration Logic
# =============================================================================

async def _run_orchestration(prompt: str, on_event=None) -> dict:
    """
    Core orchestration pipeline:
    Planner → DAG → Execute → Verify → Humanize → Confidence
    """
    total_start = time.monotonic()

    # 1. PLANNING — Adaptive LLM planner
    if on_event:
        await on_event({"type": "phase", "phase": "planning", "message": "Analyzing request..."})

    plan = await generate_plan(prompt)

    if on_event:
        await on_event({
            "type": "plan_ready",
            "intent": plan.intent,
            "complexity": plan.complexity,
            "agents": plan.agents,
            "confidence": plan.confidence,
            "reasoning": plan.reasoning,
        })

    is_simple_chat = plan.complexity == 0

    # 2. RESEARCH — If research capability is needed
    research_data = None
    if "researcher" in plan.agents and not is_simple_chat:
        if on_event:
            await on_event({"type": "phase", "phase": "research", "message": "Searching the web..."})
        research_data = await search_web(prompt)
        if on_event:
            await on_event({
                "type": "research_complete",
                "sources_count": len(research_data.get("results", [])),
                "success": research_data.get("success", False),
            })

    # 3. BUILD DAG
    dag = build_dag_from_plan(plan)

    # 4. EXECUTE DAG
    if on_event:
        await on_event({"type": "phase", "phase": "executing", "message": "Executing agents..."})

    # Augment task with research context if available
    execution_task = prompt
    if research_data:
        execution_task = prompt + "\n\n" + format_sources_for_prompt(research_data)

    execution_result = await execute_dag(dag, execution_task, on_event=on_event, retry_budget={"planning": 2, "execution": 2})

    # 5. VERIFY (skip for Level 0)
    if not is_simple_chat and plan.verification:
        if on_event:
            await on_event({"type": "phase", "phase": "verifying", "message": "Verifying output..."})

        agent_outputs = []
        for stage_results in execution_result.stage_results:
            for r in stage_results:
                if r.success and r.output:
                    agent_outputs.append(r.output)

        verification = verify(
            execution_result.combined_output,
            prompt,
            plan.capabilities,
            agent_outputs=agent_outputs,
            complexity=str(plan.complexity),
        )
    else:
        verification = VerificationResult(
            passed=True, score=1.0, signals=[], reasons=["Skipped"], layer=0,
        )

    # 6. HUMANIZE (conditional)
    if on_event:
        await on_event({"type": "phase", "phase": "humanizing", "message": "Preparing response..."})

    if is_simple_chat:
        # Strip context formatting for chat
        final_response = execution_result.combined_output
        if "output ---" in final_response:
            final_response = final_response.split("output ---\n")[-1].strip()
    else:
        humanized = await humanize(
            execution_result.combined_output,
            prompt,
            agent_count=execution_result.agents_executed,
        )
        final_response = humanized.content

    # 7. CONFIDENCE
    confidence = compute_confidence(
        verification_passed=verification.passed,
        verification_score=verification.score,
        agents_executed=execution_result.agents_executed,
        agents_failed=execution_result.agents_failed,
        retries_used=execution_result.retries_used if hasattr(execution_result, "retries_used") else 0,
        max_retries=2,
        has_research="researcher" in plan.agents,
        research_sources_count=len(research_data["results"]) if research_data else 0,
        low_confidence_no_retrieval=research_data.get("low_confidence_no_retrieval", False) if research_data else False,
        is_simple_chat=is_simple_chat,
        planning_path_used=plan.planning_path,
    )

    total_duration = int((time.monotonic() - total_start) * 1000)

    # Build agent details
    agents_used = []
    for stage_results in execution_result.stage_results:
        for r in stage_results:
            agent_spec = get_agent(r.agent_name)
            agents_used.append({
                "name": r.agent_name,
                "display_name": agent_spec.display_name if agent_spec else r.agent_name,
                "model": r.model_used,
                "provider": r.provider_used,
                "duration_ms": r.duration_ms,
                "tokens": r.tokens,
                "cost": r.cost,
                "success": r.success,
                "error": r.error,
            })

    # Build execution footer payload
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
        "layer2": "skipped", # Not fully implemented yet
    }

    if on_event:
        await on_event({"type": "phase", "phase": "complete", "message": "Done"})

    return {
        "success": verification.passed,
        "answer": final_response,
        "response": final_response,  # Compat
        "execution": execution,
        "verification_footer": verification_footer,
        "confidence_score": confidence.confidence,
        "planning_path": plan.planning_path,
        
        # Detailed internal payloads (for expert mode)
        "plan": {
            "intent": plan.intent,
            "complexity": plan.complexity,
            "confidence": plan.confidence,
            "reasoning": plan.reasoning,
            "capabilities": plan.capabilities,
            "agents": plan.agents,
            "models": plan.models,
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
            "score": confidence.confidence,
            "summary": confidence.summary,
            "factors": confidence.factors,
        },
        "research": {
            "sources": research_data["results"] if research_data else [],
            "low_confidence": research_data.get("low_confidence_no_retrieval", False) if research_data else False,
        } if research_data else None,
        "agents_used": agents_used,
        "duration_ms": total_duration,
    }


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "vexora-orchestrator",
        "version": "2.0.0",
        "agents_registered": len(AGENTS),
        "models_registered": len(MODELS),
        "providers": list(set(m.provider for m in MODELS.values())),
    }


@app.post("/api/orchestrate")
async def orchestrate(request: PromptRequest):
    """Full orchestration: plan → execute → verify → humanize → confidence."""
    result = await _run_orchestration(request.prompt)

    if not request.expert_mode:
        # Strip internal details for non-expert mode
        return OrchestrateResponse(
            success=result["success"],
            answer=result["answer"],
            response=result["response"],
            execution=result["execution"],
            verification=result["verification_footer"],
            confidence=result["confidence_score"],
            planning_path=result["planning_path"],
            agents_used=result["agents_used"],
            duration_ms=result["duration_ms"],
        )

    return OrchestrateResponse(
        success=result["success"],
        answer=result["answer"],
        response=result["response"],
        execution=result["execution"],
        verification=result["verification_footer"],
        confidence=result["confidence_score"],
        planning_path=result["planning_path"],
        plan=result["plan"],
        agents_used=result["agents_used"],
        duration_ms=result["duration_ms"],
    )


@app.post("/api/orchestrate/stream")
async def orchestrate_stream(request: PromptRequest):
    """SSE streaming orchestration — events emitted line by line as agents execute."""

    async def event_generator():
        async def on_event(event: dict):
            yield f"data: {json.dumps(event)}\n\n"

        # We need to collect events since on_event is a callback
        events: list[dict] = []

        async def collect_event(event: dict):
            events.append(event)

        result = await _run_orchestration(request.prompt, on_event=collect_event)

        # Emit collected events first
        for event in events:
            yield f"data: {json.dumps(event)}\n\n"

        # Then emit the final result
        yield f"data: {json.dumps({'type': 'result', **result})}\n\n"
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
    """Dry-run: returns only the execution plan without executing."""
    plan = await generate_plan(request.prompt)

    return {
        "success": True,
        "intent": plan.intent,
        "complexity": plan.complexity,
        "confidence": plan.confidence,
        "reasoning": plan.reasoning,
        "capabilities": plan.capabilities,
        "agents": plan.agents,
        "models": plan.models,
        "tools": plan.tools,
        "parallel_groups": plan.parallel_groups,
        "verification": plan.verification,
        "humanizer": plan.humanizer,
        "estimated_latency_ms": plan.estimated_latency_ms,
        "estimated_cost": plan.estimated_cost,
        "planner_latency_ms": plan.planner_latency_ms,
    }


@app.get("/api/agents")
async def list_agents_endpoint():
    """List all available Ruflo agents and their capabilities."""
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
