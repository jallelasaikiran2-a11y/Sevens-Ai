"""
sevens Metrics Engine — V3

Tracks operational telemetry across the entire orchestration pipeline:

- Request latency (total, per-stage, per-agent)
- Token costs (per-agent, per-provider)
- Retry events and retry budget consumption
- Fallback behavior (which providers were used as fallbacks)
- Provider health signals

This data feeds the Confidence Engine and the Frontend Execution Panel.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time


@dataclass
class AgentMetric:
    """Metrics for a single agent execution."""
    agent_name: str
    model_used: str
    provider_used: str
    latency_ms: int = 0
    tokens_used: int = 0
    cost: float = 0.0
    success: bool = True
    was_retry: bool = False
    was_fallback: bool = False
    fallback_from: str = ""       # original provider that failed


@dataclass
class StageMetric:
    """Metrics for a single DAG stage."""
    stage_id: int
    stage_name: str
    agents: list[AgentMetric] = field(default_factory=list)
    latency_ms: int = 0
    parallel: bool = False


@dataclass
class PipelineMetrics:
    """
    Complete metrics for one orchestration request.
    """
    request_id: str = ""
    
    # Timing
    total_latency_ms: int = 0
    planning_latency_ms: int = 0
    resolution_latency_ms: int = 0
    execution_latency_ms: int = 0
    verification_latency_ms: int = 0
    humanization_latency_ms: int = 0
    combination_latency_ms: int = 0
    
    # Costs
    total_tokens: int = 0
    total_cost: float = 0.0
    
    # Execution
    stages: list[StageMetric] = field(default_factory=list)
    agents_executed: int = 0
    agents_failed: int = 0
    
    # Resilience
    retries_used: int = 0
    retry_budget_total: int = 0
    fallbacks_triggered: int = 0
    fallback_events: list[dict] = field(default_factory=list)
    
    # Planning
    planning_path: str = "primary"
    
    # Provider health
    provider_stats: dict[str, dict] = field(default_factory=dict)
    # e.g. {"groq": {"calls": 3, "failures": 1, "avg_latency_ms": 500}}

    def add_agent_metric(self, stage_id: int, metric: AgentMetric) -> None:
        """Add an agent metric to the appropriate stage."""
        for stage in self.stages:
            if stage.stage_id == stage_id:
                stage.agents.append(metric)
                return
        # Stage not found, create it
        new_stage = StageMetric(stage_id=stage_id, stage_name=f"Stage {stage_id}")
        new_stage.agents.append(metric)
        self.stages.append(new_stage)

    def record_fallback(self, agent_name: str, from_provider: str, to_provider: str, reason: str = "") -> None:
        """Record a fallback event."""
        self.fallbacks_triggered += 1
        self.fallback_events.append({
            "agent": agent_name,
            "from_provider": from_provider,
            "to_provider": to_provider,
            "reason": reason,
            "timestamp": time.time(),
        })

    def update_provider_stats(self, provider: str, latency_ms: int, success: bool) -> None:
        """Update rolling stats for a provider."""
        if provider not in self.provider_stats:
            self.provider_stats[provider] = {
                "calls": 0,
                "failures": 0,
                "total_latency_ms": 0,
                "avg_latency_ms": 0,
            }
        stats = self.provider_stats[provider]
        stats["calls"] += 1
        if not success:
            stats["failures"] += 1
        stats["total_latency_ms"] += latency_ms
        stats["avg_latency_ms"] = stats["total_latency_ms"] // stats["calls"]

    def finalize(self) -> None:
        """Calculate derived metrics after execution completes."""
        self.total_tokens = 0
        self.total_cost = 0.0
        for stage in self.stages:
            for agent in stage.agents:
                self.total_tokens += agent.tokens_used
                self.total_cost += agent.cost

    def to_telemetry(self) -> dict:
        """Serialize to a dict for the frontend execution panel."""
        return {
            "request_id": self.request_id,
            "total_latency_ms": self.total_latency_ms,
            "planning_latency_ms": self.planning_latency_ms,
            "execution_latency_ms": self.execution_latency_ms,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
            "agents_executed": self.agents_executed,
            "agents_failed": self.agents_failed,
            "retries_used": self.retries_used,
            "fallbacks_triggered": self.fallbacks_triggered,
            "planning_path": self.planning_path,
            "provider_stats": self.provider_stats,
            "stages": [
                {
                    "stage_id": s.stage_id,
                    "stage_name": s.stage_name,
                    "parallel": s.parallel,
                    "latency_ms": s.latency_ms,
                    "agents": [
                        {
                            "agent": a.agent_name,
                            "model": a.model_used,
                            "provider": a.provider_used,
                            "latency_ms": a.latency_ms,
                            "tokens": a.tokens_used,
                            "cost": round(a.cost, 6),
                            "success": a.success,
                            "was_retry": a.was_retry,
                            "was_fallback": a.was_fallback,
                        }
                        for a in s.agents
                    ],
                }
                for s in self.stages
            ],
        }


# =============================================================================
# Timer Utility
# =============================================================================

class PhaseTimer:
    """Context manager for timing pipeline phases."""

    def __init__(self):
        self._start: float = 0.0
        self.elapsed_ms: int = 0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = int((time.monotonic() - self._start) * 1000)
