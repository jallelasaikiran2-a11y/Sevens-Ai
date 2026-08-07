"""
sevens Response Planner — V4.1

Sits between Combiner and Humanizer.
Generates a fast, lightweight Response Outline (Markdown skeleton)
describing how the final answer should be structured, ensuring
the Humanizer never drops sections or loses track of multi-agent contributions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import json


@dataclass
class SectionOutline:
    title: str
    purpose: str
    source_agents: list[str] = field(default_factory=list)


@dataclass
class ResponsePlan:
    title: str
    sections: list[SectionOutline] = field(default_factory=list)
    key_takeaways: list[str] = field(default_factory=list)
    raw_outline: str = ""


RESPONSE_PLANNER_PROMPT = """You are sevens's Response Planning Engine.
Your SOLE job is to look at the user prompt and the outputs from multiple specialized agents, and plan the structure of the final answer.

Output a clean Markdown skeleton outline outlining the logical sections for the final response.

Do NOT generate full content or code blocks.
ONLY generate section headers and 1-line bullet points of what each section will cover.

Example:
# [Title]
## Executive Summary
- Brief overview of the solution

## Architecture & Design
- Key components and data flow

## Implementation Code
- Complete FastAPI backend code

## Security & Deployment Considerations
- Auth guidelines and Docker setup
"""


async def plan_response(task: str, agent_outputs: dict[str, str]) -> ResponsePlan:
    """
    Generate a structural Response Plan from task & combined agent outputs.
    Uses a fast model call (Groq) for minimal latency (<300ms).
    """
    from .executor import get_adapter, VEXORA_IDENTITY_PREFIX
    from .model_registry import best_models, get_model

    if len(agent_outputs) <= 1:
        # Single agent output doesn't need response planning
        return ResponsePlan(title="Direct Response", sections=[], raw_outline="")

    # Try fast model (Groq/writing)
    candidates = best_models("writing", limit=2)
    model = candidates[0] if candidates else get_model("llama-3.3-70b-versatile")

    if not model:
        return ResponsePlan(title="Combined Output", sections=[], raw_outline="")

    summary_context = f"User Request: {task}\n\nAvailable Agent Outputs:\n"
    for agent_name, content in agent_outputs.items():
        summary_context += f"- Agent '{agent_name}': {len(content)} chars of output\n"

    system = VEXORA_IDENTITY_PREFIX + RESPONSE_PLANNER_PROMPT

    try:
        adapter = get_adapter(model.provider)
        res = await adapter.generate(summary_context, model, system, temperature=0.1)
        outline_text = res.content.strip()
        
        # Parse basic sections
        sections = []
        for line in outline_text.splitlines():
            if line.startswith("## "):
                sections.append(SectionOutline(title=line[3:].strip(), purpose=""))

        return ResponsePlan(
            title="Response Outline",
            sections=sections,
            raw_outline=outline_text
        )
    except Exception as e:
        print(f"[RESPONSE PLANNER WARN] Plan generation failed: {e}")
        return ResponsePlan(title="Combined Output", sections=[], raw_outline="")
