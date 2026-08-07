"""
sevens Tool Registry — V3

Registry-driven tool resolution. The Planner and Capability Resolver
never reference concrete tools. They request abstract tool types:

    "web_search" → Tavily
    "filesystem_read" → Sevens Filesystem MCP
    "terminal_exec" → Sevens Terminal MCP

Adding a new tool = adding one entry. Zero code changes elsewhere.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolSpec:
    """A single tool specification."""
    id: str                          # e.g. "tavily"
    abstract_type: str               # e.g. "web_search"
    name: str                        # Human-readable
    provider: str                    # "tavily" | "sevens_mcp" | "github_mcp" | etc.
    is_available: bool = True
    requires_api_key: bool = False
    api_key_env_var: str = ""        # e.g. "TAVILY_API_KEY"
    description: str = ""
    tags: list[str] = field(default_factory=list)


# =============================================================================
# THE REGISTRY
# =============================================================================

TOOLS: dict[str, ToolSpec] = {}


def _register(spec: ToolSpec) -> None:
    TOOLS[spec.id] = spec


# --- Web Search ---
_register(ToolSpec(
    id="tavily",
    abstract_type="web_search",
    name="Tavily Web Search",
    provider="tavily",
    requires_api_key=True,
    api_key_env_var="TAVILY_API_KEY",
    description="Real-time web search with AI-generated summaries",
    tags=["search", "research"],
))

# --- Filesystem ---
_register(ToolSpec(
    id="sevens_fs_read",
    abstract_type="filesystem_read",
    name="Sevens Filesystem Read",
    provider="sevens_mcp",
    description="Read files from the project filesystem",
    tags=["filesystem"],
))

_register(ToolSpec(
    id="sevens_fs_write",
    abstract_type="filesystem_write",
    name="Sevens Filesystem Write",
    provider="sevens_mcp",
    description="Write/create files in the project filesystem",
    tags=["filesystem"],
))

_register(ToolSpec(
    id="sevens_fs_search",
    abstract_type="filesystem_search",
    name="Sevens Filesystem Search",
    provider="sevens_mcp",
    description="Search for files and content in the project",
    tags=["filesystem", "search"],
))

# --- Terminal ---
_register(ToolSpec(
    id="sevens_terminal",
    abstract_type="terminal_exec",
    name="Sevens Terminal",
    provider="sevens_mcp",
    description="Execute shell commands",
    tags=["terminal", "exec"],
))

# --- Browser ---
_register(ToolSpec(
    id="sevens_browser",
    abstract_type="browser_fetch",
    name="Sevens Browser Fetch",
    provider="sevens_mcp",
    description="Fetch and parse web pages",
    tags=["browser", "web"],
))

# --- GitHub ---
_register(ToolSpec(
    id="github_mcp",
    abstract_type="github",
    name="GitHub MCP",
    provider="github_mcp",
    is_available=False,  # Not yet integrated
    description="GitHub API integration for repos, PRs, issues",
    tags=["github", "git"],
))


# =============================================================================
# QUERY API
# =============================================================================

def resolve_tool(abstract_type: str) -> Optional[ToolSpec]:
    """Resolve an abstract tool type to a concrete tool spec."""
    for spec in TOOLS.values():
        if spec.abstract_type == abstract_type and spec.is_available:
            return spec
    return None


def resolve_tools(abstract_types: list[str]) -> list[ToolSpec]:
    """Resolve multiple abstract tool types."""
    resolved = []
    seen = set()
    for t in abstract_types:
        spec = resolve_tool(t)
        if spec and spec.id not in seen:
            resolved.append(spec)
            seen.add(spec.id)
    return resolved


def get_tool(tool_id: str) -> Optional[ToolSpec]:
    """Get a specific tool by its ID."""
    return TOOLS.get(tool_id)


def list_all_tools() -> list[ToolSpec]:
    """List all registered tools."""
    return list(TOOLS.values())
