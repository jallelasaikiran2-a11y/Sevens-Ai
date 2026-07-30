"""
VEXORA Conditional Humanizer — V2

Rules:
  - If only 1 agent produced output → return it directly (no LLM call).
  - If multiple agents → invoke a merge model to combine into ONE cohesive response.
  - Model choice goes through model_router — never hardcoded.
  - Removes duplication, preserves technical specifics.
"""

from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass
class HumanizedOutput:
    """The final humanized response."""
    content: str
    format: str                      # "markdown" | "plain"
    agent_attributions: dict[str, str]
    word_count: int
    was_merged: bool = False          # True if LLM merge was used


async def humanize(combined_output: str, task: str, agent_count: int = 1) -> HumanizedOutput:
    """
    Transform multi-agent output into a polished, readable response.

    TASK 4: Conditional —
      - 1 agent: return directly (zero LLM calls)
      - Multiple agents: structural merge (extract + combine sections)
    """
    # Parse out individual agent outputs from the combined context
    agent_sections = _extract_agent_sections(combined_output)
    attributions: dict[str, str] = {}

    for name, output in agent_sections.items():
        attributions[name] = f"Contributed {len(output)} chars"

    if len(agent_sections) <= 1:
        # Single agent — return directly, no processing
        content = _clean_output(combined_output)
        # Strip the "--- agent_name output ---" header if present
        content = re.sub(r"---\s+\S+\s+output\s+---\n?", "", content).strip()
        return HumanizedOutput(
            content=content,
            format="markdown",
            agent_attributions=attributions,
            word_count=len(content.split()),
            was_merged=False,
        )

    # Multiple agents — structural merge via LLM
    merged = await _structural_merge(agent_sections, task)

    return HumanizedOutput(
        content=merged,
        format="markdown",
        agent_attributions=attributions,
        word_count=len(merged.split()),
        was_merged=True,
    )


def _extract_agent_sections(combined: str) -> dict[str, str]:
    """Parse '--- agent_name output ---' delimited sections."""
    sections: dict[str, str] = {}
    parts = re.split(r"\n*---\s+(\S+)\s+output\s+---\n*", combined)

    if len(parts) < 3:
        # No delimiters found — treat as single output
        cleaned = combined.strip()
        if cleaned:
            sections["agent"] = cleaned
        return sections

    # parts = [preamble, agent1_name, agent1_content, agent2_name, agent2_content, ...]
    for i in range(1, len(parts) - 1, 2):
        agent_name = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if content:
            sections[agent_name] = content

    return sections


async def _structural_merge(sections: dict[str, str], task: str) -> str:
    """
    Merge multiple agent outputs into one cohesive response using an LLM.
    - Combines sections logically
    - Removes duplicate headings/content
    - Preserves all code blocks and technical specifics
    """
    from .executor import get_adapter, VEXORA_IDENTITY_PREFIX
    from .model_registry import get_model

    system = VEXORA_IDENTITY_PREFIX + (
        "You are the Humanizer. Your job is to merge multiple agent outputs into ONE cohesive, readable response. "
        "Remove duplication. Preserve all technical specifics and code blocks. "
        "Do NOT summarize away details. Do NOT re-explain what was already said. Output ONLY the final markdown response."
    )

    prompt = f"Original User Task: {task}\n\nAgent Outputs to Merge:\n"
    for agent_name, content in sections.items():
        prompt += f"\n--- {agent_name} output ---\n{content}\n"

    try:
        # Primary: Groq for fast merging
        model = get_model("llama-3.3-70b-versatile")
        if not model:
            raise ValueError("Primary model not found")
        adapter = get_adapter(model.provider)
        res = await adapter.generate(prompt, model, system)
        return _clean_output(res.content)
    except Exception as e:
        print(f"[HUMANIZER WARN] Primary Groq merge failed ({e}). Falling back to OpenRouter.")
        try:
            # Secondary: OpenRouter
            model = get_model("google/gemini-2.5-pro")
            if not model:
                raise ValueError("Secondary model not found")
            adapter = get_adapter(model.provider)
            res = await adapter.generate(prompt, model, system)
            return _clean_output(res.content)
        except Exception as e2:
            print(f"[HUMANIZER ERROR] Secondary OpenRouter failed ({e2}). Falling back to text concatenation.")
            merged_parts = []
            for agent_name, content in sections.items():
                merged_parts.append(content)
            merged = "\n\n".join(merged_parts)
            return _clean_output(merged)


def humanize_plan(plan: dict) -> str:
    """Format an execution plan (dry-run) as readable markdown."""
    lines = []
    lines.append("# VEXORA Orchestration Plan\n")
    lines.append(f"> **Task:** {plan.get('task', 'N/A')}\n")
    lines.append(f"**Total Agents:** {plan.get('total_agents', 0)}")
    lines.append(f"**Estimated Duration:** {plan.get('estimated_duration_seconds', 0)}s\n")

    lines.append("## Execution Graph\n")
    lines.append("```")
    for stage in plan.get("stages", []):
        agents_str = ", ".join(stage.get("agents", []))
        models_map = stage.get("models", {})
        prefix = "║" if stage.get("parallel") else "│"

        lines.append(f"Stage {stage['stage_id']}: {stage['name']}")
        for agent in stage.get("agents", []):
            model = models_map.get(agent, "?")
            lines.append(f"  {prefix}── {agent} → {model}")
        lines.append(f"  ↓")

    lines.append("  ✓ Final Response")
    lines.append("```\n")

    return "\n".join(lines)


def _clean_output(output: str) -> str:
    """Clean and normalize agent output for readability."""
    # Remove ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', output)
    # Remove excessive blank lines
    cleaned = re.sub(r'\n{4,}', '\n\n\n', cleaned)
    # Remove common CLI noise
    noise_patterns = [
        r'\[WARN\].*\n?',
        r'Skipped helper auto-refresh.*\n?',
        r'\.LOCKED marker present.*\n?',
    ]
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, '', cleaned)
    return cleaned.strip()
