"""
VEXORA Agent Selector

Matches capabilities → agents via the Agent Registry.

Flow:
    CapabilityAnalysis.capabilities
        → Agent Registry lookup
            → Deduplicated, minimal team
                → Ordered by dependency

Never hardcodes agent names. Never activates unnecessary agents.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .capability_analyzer import CapabilityAnalysis
from .agent_registry import AgentSpec, find_agents_for_capability, get_agent


@dataclass
class SelectedAgent:
    """An agent selected for execution with its role assignment."""
    agent: AgentSpec
    assigned_capability: str          # Primary capability this agent covers
    role_description: str             # What it will do in this specific task
    dependencies: list[str] = field(default_factory=list)  # Agent names it depends on
    stage: int = 0                    # Execution stage (0 = first)


@dataclass
class AgentTeam:
    """The minimal effective team of agents selected for a task."""
    agents: list[SelectedAgent]
    total_count: int
    capabilities_covered: list[str]
    capabilities_uncovered: list[str]


# =============================================================================
# Capability → Stage mapping (defines execution order)
# =============================================================================

CAPABILITY_STAGE_ORDER = {
    "architecture":  0,
    "research":      0,
    "database":      1,
    "backend":       1,
    "frontend":      1,
    "mobile":        1,
    "ml":            1,
    "devops":        2,
    "security":      2,
    "performance":   2,
    "review":        3,
    "refactoring":   3,
    "testing":       4,
    "documentation": 5,
}

# Which capability depends on which
CAPABILITY_DEPENDENCIES = {
    "backend":       ["architecture"],
    "frontend":      ["architecture"],
    "mobile":        ["architecture"],
    "database":      ["architecture"],
    "ml":            ["architecture"],
    "security":      ["backend", "frontend"],
    "review":        ["backend", "frontend"],
    "testing":       ["backend", "frontend", "review"],
    "performance":   ["backend", "frontend"],
    "devops":        ["backend", "testing"],
    "documentation": ["backend", "frontend", "testing"],
    "refactoring":   ["review"],
}


def select_agents(analysis: CapabilityAnalysis) -> AgentTeam:
    """
    Select the minimal effective agent team based on capability analysis.

    Rules:
    1. For each capability, pick the BEST single agent (highest tier that matches).
    2. Deduplicate — if one agent covers multiple capabilities, don't duplicate.
    3. For Low complexity, collapse to minimum viable team.
    4. Always include verifier + humanizer for High/Critical.
    """
    capabilities = analysis.capabilities
    complexity = analysis.complexity
    selected: dict[str, SelectedAgent] = {}  # agent_name → SelectedAgent
    covered: list[str] = []
    uncovered: list[str] = []

    for cap in capabilities:
        candidates = find_agents_for_capability(cap)
        if not candidates:
            uncovered.append(cap)
            continue

        # Pick the best agent for this capability
        # Prefer: agents not already selected (to diversify), then highest tier
        already_selected_names = set(selected.keys())
        fresh = [a for a in candidates if a.name not in already_selected_names]
        pool = fresh if fresh else candidates

        # Sort by tier descending (best first)
        pool.sort(key=lambda a: -a.tier)
        best = pool[0]

        if best.name not in selected:
            # Determine dependencies
            deps = []
            for dep_cap in CAPABILITY_DEPENDENCIES.get(cap, []):
                if dep_cap in capabilities:
                    # Find which agent covers that dependency
                    for existing in selected.values():
                        if existing.assigned_capability == dep_cap:
                            deps.append(existing.agent.name)

            stage = CAPABILITY_STAGE_ORDER.get(cap, 1)

            selected[best.name] = SelectedAgent(
                agent=best,
                assigned_capability=cap,
                role_description=f"{best.display_name}: {best.description}",
                dependencies=deps,
                stage=stage,
            )
        covered.append(cap)

    # --- Complexity-based adjustments ---

    if complexity == "Low":
        # Collapse to at most 2 agents
        agents_list = sorted(selected.values(), key=lambda a: a.stage)
        if len(agents_list) > 2:
            selected = {a.agent.name: a for a in agents_list[:2]}

    elif complexity in ("High", "Critical") and analysis.requires_verification:
        # Ensure verifier is included
        if "verifier" not in selected:
            verifier = get_agent("verifier")
            if verifier:
                max_stage = max((a.stage for a in selected.values()), default=0)
                selected["verifier"] = SelectedAgent(
                    agent=verifier,
                    assigned_capability="review",
                    role_description="Verifies correctness, completeness, and quality",
                    dependencies=[a.agent.name for a in selected.values()],
                    stage=max_stage + 1,
                )

    # Always include humanizer if required
    if analysis.requires_humanization:
        humanizer = get_agent("humanizer")
        if humanizer:
            max_stage = max((a.stage for a in selected.values()), default=0)
            selected["humanizer"] = SelectedAgent(
                agent=humanizer,
                assigned_capability="documentation",
                role_description="Humanizes and formats the final output",
                dependencies=["verifier"] if "verifier" in selected else [a.agent.name for a in selected.values()],
                stage=max_stage + 1,
            )

    # Sort final list by stage
    agents_list = sorted(selected.values(), key=lambda a: a.stage)

    return AgentTeam(
        agents=agents_list,
        total_count=len(agents_list),
        capabilities_covered=covered,
        capabilities_uncovered=uncovered,
    )
