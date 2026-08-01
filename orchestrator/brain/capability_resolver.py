"""
VEXORA Capability Resolver — V3

Sits between the Planner and the Registries.

The Planner outputs raw capabilities (e.g., ["architecture", "backend", "security"]).
The Capability Resolver translates those into:

    Required Skills     → what competencies are needed
    Required Agent Types → which agent roles to query from AgentRegistry
    Required Tool Types  → which tools to query from ToolRegistry
    Required Model Caps  → what model capabilities to query from ModelRegistry

This decouples the Planner from knowing about specific agents, models, or tools.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ResolvedRequirements:
    """Output of the Capability Resolver."""
    skills: list[str]                          # e.g. ["system_design", "api_development"]
    agent_types: list[str]                     # e.g. ["architect", "backend-dev"]
    tool_types: list[str]                      # e.g. ["web_search", "filesystem_read"]
    model_capabilities: dict[str, str]         # agent_type → required model cap (e.g. "architect" → "reasoning")
    parallel_groups: list[list[str]]           # suggested parallelism
    requires_verification: bool = True
    requires_humanization: bool = True


# =============================================================================
# Capability → Skill mapping
# =============================================================================

CAPABILITY_SKILLS: dict[str, list[str]] = {
    "architecture":  ["system_design", "schema_design", "component_layout"],
    "backend":       ["api_development", "server_logic", "database_queries"],
    "frontend":      ["ui_development", "component_design", "styling"],
    "database":      ["schema_design", "query_optimization", "migration"],
    "security":      ["threat_modeling", "auth_design", "vulnerability_analysis"],
    "testing":       ["test_strategy", "test_implementation", "coverage_planning"],
    "devops":        ["containerization", "ci_cd", "deployment"],
    "documentation": ["technical_writing", "api_docs"],
    "ml":            ["model_training", "data_pipeline", "inference"],
    "mobile":        ["mobile_ui", "native_integration"],
    "performance":   ["profiling", "optimization", "caching"],
    "refactoring":   ["code_cleanup", "pattern_application", "debt_reduction"],
    "research":      ["information_retrieval", "comparison", "evidence_gathering"],
    "review":        ["code_review", "quality_assessment"],
    "reasoning":     ["analysis", "explanation", "step_by_step"],
    "conversation":  ["natural_language", "greeting"],
}


# =============================================================================
# Capability → Agent Type mapping
# =============================================================================

CAPABILITY_AGENTS: dict[str, list[str]] = {
    "architecture":  ["architect"],
    "backend":       ["backend-dev"],
    "frontend":      ["frontend-dev"],
    "database":      ["architect", "backend-dev"],
    "security":      ["security-architect", "security-auditor"],
    "testing":       ["test-architect", "tester"],
    "devops":        ["devops-engineer"],
    "documentation": ["documenter"],
    "ml":            ["ml-dev"],
    "mobile":        ["mobile-dev"],
    "performance":   ["performance-engineer"],
    "refactoring":   ["coder"],
    "research":      ["researcher"],
    "review":        ["reviewer"],
    "reasoning":     ["reasoning"],
    "conversation":  ["conversation"],
}


# =============================================================================
# Capability → Tool Type mapping
# =============================================================================

CAPABILITY_TOOLS: dict[str, list[str]] = {
    "architecture":  ["filesystem_read", "filesystem_search"],
    "backend":       ["filesystem_read", "filesystem_write", "terminal_exec"],
    "frontend":      ["filesystem_read", "filesystem_write", "terminal_exec"],
    "database":      ["filesystem_read", "filesystem_write", "terminal_exec"],
    "security":      ["filesystem_read", "filesystem_search", "terminal_exec"],
    "testing":       ["filesystem_read", "filesystem_write", "terminal_exec"],
    "devops":        ["filesystem_read", "filesystem_write", "terminal_exec"],
    "documentation": ["filesystem_read", "filesystem_write"],
    "ml":            ["filesystem_read", "filesystem_write", "terminal_exec"],
    "mobile":        ["filesystem_read", "filesystem_write", "terminal_exec"],
    "performance":   ["filesystem_read", "terminal_exec"],
    "refactoring":   ["filesystem_read", "filesystem_write", "filesystem_search"],
    "research":      ["web_search"],
    "review":        ["filesystem_read", "filesystem_search"],
    "reasoning":     [],
    "conversation":  [],
}


# =============================================================================
# Agent Type → Model Capability mapping
# =============================================================================

AGENT_MODEL_CAPABILITY: dict[str, str] = {
    "architect":            "reasoning",
    "core-architect":       "reasoning",
    "security-architect":   "reasoning",
    "test-architect":       "reasoning",
    "backend-dev":          "coding",
    "frontend-dev":         "coding",
    "mobile-dev":           "coding",
    "ml-dev":               "coding",
    "coder":                "coding",
    "reviewer":             "reasoning",
    "tester":               "coding",
    "security-auditor":     "reasoning",
    "performance-engineer": "reasoning",
    "devops-engineer":      "coding",
    "researcher":           "research",
    "documenter":           "writing",
    "reasoning":            "reasoning",
    "conversation":         "general",
}


# =============================================================================
# Dependency Graph — V4.1 (replaces flat EXECUTION_ORDER)
# =============================================================================

# Each agent declares which other agents it depends on.
# The scheduler launches an agent the moment ALL its dependencies are satisfied.
AGENT_DEPENDENCIES: dict[str, list[str]] = {
    "architect":            [],
    "core-architect":       [],
    "security-architect":   [],
    "researcher":           [],
    "reasoning":            [],
    "conversation":         [],
    "backend-dev":          ["architect"],
    "frontend-dev":         ["architect"],
    "mobile-dev":           ["architect"],
    "ml-dev":               ["architect"],
    "coder":                ["architect"],
    "devops-engineer":      ["architect"],
    "documenter":           ["architect"],
    "performance-engineer": ["backend-dev"],
    "tester":               ["backend-dev"],
    "security-auditor":     ["backend-dev"],
    "reviewer":             ["backend-dev", "frontend-dev"],
    "test-architect":       ["backend-dev"],
}

# Back-compat: derive integer order from the dependency graph for any code
# that still reads EXECUTION_ORDER (e.g. _build_dag_from_context).
def _depth(agent: str, _cache: dict[str, int] = {}) -> int:
    if agent in _cache:
        return _cache[agent]
    deps = AGENT_DEPENDENCIES.get(agent, [])
    d = 0 if not deps else max(_depth(d) for d in deps) + 1
    _cache[agent] = d
    return d

EXECUTION_ORDER: dict[str, int] = {a: _depth(a) for a in AGENT_DEPENDENCIES}


# =============================================================================
# Namespace Access Matrix — V4.1
# =============================================================================
# Defines which memory namespaces each agent is allowed to READ and WRITE.
# The scheduler uses this to inject only the relevant memory slices.

AGENT_NAMESPACE_ACCESS: dict[str, dict[str, list[str]]] = {
    "architect": {
        "reads":  ["facts"],
        "writes": ["architecture", "api_contracts", "facts"],
    },
    "core-architect": {
        "reads":  ["facts"],
        "writes": ["architecture", "facts"],
    },
    "security-architect": {
        "reads":  ["facts", "architecture"],
        "writes": ["security", "facts"],
    },
    "researcher": {
        "reads":  ["facts"],
        "writes": ["research", "facts"],
    },
    "reasoning": {
        "reads":  ["facts"],
        "writes": ["facts"],
    },
    "conversation": {
        "reads":  [],
        "writes": [],
    },
    "backend-dev": {
        "reads":  ["architecture", "api_contracts", "facts"],
        "writes": ["deliverables", "facts"],
    },
    "frontend-dev": {
        "reads":  ["architecture", "api_contracts"],
        "writes": ["deliverables"],
    },
    "mobile-dev": {
        "reads":  ["architecture", "api_contracts"],
        "writes": ["deliverables"],
    },
    "ml-dev": {
        "reads":  ["architecture", "facts", "research"],
        "writes": ["deliverables", "facts"],
    },
    "coder": {
        "reads":  ["architecture", "api_contracts", "facts"],
        "writes": ["deliverables"],
    },
    "devops-engineer": {
        "reads":  ["architecture", "deliverables"],
        "writes": ["deliverables"],
    },
    "documenter": {
        "reads":  ["architecture", "deliverables", "api_contracts"],
        "writes": ["deliverables"],
    },
    "performance-engineer": {
        "reads":  ["deliverables", "architecture"],
        "writes": ["performance"],
    },
    "tester": {
        "reads":  ["deliverables", "api_contracts"],
        "writes": ["testing"],
    },
    "security-auditor": {
        "reads":  ["architecture", "deliverables", "facts"],
        "writes": ["security"],
    },
    "reviewer": {
        "reads":  ["architecture", "deliverables", "security", "testing"],
        "writes": ["facts"],
    },
    "test-architect": {
        "reads":  ["architecture", "deliverables", "testing"],
        "writes": ["testing"],
    },
}

def get_agent_read_namespaces(agent_type: str) -> list[str]:
    """Return the memory namespaces an agent is allowed to read."""
    access = AGENT_NAMESPACE_ACCESS.get(agent_type)
    if not access:
        return ["facts"]  # safe default
    return access["reads"]

def get_agent_write_namespaces(agent_type: str) -> list[str]:
    """Return the memory namespaces an agent is allowed to write."""
    access = AGENT_NAMESPACE_ACCESS.get(agent_type)
    if not access:
        return ["facts"]
    return access["writes"]


# =============================================================================
# Main Resolver
# =============================================================================

def resolve_capabilities(
    capabilities: list[str],
    complexity: int = 2,
) -> ResolvedRequirements:
    """
    Translate raw planner capabilities into concrete requirements.

    Args:
        capabilities: List of capability strings from the planner.
        complexity: 0-4 complexity level.

    Returns:
        ResolvedRequirements with skills, agent types, tools, and model caps.
    """
    all_skills: list[str] = []
    all_agent_types: list[str] = []
    all_tool_types: set[str] = set()
    model_caps: dict[str, str] = {}

    for cap in capabilities:
        # Skills
        skills = CAPABILITY_SKILLS.get(cap, [cap])
        all_skills.extend(s for s in skills if s not in all_skills)

        # Agent types
        agents = CAPABILITY_AGENTS.get(cap, ["coder"])
        for agent in agents:
            if agent not in all_agent_types:
                all_agent_types.append(agent)

        # Tools
        tools = CAPABILITY_TOOLS.get(cap, [])
        all_tool_types.update(tools)

    # Map each agent type to its required model capability
    for agent_type in all_agent_types:
        model_caps[agent_type] = AGENT_MODEL_CAPABILITY.get(agent_type, "general")

    # Add reviewer for complex tasks
    if complexity >= 2 and "reviewer" not in all_agent_types and "conversation" not in all_agent_types:
        all_agent_types.append("reviewer")
        model_caps["reviewer"] = "reasoning"

    # Build parallel groups based on execution order
    groups: dict[int, list[str]] = {}
    for agent_type in all_agent_types:
        order = EXECUTION_ORDER.get(agent_type, 1)
        if order not in groups:
            groups[order] = []
        groups[order].append(agent_type)

    parallel_groups = [groups[k] for k in sorted(groups.keys())]

    # Simple tasks don't need verification or humanization
    is_simple = complexity <= 1 and len(all_agent_types) <= 1
    requires_verification = not is_simple
    requires_humanization = not is_simple

    return ResolvedRequirements(
        skills=all_skills,
        agent_types=all_agent_types,
        tool_types=sorted(all_tool_types),
        model_capabilities=model_caps,
        parallel_groups=parallel_groups,
        requires_verification=requires_verification,
        requires_humanization=requires_humanization,
    )
