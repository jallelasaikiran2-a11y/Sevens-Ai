"""
VEXORA Tool Selector

Determines which Ruflo MCP tools each agent needs for its task.
Only activates tools the task actually requires.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .capability_analyzer import CapabilityAnalysis


@dataclass
class ToolSelection:
    """Tools required for a task execution."""
    tools: list[str]            # List of MCP tool names
    reason: str                 # Why these tools were selected


# Capability → tool mapping
CAPABILITY_TOOLS: dict[str, list[str]] = {
    "architecture":  ["filesystem_read", "filesystem_search"],
    "backend":       ["filesystem_read", "filesystem_write", "terminal_exec", "filesystem_search"],
    "frontend":      ["filesystem_read", "filesystem_write", "terminal_exec"],
    "database":      ["filesystem_read", "filesystem_write", "terminal_exec"],
    "security":      ["filesystem_read", "filesystem_search", "terminal_exec"],
    "testing":       ["filesystem_read", "filesystem_write", "terminal_exec"],
    "devops":        ["filesystem_read", "filesystem_write", "terminal_exec"],
    "documentation": ["filesystem_read", "filesystem_write"],
    "ml":            ["filesystem_read", "filesystem_write", "terminal_exec"],
    "mobile":        ["filesystem_read", "filesystem_write", "terminal_exec"],
    "performance":   ["filesystem_read", "terminal_exec", "filesystem_search"],
    "refactoring":   ["filesystem_read", "filesystem_write", "filesystem_search"],
    "research":      ["web_search", "browser_fetch"],
    "review":        ["filesystem_read", "filesystem_search"],
}


def select_tools(analysis: CapabilityAnalysis) -> ToolSelection:
    """
    Select the minimum set of tools needed for the task.
    """
    tools_needed: set[str] = set()

    for cap in analysis.capabilities:
        cap_tools = CAPABILITY_TOOLS.get(cap, [])
        tools_needed.update(cap_tools)

    tools_list = sorted(tools_needed)
    reason = f"Selected {len(tools_list)} tools for capabilities: {', '.join(analysis.capabilities)}"

    return ToolSelection(tools=tools_list, reason=reason)
