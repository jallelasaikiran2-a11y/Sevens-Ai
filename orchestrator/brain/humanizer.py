"""
sevens Conditional Humanizer — V2

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


# V4.1 — Editorial Engine system prompt (strict preservation constraints)
_HUMANIZER_SYSTEM = (
    "You are sevens's Editorial Engine — an elite technical editor.\n"
    "Your ONLY job is presentation. Merge and polish the agent outputs below into ONE cohesive, readable response.\n\n"
    "RULES:\n"
    "✓ Professional, natural writing with smooth transitions\n"
    "✓ Remove robotic filler and duplicate wording\n"
    "✓ Preserve EVERY code block exactly as written\n"
    "✓ Preserve EVERY architectural decision and reasoning chain\n"
    "✓ Preserve EVERY citation and source URL\n"
    "✓ Preserve ALL technical facts and specifics\n\n"
    "CONSTRAINTS:\n"
    "✗ Do NOT redesign or rewrite architecture\n"
    "✗ Do NOT optimize or change code logic\n"
    "✗ Do NOT invent new information\n"
    "✗ Do NOT remove technical details\n"
    "✗ Do NOT add disclaimers about being an AI\n\n"
    "Output ONLY the final polished markdown response."
)


def _get_humanizer_model():
    """Select the best available model for humanization using the model router."""
    from .model_registry import best_models, get_model

    # Try writing-optimized models first
    candidates = best_models("writing", limit=3)
    if candidates:
        return candidates[0]

    # Fall back to general capability
    candidates = best_models("general", limit=3)
    if candidates:
        return candidates[0]

    # Absolute fallback
    return get_model("llama-3.3-70b-versatile")


async def _structural_merge(sections: dict[str, str], task: str) -> str:
    """
    Merge multiple agent outputs into one cohesive response using an LLM.
    V4.1: Uses model router instead of hardcoded model IDs.
    """
    from .executor import get_adapter, VEXORA_IDENTITY_PREFIX

    system = VEXORA_IDENTITY_PREFIX + _HUMANIZER_SYSTEM

    prompt = f"Original User Task: {task}\n\nAgent Outputs to Merge:\n"
    for agent_name, content in sections.items():
        prompt += f"\n--- {agent_name} output ---\n{content}\n"

    model = _get_humanizer_model()
    if not model:
        # No models available — fall back to text concatenation
        return _clean_output("\n\n".join(sections.values()))

    try:
        adapter = get_adapter(model.provider)
        res = await adapter.generate(prompt, model, system)
        return _clean_output(res.content)
    except Exception as e:
        print(f"[HUMANIZER WARN] Primary merge failed ({e}). Trying fallback.")
        # Try a different provider
        from .model_registry import best_models
        candidates = best_models("general", limit=5)
        for cand in candidates:
            if cand.provider != model.provider:
                try:
                    adapter = get_adapter(cand.provider)
                    res = await adapter.generate(prompt, cand, system)
                    return _clean_output(res.content)
                except Exception:
                    continue
        # All providers failed — raw concatenation
        print("[HUMANIZER ERROR] All providers failed. Using raw concatenation.")
        return _clean_output("\n\n".join(sections.values()))


async def humanize_stream(combined_output: str, task: str, agent_count: int = 1):
    """
    V4.1 Streaming Humanizer — yields tokens as they are generated.
    
    For single-agent output: yields the cleaned text in one chunk (no LLM call).
    For multi-agent output: streams the editorial merge via generate_stream().
    
    Usage in main.py:
        async for chunk in humanize_stream(combined, task, agent_count):
            await send_sse({"type": "chunk", "text": chunk})
    """
    from .executor import get_adapter, VEXORA_IDENTITY_PREFIX

    agent_sections = _extract_agent_sections(combined_output)

    if len(agent_sections) <= 1:
        # Single agent — return directly, no LLM call
        content = _clean_output(combined_output)
        content = re.sub(r"---\s+\S+\s+output\s+---\n?", "", content).strip()
        yield content
        return

    # Multi-agent — stream the editorial merge
    system = VEXORA_IDENTITY_PREFIX + _HUMANIZER_SYSTEM
    prompt = f"Original User Task: {task}\n\nAgent Outputs to Merge:\n"
    for agent_name, content in agent_sections.items():
        prompt += f"\n--- {agent_name} output ---\n{content}\n"

    model = _get_humanizer_model()
    if not model:
        yield _clean_output("\n\n".join(agent_sections.values()))
        return

    try:
        adapter = get_adapter(model.provider)
        async for chunk in adapter.generate_stream(prompt, model, system):
            yield chunk
    except Exception as e:
        print(f"[HUMANIZER STREAM ERROR] {e}. Falling back to non-streaming.")
        try:
            res = await adapter.generate(prompt, model, system)
            yield _clean_output(res.content)
        except Exception:
            yield _clean_output("\n\n".join(agent_sections.values()))


def humanize_plan(plan: dict) -> str:
    """Format an execution plan (dry-run) as readable markdown."""
    lines = []
    lines.append("# sevens Orchestration Plan\n")
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


def _strip_internal_contract(content: str) -> str:
    """
    Remove the Sevens agent contract metadata from the output.
    Finds the last occurrence of '## Handoff Notes' and returns everything after it.
    """
    marker = "## Handoff Notes"
    if marker in content:
        parts = content.split(marker)
        # The actual answer is everything after the handoff notes section
        # Handoff notes might have content below it, so we split by double newline
        # to skip the handoff notes content.
        after_marker = parts[-1].strip()
        # Find the first blank line after the marker content to start the real answer
        if "\n\n" in after_marker:
            return after_marker.split("\n\n", 1)[1].strip()
        return after_marker.strip()
    return content

def _clean_output(output: str) -> str:
    """Clean and normalize agent output for readability."""
    # Remove ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', output)
    
    # Strip internal contract headers if they leaked
    cleaned = _strip_internal_contract(cleaned)
    
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
