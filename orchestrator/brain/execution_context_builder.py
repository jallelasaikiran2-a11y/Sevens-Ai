"""
sevens Execution Context Builder — V3

Sits between the Registries and the Execution Graph Builder.

After the Capability Resolver has determined which agents, models, and tools
are needed, the Execution Context Builder prepares the complete runtime
environment for the DAG:

1. Resolves each agent type to a concrete AgentSpec from the Agent Registry.
2. Assigns the best available model per agent from the Model Registry.
3. Resolves abstract tool types to concrete ToolSpecs from the Tool Registry.
4. Initializes a fresh ExecutionMemory for the request.
5. Injects Conversation Memory context (if available).
6. Packages everything into an ExecutionContext object that the DAG Builder
   and Execution Engine consume.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .capability_resolver import ResolvedRequirements, AGENT_DEPENDENCIES, get_agent_read_namespaces
from .agent_registry import get_agent, AgentSpec
from .model_registry import get_model, best_models, ModelSpec
from .tool_registry import resolve_tools, ToolSpec
from .memory_manager import ExecutionMemory, ConversationMemory


@dataclass
class AgentAssignment:
    """A fully resolved agent with its model and tools."""
    agent_name: str
    agent_spec: AgentSpec
    model_spec: ModelSpec
    model_capability: str       # what capability was requested
    tools: list[ToolSpec]       # tools available to this agent
    stage_order: int = 0        # execution order within the DAG
    depends_on: list[str] = field(default_factory=list)   # V4.1: explicit dependency edges
    read_namespaces: list[str] = field(default_factory=list)  # V4.1: memory namespaces to inject


@dataclass
class ExecutionContext:
    """
    The complete runtime context for a single orchestration request.
    Consumed by the DAG Builder and Execution Engine.
    """
    task: str
    intent: str
    complexity: int
    assignments: list[AgentAssignment]
    parallel_groups: list[list[str]]     # groups of agent names
    execution_memory: ExecutionMemory
    conversation_context: str            # serialized conversation history
    all_tools: list[ToolSpec]
    requires_verification: bool = True
    requires_humanization: bool = True
    planning_path: str = "primary"


def build_execution_context(
    task: str,
    intent: str,
    complexity: int,
    requirements: ResolvedRequirements,
    conversation_memory: ConversationMemory | None = None,
    planning_path: str = "primary",
) -> ExecutionContext:
    """
    Build the full execution context from resolved requirements.

    This is the bridge between planning and execution:
    - Planner decides WHAT is needed (capabilities)
    - Capability Resolver decides WHO is needed (agent types, model caps)
    - This function resolves HOW to execute (concrete agents, models, tools)
    """
    assignments: list[AgentAssignment] = []
    
    # Track provider usage in this request for load balancing
    used_providers: dict[str, int] = {}

    for agent_type in requirements.agent_types:
        # 1. Resolve agent from registry
        agent_spec = get_agent(agent_type)
        if not agent_spec:
            print(f"[CONTEXT BUILDER WARN] Agent '{agent_type}' not in registry, skipping")
            continue

        # 2. Determine what model capability this agent needs
        model_cap = requirements.model_capabilities.get(agent_type, "general")

        # 3. Find the best available model for that capability, balancing providers
        model_spec = _select_best_model(model_cap, used_providers)
        if not model_spec:
            print(f"[CONTEXT BUILDER WARN] No model for capability '{model_cap}', using fallback")
            model_spec = get_model("llama-3.3-70b-versatile")
            if not model_spec:
                # Absolute last resort — skip this agent
                print(f"[CONTEXT BUILDER ERROR] No fallback model available, skipping {agent_type}")
                continue

        # 4. Resolve tools for this agent's capabilities
        agent_tools = resolve_tools(requirements.tool_types)

        # 5. Determine stage order from parallel groups
        stage_order = 0
        for i, group in enumerate(requirements.parallel_groups):
            if agent_type in group:
                stage_order = i
                break

        # 6. V4.1: Resolve dependencies and namespace access
        #    Filter depends_on to only include agents that are actually in this request.
        all_requested = set(requirements.agent_types)
        raw_deps = AGENT_DEPENDENCIES.get(agent_type, [])
        active_deps = [d for d in raw_deps if d in all_requested]

        read_ns = get_agent_read_namespaces(agent_type)

        assignments.append(AgentAssignment(
            agent_name=agent_type,
            agent_spec=agent_spec,
            model_spec=model_spec,
            model_capability=model_cap,
            tools=agent_tools,
            stage_order=stage_order,
            depends_on=active_deps,
            read_namespaces=read_ns,
        ))

    # Initialize execution memory
    execution_memory = ExecutionMemory()

    # Inject conversation context if available
    conversation_context = ""
    if conversation_memory:
        conversation_context = conversation_memory.get_recent_context(max_turns=5)

    # Resolve all unique tools
    all_tools = resolve_tools(requirements.tool_types)

    return ExecutionContext(
        task=task,
        intent=intent,
        complexity=complexity,
        assignments=assignments,
        parallel_groups=requirements.parallel_groups,
        execution_memory=execution_memory,
        conversation_context=conversation_context,
        all_tools=all_tools,
        requires_verification=requirements.requires_verification,
        requires_humanization=requirements.requires_humanization,
        planning_path=planning_path,
    )


def _select_best_model(capability: str, used_providers: dict[str, int]) -> ModelSpec | None:
    """
    Select the best available model for a given capability, distributing load
    across providers to prevent rate limits (e.g., 429 Too Many Requests).
    """
    candidates = best_models(capability, limit=5)
    
    if not candidates:
        # Broaden: try "coding" as universal fallback
        candidates = best_models("coding", limit=5)
        
    if not candidates:
        return get_model("llama-3.3-70b-versatile")
        
    # Sort candidates to prefer providers with lower current usage in this request,
    # while still respecting quality tier. We heavily penalize providers already used
    # to enforce load balancing across the agent swarm.
    candidates.sort(key=lambda m: (used_providers.get(m.provider, 0), -m.quality_tier, m.cost_per_1m_input))
    
    selected = candidates[0]
    used_providers[selected.provider] = used_providers.get(selected.provider, 0) + 1
    return selected
