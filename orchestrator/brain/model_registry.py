"""
VEXORA Model Registry — Dynamic Model Catalog

Never hardcode model names. This registry is the single source of truth
for every model the orchestrator can use. When a new model launches on
OpenRouter or Gemini, add it here — zero code changes anywhere else.

The router asks:
    best_models("coding")
instead of:
    return "deepseek-chat"
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelSpec:
    """A single LLM model specification."""
    id: str                          # e.g. "deepseek/deepseek-chat"
    provider: str                    # "openrouter" | "gemini" | "groq" | "ollama"
    name: str                        # Human-readable name
    capabilities: list[str]          # ["coding", "reasoning", "research", ...]
    context_window: int = 128_000    # tokens
    cost_per_1m_input: float = 0.0   # USD per 1M input tokens
    cost_per_1m_output: float = 0.0  # USD per 1M output tokens
    speed_tier: int = 2              # 1=fast, 2=balanced, 3=slow-but-powerful
    quality_tier: int = 2            # 1=basic, 2=good, 3=best
    is_available: bool = True        # Can be toggled off without removal
    max_output_tokens: int = 8192
    supports_streaming: bool = True
    supports_vision: bool = False
    tags: list[str] = field(default_factory=list)  # Extra tags: ["free", "open-source", ...]


# =============================================================================
# THE REGISTRY — Single source of truth for all models
# =============================================================================

MODELS: dict[str, ModelSpec] = {}


def _register(spec: ModelSpec) -> None:
    """Register a model spec in the global registry."""
    MODELS[spec.id] = spec


# ---------------------------------------------------------------------------
# OpenRouter models
# ---------------------------------------------------------------------------

_register(ModelSpec(
    id="deepseek/deepseek-r1",
    provider="openrouter",
    name="DeepSeek R1 (Reasoner)",
    capabilities=["reasoning", "architecture", "security", "coding", "analysis"],
    context_window=128_000,
    cost_per_1m_input=0.55,
    cost_per_1m_output=2.19,
    speed_tier=3,
    quality_tier=3,
    tags=["deep-reasoning", "open-source"],
))

_register(ModelSpec(
    id="deepseek/deepseek-chat",
    provider="openrouter",
    name="DeepSeek V3 Chat",
    capabilities=["coding", "review", "implementation", "optimization", "analysis"],
    context_window=128_000,
    cost_per_1m_input=0.27,
    cost_per_1m_output=1.10,
    speed_tier=2,
    quality_tier=3,
    tags=["cost-effective", "open-source"],
))

_register(ModelSpec(
    id="google/gemini-2.5-flash",
    provider="openrouter",
    name="Gemini 2.5 Flash (OR)",
    capabilities=["general", "coding", "research", "documentation", "writing", "analysis", "reasoning"],
    context_window=1_048_576,
    cost_per_1m_input=0.15,
    cost_per_1m_output=0.60,
    speed_tier=1,
    quality_tier=2,
    supports_vision=True,
    tags=["fast", "cost-effective"],
))

_register(ModelSpec(
    id="qwen/qwen-2.5-coder-32b-instruct",
    provider="openrouter",
    name="Qwen 2.5 Coder 32B",
    capabilities=["coding", "review", "debugging", "refactoring"],
    context_window=131_072,
    cost_per_1m_input=0.20,
    cost_per_1m_output=0.20,
    speed_tier=2,
    quality_tier=2,
    tags=["code-specialist", "open-source"],
))

_register(ModelSpec(
    id="meta-llama/llama-4-maverick",
    provider="openrouter",
    name="Llama 4 Maverick",
    capabilities=["coding", "reasoning", "research", "analysis"],
    context_window=1_048_576,
    cost_per_1m_input=0.20,
    cost_per_1m_output=0.60,
    speed_tier=2,
    quality_tier=2,
    tags=["open-source", "long-context"],
))

_register(ModelSpec(
    id="microsoft/mai-ds-r1",
    provider="openrouter",
    name="Microsoft MAI DS R1",
    capabilities=["reasoning", "analysis", "coding", "architecture"],
    context_window=131_072,
    cost_per_1m_input=0.0,
    cost_per_1m_output=0.0,
    speed_tier=2,
    quality_tier=2,
    tags=["free", "reasoning"],
))

# ---------------------------------------------------------------------------
# Gemini models (Google AI Studio)
# ---------------------------------------------------------------------------

_register(ModelSpec(
    id="gemini-2.5-pro",
    provider="gemini",
    name="Gemini 2.5 Pro",
    capabilities=["reasoning", "research", "documentation", "writing", "analysis", "coding", "vision"],
    context_window=1_048_576,
    cost_per_1m_input=1.25,
    cost_per_1m_output=10.0,
    speed_tier=2,
    quality_tier=3,
    supports_vision=True,
    tags=["long-context", "multimodal"],
))

_register(ModelSpec(
    id="gemini-2.5-flash",
    provider="gemini",
    name="Gemini 2.5 Flash",
    capabilities=["general", "coding", "research", "documentation", "writing", "analysis", "reasoning"],
    context_window=1_048_576,
    cost_per_1m_input=0.15,
    cost_per_1m_output=0.60,
    speed_tier=1,
    quality_tier=2,
    supports_vision=True,
    tags=["fast", "cost-effective", "long-context"],
))

_register(ModelSpec(
    id="gemini-2.0-flash",
    provider="gemini",
    name="Gemini 2.0 Flash",
    capabilities=["testing", "research", "documentation", "fast-tasks"],
    context_window=1_048_576,
    cost_per_1m_input=0.10,
    cost_per_1m_output=0.40,
    speed_tier=1,
    quality_tier=1,
    supports_vision=True,
    tags=["fastest", "cheapest"],
))

# ---------------------------------------------------------------------------
# Groq models
# ---------------------------------------------------------------------------

_register(ModelSpec(
    id="llama-3.3-70b-versatile",
    provider="groq",
    name="Llama 3.3 70B (Groq)",
    capabilities=["general", "coding", "reasoning", "fast-tasks", "analysis"],
    context_window=131_072,
    cost_per_1m_input=0.59,
    cost_per_1m_output=0.79,
    speed_tier=1,
    quality_tier=2,
    tags=["ultra-fast", "groq-inference"],
))


# =============================================================================
# QUERY API — used by the model router
# =============================================================================

def best_models(
    capability: str,
    *,
    provider: Optional[str] = None,
    min_quality: int = 1,
    max_cost_input: Optional[float] = None,
    limit: int = 5,
    exclude_unavailable: bool = True,
) -> list[ModelSpec]:
    """
    Return the best models for a given capability, ranked by quality then cost.

    Args:
        capability: e.g. "coding", "reasoning", "research", "security"
        provider: filter to a specific provider
        min_quality: minimum quality tier (1-3)
        max_cost_input: maximum cost per 1M input tokens
        limit: max results to return
        exclude_unavailable: skip models marked unavailable
    """
    candidates = []
    for spec in MODELS.values():
        if exclude_unavailable and not spec.is_available:
            continue
        if capability not in spec.capabilities:
            continue
        if provider and spec.provider != provider:
            continue
        if spec.quality_tier < min_quality:
            continue
        if max_cost_input is not None and spec.cost_per_1m_input > max_cost_input:
            continue
        candidates.append(spec)

    # Sort: highest quality first, then lowest cost, then fastest
    candidates.sort(key=lambda m: (-m.quality_tier, m.cost_per_1m_input, m.speed_tier))
    return candidates[:limit]


def get_model(model_id: str) -> Optional[ModelSpec]:
    """Get a specific model by ID."""
    return MODELS.get(model_id)


def list_all_capabilities() -> list[str]:
    """Return all unique capabilities across all registered models."""
    caps: set[str] = set()
    for spec in MODELS.values():
        caps.update(spec.capabilities)
    return sorted(caps)


def list_models_by_provider(provider: str) -> list[ModelSpec]:
    """Return all models from a given provider."""
    return [m for m in MODELS.values() if m.provider == provider]


def register_model(spec: ModelSpec) -> None:
    """
    Register a new model at runtime — allows hot-adding models
    when a new one appears on OpenRouter without restarting.
    """
    MODELS[spec.id] = spec


def disable_model(model_id: str) -> bool:
    """Mark a model as unavailable (e.g., temporarily down)."""
    if model_id in MODELS:
        MODELS[model_id].is_available = False
        return True
    return False


def enable_model(model_id: str) -> bool:
    """Re-enable a previously disabled model."""
    if model_id in MODELS:
        MODELS[model_id].is_available = True
        return True
    return False
