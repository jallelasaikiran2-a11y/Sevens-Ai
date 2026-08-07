"""
sevens DAG Builder

Constructs a Directed Acyclic Graph (DAG) from the selected agent team.
Parallelizes whenever possible. Respects dependency chains.

Example output:
    Stage 0: [architect]              ← sequential
    Stage 1: [backend-dev, frontend-dev]  ← parallel
    Stage 2: [reviewer, security-auditor] ← parallel
    Stage 3: [tester]                 ← sequential
    Stage 4: [verifier]               ← always runs
    Stage 5: [humanizer]              ← always last
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .agent_selector import SelectedAgent, AgentTeam
from .model_router import ModelAssignment, TeamModelAssignment


@dataclass
class DAGStage:
    """A single stage in the execution DAG."""
    stage_id: int
    name: str
    agents: list[str]                    # Agent names in this stage
    models: dict[str, str]               # agent_name → model_id
    parallel: bool                       # Can agents in this stage run in parallel?
    depends_on: list[int] = field(default_factory=list)  # Stage IDs this depends on


@dataclass
class ExecutionDAG:
    """The complete execution graph."""
    stages: list[DAGStage]
    total_stages: int
    total_agents: int
    has_parallel_stages: bool
    estimated_duration_seconds: int


# Stage name templates based on what agents are in the stage
STAGE_NAMES = {
    0: "Analysis & Architecture",
    1: "Implementation",
    2: "Quality & Security",
    3: "Review & Refactoring",
    4: "Testing",
    5: "Documentation",
    6: "Verification",
    7: "Humanization",
}


def build_dag(team: AgentTeam, model_assignments: TeamModelAssignment) -> ExecutionDAG:
    """
    Build an execution DAG from the agent team and model assignments.

    Groups agents by their stage number, determines parallelism,
    and links dependencies.
    """
    # Build model lookup: agent_name → model_id
    model_lookup: dict[str, str] = {}
    for assignment in model_assignments.assignments:
        model_lookup[assignment.agent_name] = assignment.primary.id

    # Group agents by stage
    stage_groups: dict[int, list[SelectedAgent]] = {}
    for agent in team.agents:
        stage_num = agent.stage
        if stage_num not in stage_groups:
            stage_groups[stage_num] = []
        stage_groups[stage_num].append(agent)

    # Build DAG stages
    stages: list[DAGStage] = []
    sorted_stage_nums = sorted(stage_groups.keys())

    for i, stage_num in enumerate(sorted_stage_nums):
        agents_in_stage = stage_groups[stage_num]
        agent_names = [a.agent.name for a in agents_in_stage]
        models_in_stage = {
            a.agent.name: model_lookup.get(a.agent.name, "unknown")
            for a in agents_in_stage
        }

        # Parallel if more than one agent in the stage
        parallel = len(agents_in_stage) > 1

        # Dependencies: this stage depends on all previous stages
        depends_on = [s.stage_id for s in stages] if stages else []

        # Generate a descriptive stage name
        if len(agents_in_stage) == 1:
            name = agents_in_stage[0].agent.display_name
        else:
            name = STAGE_NAMES.get(stage_num, f"Stage {stage_num}")

        stages.append(DAGStage(
            stage_id=i,
            name=name,
            agents=agent_names,
            models=models_in_stage,
            parallel=parallel,
            depends_on=[i - 1] if i > 0 else [],  # Linear dependency chain
        ))

    # Estimate duration: ~30s per sequential stage, parallel stages don't add
    sequential_count = sum(1 for s in stages if not s.parallel)
    parallel_count = sum(1 for s in stages if s.parallel)
    estimated_duration = (sequential_count * 30) + (parallel_count * 30)

    return ExecutionDAG(
        stages=stages,
        total_stages=len(stages),
        total_agents=team.total_count,
        has_parallel_stages=any(s.parallel for s in stages),
        estimated_duration_seconds=estimated_duration,
    )


def build_dag_from_plan(plan) -> ExecutionDAG:
    """
    Build an execution DAG directly from a Planner's ExecutionPlan.
    Uses the planner's parallel_groups to determine stage structure.
    """
    from .agent_registry import get_agent

    stages: list[DAGStage] = []

    for i, group in enumerate(plan.parallel_groups):
        # Build models map for this group
        models_in_stage = {}
        agent_names = []
        for agent_name in group:
            agent_names.append(agent_name)
            models_in_stage[agent_name] = plan.models.get(agent_name, "llama-3.3-70b-versatile")

        # Generate stage name
        if len(agent_names) == 1:
            spec = get_agent(agent_names[0])
            name = spec.display_name if spec else agent_names[0]
        else:
            name = STAGE_NAMES.get(i, f"Stage {i}")

        stages.append(DAGStage(
            stage_id=i,
            name=name,
            agents=agent_names,
            models=models_in_stage,
            parallel=len(agent_names) > 1,
            depends_on=[i - 1] if i > 0 else [],
        ))

    # Estimate duration
    sequential_count = sum(1 for s in stages if not s.parallel)
    parallel_count = sum(1 for s in stages if s.parallel)
    estimated_duration = (sequential_count * 30) + (parallel_count * 30)

    total_agents = sum(len(s.agents) for s in stages)

    return ExecutionDAG(
        stages=stages,
        total_stages=len(stages),
        total_agents=total_agents,
        has_parallel_stages=any(s.parallel for s in stages),
        estimated_duration_seconds=estimated_duration,
    )

