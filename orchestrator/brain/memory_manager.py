"""
sevens Memory Manager — V3

Three memory scopes:

1. Conversation Memory (Long-lived)
   - Persists across multiple user requests within a session.
   - Stores: user preferences, project state, conversation history.

2. Execution Memory (Request-scoped)
   - Lives only for the duration of a single orchestration request.
   - Shared across ALL agents in the DAG.
   - Structured into: Decisions, Artifacts, Facts, Pending Tasks.
   - Example: Architect writes a schema decision → Backend Dev reads it.

3. Scratch Memory (Agent-scoped)
   - Private to a single agent execution.
   - Never shared. Destroyed after the agent finishes.
   - Used for intermediate reasoning, drafts, etc.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import time
import uuid


# =============================================================================
# Execution Memory — Structured, Request-Scoped
# =============================================================================

@dataclass
class Decision:
    """A design/architecture decision made by an agent — reasoning-preserving."""
    agent: str
    category: str                                   # "architecture" | "technology" | "security" | "data" | etc.
    summary: str
    reasoning: str = ""                              # WHY this decision was made
    alternatives: list[str] = field(default_factory=list)   # What else was considered
    rejection_reasons: list[str] = field(default_factory=list)  # Why alternatives were rejected
    confidence: float = 0.8                          # Agent's confidence in this decision (0.0-1.0)
    linked_artifacts: list[str] = field(default_factory=list)  # Names of related Artifacts
    timestamp: float = 0.0

    # Back-compat alias for code that still uses 'rationale'
    @property
    def rationale(self) -> str:
        return self.reasoning

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class Artifact:
    """A concrete output produced by an agent (code, schema, config, etc.)."""
    agent: str
    artifact_type: str      # "code" | "schema" | "config" | "documentation" | "test"
    name: str
    content: str
    language: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class Fact:
    """A verified fact or constraint discovered during execution."""
    agent: str
    statement: str
    source: str = ""        # "user" | "research" | "agent_inference"
    confidence: float = 1.0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class PendingTask:
    """A task flagged by one agent for another downstream agent."""
    from_agent: str
    for_capability: str     # capability needed, e.g. "testing", "security"
    description: str
    priority: str = "normal"  # "low" | "normal" | "high" | "critical"
    resolved: bool = False
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


# =============================================================================
# Memory Namespaces — V4.1
# =============================================================================

# All valid namespace identifiers.
NAMESPACE_ALL = "*"
NAMESPACES = [
    "architecture",
    "research",
    "api_contracts",
    "facts",
    "security",
    "performance",
    "testing",
    "deliverables",
    "pending_tasks",
    "completed_tasks",
]

# Maps Decision/Artifact categories → namespaces for automatic routing.
_CATEGORY_NAMESPACE: dict[str, str] = {
    "architecture": "architecture",
    "technology": "architecture",
    "design": "architecture",
    "schema": "api_contracts",
    "api": "api_contracts",
    "contract": "api_contracts",
    "security": "security",
    "auth": "security",
    "performance": "performance",
    "optimization": "performance",
    "test": "testing",
    "testing": "testing",
    "research": "research",
    "data": "architecture",
    "code": "deliverables",
    "documentation": "deliverables",
    "config": "deliverables",
}

def _resolve_namespace(category: str) -> str:
    """Map a decision/artifact category to its memory namespace."""
    return _CATEGORY_NAMESPACE.get(category.lower(), "facts")


@dataclass
class ExecutionMemory:
    """
    Structured shared memory for a single orchestration request.
    All agents read from and write to this during DAG execution.

    V4.1: Supports namespace-partitioned reads via to_namespace_prompt().
    """
    request_id: str = ""
    decisions: list[Decision] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    pending_tasks: list[PendingTask] = field(default_factory=list)
    created_at: float = 0.0

    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = time.time()

    # --- Write API ---

    def add_decision(
        self,
        agent: str,
        category: str,
        summary: str,
        reasoning: str = "",
        alternatives: list[str] | None = None,
        rejection_reasons: list[str] | None = None,
        confidence: float = 0.8,
        linked_artifacts: list[str] | None = None,
    ) -> None:
        self.decisions.append(Decision(
            agent=agent,
            category=category,
            summary=summary,
            reasoning=reasoning,
            alternatives=alternatives or [],
            rejection_reasons=rejection_reasons or [],
            confidence=confidence,
            linked_artifacts=linked_artifacts or [],
        ))

    def add_artifact(self, agent: str, artifact_type: str, name: str, content: str, language: str = "") -> None:
        self.artifacts.append(Artifact(agent=agent, artifact_type=artifact_type, name=name, content=content, language=language))

    def add_fact(self, agent: str, statement: str, source: str = "agent_inference", confidence: float = 1.0) -> None:
        self.facts.append(Fact(agent=agent, statement=statement, source=source, confidence=confidence))

    def add_pending_task(self, from_agent: str, for_capability: str, description: str, priority: str = "normal") -> None:
        self.pending_tasks.append(PendingTask(from_agent=from_agent, for_capability=for_capability, description=description, priority=priority))

    def resolve_task(self, index: int) -> None:
        if 0 <= index < len(self.pending_tasks):
            self.pending_tasks[index].resolved = True

    # --- Read API ---

    def get_decisions(self, category: str | None = None) -> list[Decision]:
        if category:
            return [d for d in self.decisions if d.category == category]
        return list(self.decisions)

    def get_artifacts(self, artifact_type: str | None = None) -> list[Artifact]:
        if artifact_type:
            return [a for a in self.artifacts if a.artifact_type == artifact_type]
        return list(self.artifacts)

    def get_facts(self) -> list[Fact]:
        return list(self.facts)

    def get_pending_tasks(self, for_capability: str | None = None, unresolved_only: bool = True) -> list[PendingTask]:
        tasks = self.pending_tasks
        if for_capability:
            tasks = [t for t in tasks if t.for_capability == for_capability]
        if unresolved_only:
            tasks = [t for t in tasks if not t.resolved]
        return tasks

    # --- Serialization for prompt injection ---

    def to_context_prompt(self) -> str:
        """Serialize the ENTIRE execution memory into a text block for agent prompts.
        
        Prefer to_namespace_prompt() for targeted injection.
        """
        return self.to_namespace_prompt([NAMESPACE_ALL])

    def to_namespace_prompt(self, namespaces: list[str]) -> str:
        """
        Serialize ONLY the requested memory namespaces into a text block.

        This is the V4.1 targeted injection API. The scheduler calls this
        with the agent's declared namespace requirements, drastically
        reducing token usage and TTFT.

        Pass [NAMESPACE_ALL] or ["*"] to get everything (equivalent to to_context_prompt).
        """
        want_all = NAMESPACE_ALL in namespaces or "*" in namespaces
        ns_set = set(namespaces)
        lines: list[str] = []

        # --- Decisions ---
        if self.decisions:
            if want_all:
                matching = self.decisions
            else:
                matching = [d for d in self.decisions if _resolve_namespace(d.category) in ns_set]
            if matching:
                lines.append("## Shared Decisions")
                for d in matching:
                    lines.append(f"- [{d.category}] {d.summary} (by {d.agent}, confidence: {d.confidence})")
                    if d.reasoning:
                        lines.append(f"  Reasoning: {d.reasoning}")
                    if d.alternatives:
                        lines.append(f"  Alternatives considered: {', '.join(d.alternatives)}")
                    if d.rejection_reasons:
                        lines.append(f"  Rejected because: {'; '.join(d.rejection_reasons)}")
                lines.append("")

        # --- Artifacts ---
        if self.artifacts:
            if want_all:
                matching_art = self.artifacts
            else:
                matching_art = [a for a in self.artifacts if _resolve_namespace(a.artifact_type) in ns_set]
            if matching_art:
                lines.append("## Shared Artifacts")
                for a in matching_art:
                    lines.append(f"- [{a.artifact_type}] {a.name} (by {a.agent}, {len(a.content)} chars)")
                lines.append("")

        # --- Facts ---
        if self.facts and (want_all or "facts" in ns_set or "research" in ns_set):
            matching_facts = self.facts
            if "research" in ns_set and not want_all and "facts" not in ns_set:
                matching_facts = [f for f in self.facts if f.source == "research"]
            if matching_facts:
                lines.append("## Known Facts")
                for f in matching_facts:
                    lines.append(f"- {f.statement} (source: {f.source}, confidence: {f.confidence})")
                lines.append("")

        # --- Pending Tasks ---
        if want_all or "pending_tasks" in ns_set:
            pending = self.get_pending_tasks(unresolved_only=True)
            if pending:
                lines.append("## Pending Tasks for You")
                for t in pending:
                    lines.append(f"- [{t.priority}] {t.description} (from {t.from_agent})")
                lines.append("")

        return "\n".join(lines) if lines else ""

    def summary_stats(self) -> dict:
        """Return counts for telemetry display."""
        return {
            "decisions": len(self.decisions),
            "artifacts": len(self.artifacts),
            "facts": len(self.facts),
            "pending_tasks": len(self.get_pending_tasks(unresolved_only=True)),
        }


# =============================================================================
# Scratch Memory — Agent-Private
# =============================================================================

@dataclass
class ScratchMemory:
    """
    Private memory for a single agent execution.
    Never shared with other agents. Destroyed after execution.
    """
    agent_name: str
    notes: list[str] = field(default_factory=list)
    intermediate_drafts: list[str] = field(default_factory=list)

    def add_note(self, note: str) -> None:
        self.notes.append(note)

    def add_draft(self, draft: str) -> None:
        self.intermediate_drafts.append(draft)


# =============================================================================
# Conversation Memory — Session-Scoped, Cross-Turn
# =============================================================================

@dataclass
class ConversationTurn:
    """A single turn in the conversation history."""
    role: str               # "user" | "assistant"
    content: str
    timestamp: float = 0.0
    capabilities_used: list[str] = field(default_factory=list)
    agents_used: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class ConversationMemory:
    """
    Persistent memory across user turns within a session.
    Tracks conversation history, user preferences, and project state.
    """
    session_id: str = ""
    turns: list[ConversationTurn] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    project_context: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def __post_init__(self):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = time.time()

    def add_turn(self, role: str, content: str, capabilities: list[str] | None = None, agents: list[str] | None = None) -> None:
        self.turns.append(ConversationTurn(
            role=role,
            content=content,
            capabilities_used=capabilities or [],
            agents_used=agents or [],
        ))

    def get_recent_context(self, max_turns: int = 5) -> str:
        """Get the last N turns as a context string for the planner."""
        recent = self.turns[-max_turns:] if len(self.turns) > max_turns else self.turns
        lines = ["## Conversation History"]
        for turn in recent:
            prefix = "User" if turn.role == "user" else "sevens"
            # Truncate long content
            content = turn.content[:300] + "..." if len(turn.content) > 300 else turn.content
            lines.append(f"**{prefix}:** {content}")
        return "\n".join(lines)

    def set_preference(self, key: str, value: Any) -> None:
        self.user_preferences[key] = value

    def set_project_context(self, key: str, value: Any) -> None:
        self.project_context[key] = value


# =============================================================================
# Session Store — In-memory session management
# =============================================================================

_sessions: dict[str, ConversationMemory] = {}


def get_or_create_session(session_id: str | None = None) -> ConversationMemory:
    """Get an existing session or create a new one."""
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    session = ConversationMemory(session_id=session_id or "")
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> ConversationMemory | None:
    """Get a session by ID, or None if not found."""
    return _sessions.get(session_id)
