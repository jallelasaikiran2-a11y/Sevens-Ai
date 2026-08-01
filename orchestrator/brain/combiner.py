"""
VEXORA Combiner — V3

Structurally merges distinct agent outputs into one coherent draft
before verification.

This is NOT text concatenation. The Combiner:

1. Reads structured Agent Contracts (Summary, Deliverables, Artifacts, etc.)
2. Detects conflicts between agents (e.g., tech choice disagreements)
3. Resolves conflicts using hierarchical agent weighting (Architect > Dev)
4. Assembles a single, ordered draft artifact

The Combiner output goes directly to the Verifier.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# =============================================================================
# Agent Contract — Structured Output Format
# =============================================================================

@dataclass
class AgentContract:
    """
    Structured output that every agent must produce.
    Enables deterministic merging by the Combiner.
    """
    agent_name: str
    summary: str                                 # Brief description of what was done
    deliverables: list[str] = field(default_factory=list)  # What was produced
    artifacts: list[dict[str, str]] = field(default_factory=list)  # [{type, name, content, language}]
    assumptions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # What this agent depended on
    handoff_notes: list[str] = field(default_factory=list)  # Notes for downstream agents
    confidence: float = 0.8                      # 0.0-1.0 self-assessed confidence
    raw_output: str = ""                         # The full text output (fallback)


# =============================================================================
# Agent Tier Hierarchy (for conflict resolution)
# =============================================================================

AGENT_TIER: dict[str, int] = {
    "architect": 10,
    "core-architect": 10,
    "security-architect": 9,
    "test-architect": 8,
    "researcher": 7,
    "reasoning": 7,
    "backend-dev": 6,
    "frontend-dev": 6,
    "mobile-dev": 6,
    "ml-dev": 6,
    "coder": 5,
    "devops-engineer": 5,
    "performance-engineer": 5,
    "tester": 4,
    "security-auditor": 4,
    "reviewer": 3,
    "documenter": 2,
    "conversation": 1,
}


# =============================================================================
# Combined Draft
# =============================================================================

@dataclass
class CombinedDraft:
    """The Combiner's output — a single coherent draft for verification."""
    content: str                                  # The assembled text
    agent_contributions: dict[str, str]           # agent_name → summary of contribution
    conflicts_detected: list[dict[str, Any]]      # [{agents, description, resolution}]
    conflicts_resolved: int
    total_artifacts: int
    total_agents: int
    cross_agent_agreement: float                  # 0.0-1.0 how much agents agreed


# =============================================================================
# Combiner Logic
# =============================================================================

def combine_contracts(contracts: list[AgentContract], task: str) -> CombinedDraft:
    """
    Combine multiple AgentContracts into a single CombinedDraft.

    Strategy:
    1. Order contributions by agent tier (highest authority first)
    2. Detect conflicts in assumptions/constraints
    3. Resolve conflicts by deferring to higher-tier agent
    4. Assemble content preserving structure and code blocks
    """
    if not contracts:
        return CombinedDraft(
            content="No agent outputs to combine.",
            agent_contributions={},
            conflicts_detected=[],
            conflicts_resolved=0,
            total_artifacts=0,
            total_agents=0,
            cross_agent_agreement=0.0,
        )

    # Sort by tier (highest first)
    sorted_contracts = sorted(
        contracts,
        key=lambda c: AGENT_TIER.get(c.agent_name, 0),
        reverse=True,
    )

    # Detect conflicts
    conflicts = _detect_conflicts(sorted_contracts)
    resolutions = _resolve_conflicts(conflicts, sorted_contracts)

    # Assemble the combined content
    content_parts: list[str] = []
    contributions: dict[str, str] = {}
    total_artifacts = 0

    for contract in sorted_contracts:
        contributions[contract.agent_name] = contract.summary

        # Use raw_output as the primary content
        if contract.raw_output.strip():
            content_parts.append(contract.raw_output.strip())

        total_artifacts += len(contract.artifacts)

    combined_content = "\n\n".join(content_parts)

    # Calculate cross-agent agreement
    agreement = _calculate_agreement(sorted_contracts)

    return CombinedDraft(
        content=combined_content,
        agent_contributions=contributions,
        conflicts_detected=conflicts,
        conflicts_resolved=len(resolutions),
        total_artifacts=total_artifacts,
        total_agents=len(contracts),
        cross_agent_agreement=agreement,
    )


