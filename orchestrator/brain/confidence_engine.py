"""
VEXORA Confidence Engine — V2

Computes a confidence score (0-100) per request based on:
  - Verifier result (pass/fail/severity)
  - retry_count used
  - Retrieval coverage (did research find real sources)
  - Agent success rate
  - Output quality signals

Returns: {confidence: int, factors: {...}}
Attached to every final response sent to the frontend.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ConfidenceResult:
    """Confidence assessment for a VEXORA response."""
    confidence: int                   # 0-100
    factors: dict[str, float]         # Individual factor scores
    summary: str                      # Human-readable explanation


def compute_confidence(
    verification_passed: bool,
    verification_score: float,
    agents_executed: int,
    agents_failed: int,
    retries_used: int,
    max_retries: int,
    has_research: bool = False,
    research_sources_count: int = 0,
    low_confidence_no_retrieval: bool = False,
    is_simple_chat: bool = False,
    planning_path_used: str = "primary"
) -> ConfidenceResult:
    """
    Compute overall confidence score based on execution signals.
    """
    factors: dict[str, float] = {}
    
    # 0. Planning path penalty (deterministic planning implies degraded capability)
    if planning_path_used == "deterministic":
        factors["planning_health"] = -15.0  # Penalty
    elif planning_path_used == "tertiary":
        factors["planning_health"] = -5.0
    else:
        factors["planning_health"] = 0.0

    # 1. Verification factor (0-30 points)
    if verification_passed:
        factors["verification"] = 25.0 + (verification_score * 5.0)
    else:
        factors["verification"] = verification_score * 15.0

    # 2. Agent success rate (0-25 points)
    if agents_executed > 0:
        success_rate = (agents_executed - agents_failed) / agents_executed
        factors["agent_success"] = success_rate * 25.0
    else:
        factors["agent_success"] = 0.0

    # 3. Retry penalty (0-15 points, full points if no retries)
    retry_ratio = retries_used / max(max_retries, 1)
    factors["retry_health"] = (1.0 - retry_ratio) * 15.0

    # 4. Research coverage (0-15 points, only relevant for research tasks)
    if has_research:
        if low_confidence_no_retrieval:
            factors["retrieval_coverage"] = 2.0  # Very low — no real sources
        elif research_sources_count >= 3:
            factors["retrieval_coverage"] = 15.0
        elif research_sources_count >= 1:
            factors["retrieval_coverage"] = 10.0
        else:
            factors["retrieval_coverage"] = 5.0
    else:
        factors["retrieval_coverage"] = 15.0  # Full score for non-research tasks

    # 5. Simplicity bonus (0-15 points)
    if is_simple_chat:
        factors["task_fit"] = 15.0  # Simple chat = high confidence
    elif agents_executed <= 2:
        factors["task_fit"] = 12.0
    elif agents_executed <= 5:
        factors["task_fit"] = 10.0
    else:
        factors["task_fit"] = 8.0  # Many agents = slightly lower confidence

    # Calculate total
    total = sum(factors.values())
    confidence = min(100, max(0, int(total)))

    # Generate summary
    if confidence >= 90:
        summary = "High confidence — all checks passed"
    elif confidence >= 70:
        summary = "Good confidence — minor issues detected"
    elif confidence >= 50:
        summary = "Moderate confidence — some checks failed"
    elif confidence >= 30:
        summary = "Low confidence — significant issues detected"
    else:
        summary = "Very low confidence — critical failures"

    # Round factors for display
    factors = {k: round(v, 1) for k, v in factors.items()}

    return ConfidenceResult(
        confidence=confidence,
        factors=factors,
        summary=summary,
    )
