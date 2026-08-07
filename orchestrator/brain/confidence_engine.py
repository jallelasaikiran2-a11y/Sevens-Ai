"""
sevens Confidence & Trust Engine — V3

Replaces the V2 single-number confidence score with a multi-dimensional
trust assessment that explains WHY a response should (or shouldn't) be trusted.

Dimensions:
  - Overall Confidence (0-100)
  - Trust Factors (detailed breakdown)
  - Verification Results
  - Agent Contributions
  - Provider Health
  - Memory Quality
  - Fallback Usage
  - Evidence Availability
  - Cross-Agent Agreement
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TrustFactor:
    """A single trust dimension."""
    name: str
    score: float            # 0.0 - 1.0
    weight: float           # how much this matters (0.0-1.0)
    explanation: str
    severity: str = "info"  # "info" | "warning" | "critical"


@dataclass
class TrustAssessment:
    """Complete trust assessment for a sevens response."""
    overall_confidence: int              # 0-100
    trust_factors: list[TrustFactor]
    summary: str                         # Human-readable overall summary
    agent_contributions: dict[str, str]  # agent → what they contributed
    recommendation: str = ""             # "high_trust" | "moderate_trust" | "low_trust" | "review_required"


def compute_trust(
    # Verification
    verification_passed: bool,
    verification_score: float,
    verification_signals: list[dict] | None = None,

    # Execution
    agents_executed: int = 0,
    agents_failed: int = 0,
    agent_contributions: dict[str, str] | None = None,

    # Resilience
    retries_used: int = 0,
    max_retries: int = 2,
    fallbacks_triggered: int = 0,
    planning_path: str = "primary",

    # Research
    has_research: bool = False,
    research_sources_count: int = 0,
    low_confidence_no_retrieval: bool = False,

    # Memory
    execution_memory_decisions: int = 0,
    execution_memory_facts: int = 0,

    # Combiner
    cross_agent_agreement: float = 1.0,
    conflicts_detected: int = 0,
    conflicts_resolved: int = 0,

    # Task
    is_simple_chat: bool = False,
    complexity: int = 2,

    # V5 Ensemble (Fugu-style MoA)
    ensemble_used: bool = False,
    ensemble_agreement: float = 1.0,
) -> TrustAssessment:
    """
    Compute a multi-dimensional trust assessment.
    """
    factors: list[TrustFactor] = []
    contributions = agent_contributions or {}

    # --- 1. Verification Trust ---
    if verification_passed:
        v_score = 0.8 + (verification_score * 0.2)
        v_explanation = f"All verification checks passed (score: {verification_score:.2f})"
        v_severity = "info"
    else:
        v_score = verification_score * 0.5
        v_explanation = f"Verification issues detected (score: {verification_score:.2f})"
        v_severity = "warning"

    factors.append(TrustFactor(
        name="Verification",
        score=v_score,
        weight=0.25,
        explanation=v_explanation,
        severity=v_severity,
    ))

    # --- 2. Agent Success ---
    if agents_executed > 0:
        success_rate = (agents_executed - agents_failed) / agents_executed
        if success_rate == 1.0:
            a_explanation = f"All {agents_executed} agents completed successfully"
        else:
            a_explanation = f"{agents_failed}/{agents_executed} agents failed"
    else:
        success_rate = 0.0
        a_explanation = "No agents executed"

    factors.append(TrustFactor(
        name="Agent Success",
        score=success_rate,
        weight=0.20,
        explanation=a_explanation,
        severity="info" if success_rate >= 0.8 else "warning",
    ))

    # --- 3. Planning Health ---
    planning_scores = {
        "primary": 1.0,
        "fast_path": 1.0,
        "secondary": 0.7,
        "tertiary": 0.4,
        "deterministic": 0.2,
    }
    p_score = planning_scores.get(planning_path, 0.5)
    if planning_path in ("primary", "fast_path"):
        p_explanation = "Primary planner responded successfully"
    elif planning_path == "deterministic":
        p_explanation = "All LLM planners failed — using keyword-based fallback"
    else:
        p_explanation = f"Used {planning_path} fallback planner"

    factors.append(TrustFactor(
        name="Planning Health",
        score=p_score,
        weight=0.10,
        explanation=p_explanation,
        severity="info" if p_score >= 0.7 else "warning",
    ))

    # --- 4. Provider Resilience ---
    if fallbacks_triggered == 0 and retries_used == 0:
        r_score = 1.0
        r_explanation = "No retries or fallbacks needed"
    elif fallbacks_triggered > 0:
        r_score = max(0.3, 1.0 - (fallbacks_triggered * 0.2))
        r_explanation = f"{fallbacks_triggered} provider fallback(s) triggered"
    else:
        r_score = max(0.5, 1.0 - (retries_used / max(max_retries, 1) * 0.3))
        r_explanation = f"{retries_used} retry(ies) used"

    factors.append(TrustFactor(
        name="Provider Resilience",
        score=r_score,
        weight=0.10,
        explanation=r_explanation,
        severity="info" if r_score >= 0.7 else "warning",
    ))

    # --- 5. Evidence Availability ---
    if has_research:
        if research_sources_count >= 3:
            e_score = 1.0
            e_explanation = f"Grounded with {research_sources_count} real-time sources"
        elif research_sources_count >= 1:
            e_score = 0.7
            e_explanation = f"Partially grounded ({research_sources_count} source(s))"
        elif low_confidence_no_retrieval:
            e_score = 0.2
            e_explanation = "No real-time sources — based on training data only"
        else:
            e_score = 0.4
            e_explanation = "Research attempted but few results found"
    else:
        e_score = 0.8  # Non-research tasks don't need external evidence
        e_explanation = "Task does not require external research"

    factors.append(TrustFactor(
        name="Evidence",
        score=e_score,
        weight=0.10,
        explanation=e_explanation,
    ))

    # --- 5.5 Ensemble Agreement (V5 MoA) ---
    if ensemble_used:
        ea_score = ensemble_agreement
        ea_explanation = f"Ensemble synthesis agreement: {ensemble_agreement:.0%}"
        factors.append(TrustFactor(
            name="Ensemble Agreement",
            score=ea_score,
            weight=0.20,
            explanation=ea_explanation,
            severity="info" if ea_score >= 0.8 else "warning",
        ))

    # --- 6. Cross-Agent Agreement ---
    if agents_executed > 1:
        ca_score = cross_agent_agreement
        if conflicts_detected > 0:
            ca_explanation = f"{conflicts_detected} conflict(s) detected, {conflicts_resolved} resolved"
            if conflicts_detected > conflicts_resolved:
                ca_score = max(0.3, ca_score - 0.2)
        else:
            ca_explanation = "All agents produced consistent outputs"
    else:
        ca_score = 1.0
        ca_explanation = "Single agent — no cross-validation needed"

    factors.append(TrustFactor(
        name="Cross-Agent Agreement",
        score=ca_score,
        weight=0.15,
        explanation=ca_explanation,
        severity="info" if ca_score >= 0.7 else "warning",
    ))

    # --- 7. Memory Quality ---
    if execution_memory_decisions > 0 or execution_memory_facts > 0:
        m_score = min(1.0, 0.6 + (execution_memory_decisions * 0.1) + (execution_memory_facts * 0.05))
        m_explanation = f"Shared context: {execution_memory_decisions} decisions, {execution_memory_facts} facts"
    elif is_simple_chat:
        m_score = 1.0
        m_explanation = "Simple task — no shared memory required"
    else:
        m_score = 0.5
        m_explanation = "No shared context was built between agents"

    factors.append(TrustFactor(
        name="Memory Quality",
        score=m_score,
        weight=0.10,
        explanation=m_explanation,
    ))

    # --- Calculate Overall ---
    weighted_sum = sum(f.score * f.weight for f in factors)
    total_weight = sum(f.weight for f in factors)
    normalized = weighted_sum / total_weight if total_weight > 0 else 0.5
    overall = min(100, max(0, int(normalized * 100)))

    # Simple chat bonus
    if is_simple_chat:
        overall = max(overall, 90)

    # Generate summary and recommendation
    if overall >= 85:
        summary = "High trust — all systems performed well"
        recommendation = "high_trust"
    elif overall >= 65:
        summary = "Good trust — minor issues detected but answer is reliable"
        recommendation = "moderate_trust"
    elif overall >= 40:
        summary = "Moderate trust — some concerns, review recommended"
        recommendation = "low_trust"
    else:
        summary = "Low trust — significant issues detected, manual review required"
        recommendation = "review_required"

    return TrustAssessment(
        overall_confidence=overall,
        trust_factors=factors,
        summary=summary,
        agent_contributions=contributions,
        recommendation=recommendation,
    )
