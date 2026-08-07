"""
sevens Model Router

Dynamically selects the BEST model for each agent by querying the Model Registry.

Never hardcodes model names. Asks:
    best_models("coding")
instead of:
    return "deepseek-chat"

Supports:
- Multi-model selection (picks ranked list, not just one)
- Provider-priority failover: OpenRouter → Gemini → Groq
- Cost optimization
- Capability-based matching
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .model_registry import ModelSpec, best_models, get_model
from .agent_selector import SelectedAgent


PROVIDER_PRIORITY = ["openrouter", "gemini", "groq", "ollama"]


@dataclass
class ModelAssignment:
    """Model assignment for a specific agent."""
    agent_name: str
    primary: ModelSpec                  # Best model
    fallbacks: list[ModelSpec]          # Ordered fallback chain
    reason: str                        # Why this model was selected


@dataclass
class TeamModelAssignment:
    """Model assignments for the entire agent team."""
    assignments: list[ModelAssignment]
    total_estimated_cost: float         # Rough cost estimate for the full run
    providers_used: list[str]           # Unique providers in use


def assign_models(agents: list[SelectedAgent]) -> TeamModelAssignment:
    """
    For each agent in the team, dynamically select the best model
    based on the agent's preferred_model_capability.

    Returns a ranked list of models per agent (primary + fallbacks),
    following provider priority: OpenRouter → Gemini → Groq.
    """
    assignments: list[ModelAssignment] = []
    providers_used: set[str] = set()
    total_cost = 0.0

    for selected in agents:
        agent = selected.agent
        capability = agent.preferred_model_capability

        # Get all models for this capability, ranked by quality
        all_candidates = best_models(capability, limit=10)

        if not all_candidates:
            # Fallback: try "coding" as a universal capability
            all_candidates = best_models("coding", limit=10)

        # Apply provider priority ordering
        ordered = _order_by_provider_priority(all_candidates)

        if not ordered:
            # Absolute fallback — should never happen if registry is populated
            continue

        primary = ordered[0]
        fallbacks = ordered[1:4]  # Top 3 fallbacks

        providers_used.add(primary.provider)
        total_cost += primary.cost_per_1m_input * 0.01  # Rough per-task estimate

        reason = (
            f"Best {capability} model: {primary.name} "
            f"(quality={primary.quality_tier}, cost=${primary.cost_per_1m_input}/1M, "
            f"provider={primary.provider})"
        )

        assignments.append(ModelAssignment(
            agent_name=agent.name,
            primary=primary,
            fallbacks=fallbacks,
            reason=reason,
        ))

    return TeamModelAssignment(
        assignments=assignments,
        total_estimated_cost=round(total_cost, 4),
        providers_used=sorted(providers_used),
    )


def _order_by_provider_priority(models: list[ModelSpec]) -> list[ModelSpec]:
    """
    Re-order models by provider priority while preserving quality ranking
    within each provider group.
    For OpenRouter specifically, prioritize paid-trial models over free models.
    """
    buckets: dict[str, list[ModelSpec]] = {p: [] for p in PROVIDER_PRIORITY}
    other: list[ModelSpec] = []

    for m in models:
        if m.provider in buckets:
            buckets[m.provider].append(m)
        else:
            other.append(m)

    result: list[ModelSpec] = []
    
    # Sort OpenRouter bucket specifically by tier
    if buckets.get("openrouter"):
        # Map tier to sort order (lower is better):
        # 1. paid-trial
        # 2. standard-paid
        # 3. free
        def _tier_sort_key(m: ModelSpec) -> tuple[int, int, float]:
            tier_order = {"paid-trial": 0, "standard-paid": 1, "free": 2}
            return (tier_order.get(getattr(m, "tier", "standard-paid"), 1), -m.quality_tier, m.cost_per_1m_input)
            
        buckets["openrouter"].sort(key=_tier_sort_key)

    for provider in PROVIDER_PRIORITY:
        result.extend(buckets[provider])
    result.extend(other)

    return result