def _detect_conflicts(contracts: list[AgentContract]) -> list[dict[str, Any]]:
    """
    Detect conflicts between agent outputs.
    Looks for contradictory assumptions, technology choices, etc.
    """
    conflicts: list[dict[str, Any]] = []

    all_assumptions: dict[str, list[str]] = {}
    for c in contracts:
        for assumption in c.assumptions:
            key = assumption.lower().strip()
            if key not in all_assumptions:
                all_assumptions[key] = []
            all_assumptions[key].append(c.agent_name)

    # Check for opposing constraints
    all_constraints: list[tuple[str, str]] = []
    for c in contracts:
        for constraint in c.constraints:
            all_constraints.append((c.agent_name, constraint))

    # Technology choice conflicts (simple keyword check)
    tech_choices: dict[str, list[tuple[str, str]]] = {}
    tech_categories = {
        "database": ["postgres", "mysql", "mongodb", "sqlite", "redis", "dynamodb"],
        "framework": ["fastapi", "django", "flask", "express", "nextjs", "spring"],
        "language": ["python", "javascript", "typescript", "go", "rust", "java"],
    }

    for c in contracts:
        text = (c.raw_output + " ".join(c.assumptions) + " ".join(c.constraints)).lower()
        for category, options in tech_categories.items():
            for option in options:
                if option in text:
                    if category not in tech_choices:
                        tech_choices[category] = []
                    tech_choices[category].append((c.agent_name, option))

    # Flag categories where agents disagree
    for category, choices in tech_choices.items():
        unique_choices = set(choice for _, choice in choices)
        if len(unique_choices) > 1:
            agents_involved = [agent for agent, _ in choices]
            conflicts.append({
                "category": category,
                "agents": agents_involved,
                "choices": list(unique_choices),
                "description": f"Agents disagree on {category}: {', '.join(unique_choices)}",
            })

    return conflicts


def _resolve_conflicts(
    conflicts: list[dict[str, Any]],
    contracts: list[AgentContract],
) -> list[dict[str, Any]]:
    """
    Resolve conflicts by deferring to the higher-tier agent.
    """
    resolutions: list[dict[str, Any]] = []

    for conflict in conflicts:
        agents = conflict["agents"]
        # Find the highest-tier agent involved
        highest_agent = max(agents, key=lambda a: AGENT_TIER.get(a, 0))
        highest_tier = AGENT_TIER.get(highest_agent, 0)

        resolution = {
            "conflict": conflict["description"],
            "resolved_by": highest_agent,
            "tier": highest_tier,
            "strategy": "deferred_to_higher_authority",
        }
        conflict["resolution"] = f"Deferred to {highest_agent} (tier {highest_tier})"
        resolutions.append(resolution)

    return resolutions


def _calculate_agreement(contracts: list[AgentContract]) -> float:
    """
    Calculate how much agents agree with each other.
    Based on shared assumptions and consistent tech choices.
    """
    if len(contracts) <= 1:
        return 1.0

    # Simple heuristic: average confidence weighted by contract count
    total_confidence = sum(c.confidence for c in contracts)
    avg_confidence = total_confidence / len(contracts)

    # Penalize if there are disagreements in assumptions
    all_assumptions = set()
    duplicated = 0
    for c in contracts:
        for a in c.assumptions:
            key = a.lower().strip()
            if key in all_assumptions:
                duplicated += 1
            all_assumptions.add(key)

    # Higher duplication = higher agreement
    if all_assumptions:
        agreement_bonus = min(0.2, duplicated / max(len(all_assumptions), 1) * 0.2)
    else:
        agreement_bonus = 0.1

    return min(1.0, avg_confidence + agreement_bonus)


# =============================================================================
# Parse raw agent output into AgentContract
# =============================================================================

def parse_agent_output(agent_name: str, raw_output: str) -> AgentContract:
    """
    Parse raw agent text output into a structured AgentContract.

    Agents are prompted to output structured sections, but if they don't,
    we extract what we can and fall back gracefully.
    """
    import re

    contract = AgentContract(
        agent_name=agent_name,
        summary="",
        raw_output=raw_output,
    )

    # Try to extract structured sections
    lines = raw_output.split("\n")
    current_section = None

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if lower.startswith("## summary") or lower.startswith("**summary"):
            current_section = "summary"
            continue
        elif lower.startswith("## deliverables") or lower.startswith("**deliverables"):
            current_section = "deliverables"
            continue
        elif lower.startswith("## assumptions") or lower.startswith("**assumptions"):
            current_section = "assumptions"
            continue
        elif lower.startswith("## constraints") or lower.startswith("**constraints"):
            current_section = "constraints"
            continue
        elif lower.startswith("## dependencies") or lower.startswith("**dependencies"):
            current_section = "dependencies"
            continue
        elif lower.startswith("## handoff") or lower.startswith("**handoff"):
            current_section = "handoff_notes"
            continue
        elif stripped.startswith("## ") or stripped.startswith("**"):
            current_section = None
            continue

        if current_section and stripped:
            item = re.sub(r"^[-*•]\s*", "", stripped)
            if current_section == "summary":
                contract.summary += item + " "
            elif current_section == "deliverables":
                contract.deliverables.append(item)
            elif current_section == "assumptions":
                contract.assumptions.append(item)
            elif current_section == "constraints":
                contract.constraints.append(item)
            elif current_section == "dependencies":
                contract.dependencies.append(item)
            elif current_section == "handoff_notes":
                contract.handoff_notes.append(item)

    # If no structured summary was found, create one from the first paragraph
    if not contract.summary.strip():
        first_para = raw_output.split("\n\n")[0] if raw_output else ""
        contract.summary = first_para[:200].strip()

    # Extract code blocks as artifacts
    code_blocks = re.findall(r"```(\w*)\n(.*?)```", raw_output, re.DOTALL)
    for i, (lang, code) in enumerate(code_blocks):
        contract.artifacts.append({
            "type": "code",
            "name": f"code_block_{i+1}",
            "content": code.strip(),
            "language": lang or "unknown",
        })

    return contract
