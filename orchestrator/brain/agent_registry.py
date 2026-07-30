"""
VEXORA Agent Registry

Every Ruflo agent registers its capabilities here.
Adding a new agent = adding one entry. Zero code changes elsewhere.

Flow:
    Capability → Registry → Agents

The Agent Selector queries this registry — it never hardcodes agent names.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class AgentSpec:
    """A single Ruflo specialized agent."""
    name: str                        # Ruflo agent name (e.g. "backend-dev")
    display_name: str                # Human-readable (e.g. "Backend Developer")
    capabilities: list[str]          # What this agent can do
    preferred_model_capability: str  # What model capability to look for (e.g. "coding")
    tier: int = 2                    # 1=fast/cheap, 2=balanced, 3=expert
    max_parallel: int = 1            # How many can run in parallel
    description: str = ""
    tags: list[str] = field(default_factory=list)


# =============================================================================
# THE REGISTRY — All Ruflo agents
# =============================================================================

AGENTS: dict[str, AgentSpec] = {}


def _register(spec: AgentSpec) -> None:
    AGENTS[spec.name] = spec


# ---------------------------------------------------------------------------
# General / Conversation agents
# ---------------------------------------------------------------------------

_register(AgentSpec(
    name="conversation",
    display_name="Conversation Agent",
    capabilities=["conversation"],
    preferred_model_capability="general",
    tier=1,
    description="Conversation Agent: Lightweight conversational response",
    tags=["chat", "basic"]
))

_register(AgentSpec(
    name="reasoning",
    display_name="Reasoning Agent",
    capabilities=["reasoning", "research", "analysis"],
    preferred_model_capability="reasoning",
    tier=2,
    description="Reasoning Agent: Clear explanations, step-by-step analysis",
    tags=["reasoning", "analysis"]
))

# ---------------------------------------------------------------------------
# Architecture / Design agents
# ---------------------------------------------------------------------------

_register(AgentSpec(
    name="architect",
    display_name="Architect",
    capabilities=["architecture", "database", "backend", "frontend"],
    preferred_model_capability="reasoning",
    tier=3,
    description="System & API architecture, schema design, technical decisions",
))

_register(AgentSpec(
    name="core-architect",
    display_name="Core Architect",
    capabilities=["architecture", "refactoring", "performance"],
    preferred_model_capability="reasoning",
    tier=3,
    description="Deep architectural analysis, core system design",
))

_register(AgentSpec(
    name="security-architect",
    display_name="Security Architect",
    capabilities=["security", "architecture"],
    preferred_model_capability="reasoning",
    tier=3,
    description="Threat modeling, security architecture, risk assessment",
))

_register(AgentSpec(
    name="test-architect",
    display_name="Test Architect",
    capabilities=["testing", "architecture"],
    preferred_model_capability="reasoning",
    tier=3,
    description="Test strategy, coverage planning, TDD architecture",
))

# ---------------------------------------------------------------------------
# Development agents
# ---------------------------------------------------------------------------

_register(AgentSpec(
    name="backend-dev",
    display_name="Backend Developer",
    capabilities=["backend", "database", "security"],
    preferred_model_capability="coding",
    tier=2,
    description="FastAPI, Django, Express, REST/GraphQL implementation",
))

_register(AgentSpec(
    name="frontend-dev",
    display_name="Frontend Developer",
    capabilities=["frontend"],
    preferred_model_capability="coding",
    tier=2,
    description="React, Vue, component implementation, UI/UX",
))

_register(AgentSpec(
    name="mobile-dev",
    display_name="Mobile Developer",
    capabilities=["mobile", "frontend"],
    preferred_model_capability="coding",
    tier=2,
    description="React Native, Flutter, iOS/Android development",
))

_register(AgentSpec(
    name="ml-dev",
    display_name="ML Developer",
    capabilities=["ml"],
    preferred_model_capability="reasoning",
    tier=3,
    description="Machine learning, model training, data pipelines",
))

_register(AgentSpec(
    name="coder",
    display_name="Coder",
    capabilities=["backend", "frontend", "refactoring", "performance"],
    preferred_model_capability="coding",
    tier=2,
    description="General-purpose implementation and coding",
))

# ---------------------------------------------------------------------------
# Quality / Review agents
# ---------------------------------------------------------------------------

_register(AgentSpec(
    name="reviewer",
    display_name="Reviewer",
    capabilities=["review", "security", "refactoring"],
    preferred_model_capability="coding",
    tier=2,
    description="Code review, quality analysis, improvement suggestions",
))

_register(AgentSpec(
    name="tester",
    display_name="Tester",
    capabilities=["testing"],
    preferred_model_capability="coding",
    tier=1,
    description="Unit tests, integration tests, test execution",
))

_register(AgentSpec(
    name="security-auditor",
    display_name="Security Auditor",
    capabilities=["security", "review"],
    preferred_model_capability="reasoning",
    tier=2,
    description="CVE scanning, vulnerability audit, security review",
))

_register(AgentSpec(
    name="performance-engineer",
    display_name="Performance Engineer",
    capabilities=["performance", "refactoring"],
    preferred_model_capability="coding",
    tier=2,
    description="Performance profiling, optimization, caching strategies",
))

# ---------------------------------------------------------------------------
# DevOps / Infrastructure agents
# ---------------------------------------------------------------------------

_register(AgentSpec(
    name="devops-engineer",
    display_name="CI/CD Engineer",
    capabilities=["devops"],
    preferred_model_capability="coding",
    tier=2,
    description="Docker, Kubernetes, CI/CD pipelines, deployment",
))

# ---------------------------------------------------------------------------
# Research / Documentation agents
# ---------------------------------------------------------------------------

_register(AgentSpec(
    name="researcher",
    display_name="Researcher",
    capabilities=["research", "documentation"],
    preferred_model_capability="research",
    tier=1,
    description="Technical research, comparison, analysis, documentation",
))

_register(AgentSpec(
    name="documenter",
    display_name="API Documentation",
    capabilities=["documentation"],
    preferred_model_capability="research",
    tier=1,
    description="README, API docs, Swagger/OpenAPI, guides",
))

# ---------------------------------------------------------------------------
# Orchestration agents (used internally by the orchestrator)
# ---------------------------------------------------------------------------

_register(AgentSpec(
    name="verifier",
    display_name="Verifier",
    capabilities=["review", "testing"],
    preferred_model_capability="reasoning",
    tier=2,
    description="Verifies correctness, completeness, and quality of output",
    tags=["internal"],
))

_register(AgentSpec(
    name="humanizer",
    display_name="Humanizer",
    capabilities=["documentation"],
    preferred_model_capability="research",
    tier=1,
    description="Improves readability and formatting of final output",
    tags=["internal"],
))

# ---------------------------------------------------------------------------
# Swarm / Hive agents
# ---------------------------------------------------------------------------

_register(AgentSpec(
    name="swarm-coordinator",
    display_name="Swarm Coordinator",
    capabilities=["architecture", "review"],
    preferred_model_capability="reasoning",
    tier=3,
    description="Coordinates parallel agent execution in swarm mode",
    tags=["orchestration"],
))

_register(AgentSpec(
    name="hive-coordinator",
    display_name="Hive Coordinator",
    capabilities=["architecture", "review"],
    preferred_model_capability="reasoning",
    tier=3,
    description="Coordinates hive-mind consensus building",
    tags=["orchestration"],
))


# =============================================================================
# QUERY API
# =============================================================================

def find_agents_for_capability(capability: str) -> list[AgentSpec]:
    """Find all agents that can handle a given capability."""
    return [a for a in AGENTS.values() if capability in a.capabilities]


def find_agents_for_capabilities(capabilities: list[str]) -> dict[str, list[AgentSpec]]:
    """Find agents for multiple capabilities. Returns {capability: [agents]}."""
    result = {}
    for cap in capabilities:
        agents = find_agents_for_capability(cap)
        if agents:
            result[cap] = agents
    return result


def get_agent(name: str) -> AgentSpec | None:
    """Get a specific agent by name."""
    return AGENTS.get(name)


def list_all_agents() -> list[AgentSpec]:
    """Return all registered agents."""
    return list(AGENTS.values())


def register_agent(spec: AgentSpec) -> None:
    """Register a new agent at runtime."""
    AGENTS[spec.name] = spec
