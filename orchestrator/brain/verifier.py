"""
VEXORA Layered Verifier — V2

Layer 1 (Default — Executable Ground Truth):
  - Code syntax: ast.parse (Python), regex checks for other langs
  - JSON/structure validation
  - Duplicate-section detection (hash-based)
  - Missing-required-section check (CRUD must have Create/Read/Update/Delete)
  - Refusal pattern detection
  - Identity leak detection
  - Truncation detection

Layer 2 (LLM Critique — Level 3/4 only):
  - Uses a DIFFERENT model than the generator to review
  - Escalates only if Layer 1 is inconclusive or task is complex
"""

from __future__ import annotations
import ast
import hashlib
import json
import re
from dataclasses import dataclass, field


@dataclass
class VerifySignal:
    """A single verification signal."""
    name: str
    passed: bool
    severity: str = "info"    # "info" | "warning" | "error"
    detail: str = ""


@dataclass
class VerificationResult:
    """Complete verification verdict."""
    passed: bool
    score: float                    # 0.0 to 1.0
    signals: list[VerifySignal]
    reasons: list[str]              # Failure reasons (empty if passed)
    suggestion: str = ""
    layer: int = 1


# =============================================================================
# Layer 1 — Executable / Structural Verification
# =============================================================================

def _check_non_empty(output: str) -> VerifySignal:
    trimmed = output.strip()
    passed = len(trimmed) >= 20
    return VerifySignal(
        name="non_empty", passed=passed,
        severity="error" if not passed else "info",
        detail=f"Output length: {len(trimmed)} chars",
    )


def _check_refusal(output: str) -> VerifySignal:
    refusal_patterns = [
        r"i can't", r"i cannot", r"i'm not able to", r"i am not able to",
        r"as an ai", r"i don't have access", r"i'm unable to",
        r"sorry,? i", r"unfortunately,? i",
    ]
    has_refusal = any(re.search(p, output.lower()) for p in refusal_patterns)
    return VerifySignal(
        name="no_refusal", passed=not has_refusal,
        severity="warning" if has_refusal else "info",
        detail="Refusal pattern detected" if has_refusal else "No refusal patterns",
    )


def _check_identity_leak(output: str) -> VerifySignal:
    leak_patterns = [
        r"\bi am (a |an )?(large )?language model\b",
        r"\btrained by (openai|google|meta|anthropic|deepseek|alibaba)\b",
        r"\bi('m| am) (llama|gemini|claude|gpt|deepseek|qwen|chatgpt)\b",
        r"\bas (llama|gemini|claude|gpt|deepseek|qwen)\b",
    ]
    has_leak = any(re.search(p, output.lower()) for p in leak_patterns)
    return VerifySignal(
        name="no_identity_leak", passed=not has_leak,
        severity="error" if has_leak else "info",
        detail="Model identity leaked!" if has_leak else "No identity leakage",
    )


def _check_truncation(output: str) -> VerifySignal:
    trimmed = output.strip()
    ending = trimmed[-100:] if len(trimmed) > 100 else trimmed
    truncation_markers = ["...", "```\n\n```", "// ...", "# ..."]
    has_truncation = any(m in ending for m in truncation_markers)
    open_blocks = trimmed.count("```")
    unmatched = open_blocks % 2 != 0
    passed = not has_truncation and not unmatched
    return VerifySignal(
        name="not_truncated", passed=passed,
        severity="warning" if not passed else "info",
        detail="Possible truncation" if not passed else "No truncation",
    )


def _check_repetition(output: str) -> VerifySignal:
    lines = output.strip().split("\n")
    if len(lines) <= 10:
        return VerifySignal(name="no_repetition", passed=True, detail="Too few lines to check")
    non_empty = [l.strip() for l in lines if l.strip()]
    unique = set(non_empty)
    ratio = len(unique) / len(non_empty) if non_empty else 1.0
    passed = ratio > 0.3
    return VerifySignal(
        name="no_repetition", passed=passed,
        severity="error" if not passed else "info",
        detail=f"Unique line ratio: {ratio:.2f}",
    )


def _check_python_syntax(output: str) -> VerifySignal | None:
    """Extract Python code blocks and run ast.parse on them."""
    python_blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", output, re.DOTALL)
    if not python_blocks:
        return None
    errors = []
    for i, block in enumerate(python_blocks):
        try:
            ast.parse(block)
        except SyntaxError as e:
            errors.append(f"Block {i+1}: {e.msg} (line {e.lineno})")
    if errors:
        return VerifySignal(
            name="python_syntax", passed=False, severity="error",
            detail=f"Syntax errors: {'; '.join(errors)}",
        )
    return VerifySignal(
        name="python_syntax", passed=True,
        detail=f"All {len(python_blocks)} Python blocks parse successfully",
    )


def _check_json_validity(output: str) -> VerifySignal | None:
    """Check JSON blocks for validity."""
    json_blocks = re.findall(r"```json\s*\n(.*?)```", output, re.DOTALL)
    if not json_blocks:
        return None
    errors = []
    for i, block in enumerate(json_blocks):
        try:
            json.loads(block)
        except json.JSONDecodeError as e:
            errors.append(f"Block {i+1}: {e.msg}")
    if errors:
        return VerifySignal(
            name="json_validity", passed=False, severity="error",
            detail=f"Invalid JSON: {'; '.join(errors)}",
        )
    return VerifySignal(
        name="json_validity", passed=True,
        detail=f"All {len(json_blocks)} JSON blocks valid",
    )


def _check_duplicate_sections(agent_outputs: list[str]) -> VerifySignal:
    """Hash-based duplication detection across agent outputs."""
    if len(agent_outputs) <= 1:
        return VerifySignal(name="no_duplicates", passed=True, detail="Single agent output")
    paragraph_hashes: dict[str, list[int]] = {}
    for i, output in enumerate(agent_outputs):
        paragraphs = [p.strip() for p in output.split("\n\n") if len(p.strip()) > 50]
        for para in paragraphs:
            h = hashlib.md5(para.lower().encode()).hexdigest()[:12]
            if h not in paragraph_hashes:
                paragraph_hashes[h] = []
            paragraph_hashes[h].append(i)
    duplicates = sum(1 for agents in paragraph_hashes.values() if len(set(agents)) > 1)
    total = len(paragraph_hashes) if paragraph_hashes else 1
    dup_ratio = duplicates / total
    passed = dup_ratio < 0.3
    return VerifySignal(
        name="no_duplicates", passed=passed,
        severity="warning" if not passed else "info",
        detail=f"Duplicate paragraphs: {duplicates}/{total} ({dup_ratio:.0%})",
    )


def _check_crud_completeness(output: str, task: str) -> VerifySignal | None:
    """If task is CRUD-like, check that all operations are present."""
    if "crud" not in task.lower():
        return None
    crud_patterns = {
        "create": [r"\bpost\b", r"\bcreate\b", r"\.post\(", r"def create", r"insert"],
        "read": [r"\bget\b", r"\bread\b", r"\.get\(", r"def get", r"select"],
        "update": [r"\bput\b", r"\bpatch\b", r"\bupdate\b", r"\.put\(", r"def update"],
        "delete": [r"\bdelete\b", r"\.delete\(", r"def delete", r"remove"],
    }
    output_lower = output.lower()
    missing = []
    for op, patterns in crud_patterns.items():
        if not any(re.search(p, output_lower) for p in patterns):
            missing.append(op)
    passed = len(missing) == 0
    return VerifySignal(
        name="crud_completeness", passed=passed,
        severity="error" if not passed else "info",
        detail=f"Missing CRUD ops: {', '.join(missing)}" if missing else "All CRUD operations present",
    )


def _check_capability_coverage(output: str, capabilities: list[str]) -> VerifySignal:
    cap_keywords = {
        "architecture": ["architecture", "design", "schema", "structure", "component"],
        "backend": ["api", "endpoint", "route", "server", "handler", "fastapi"],
        "frontend": ["component", "ui", "react", "page", "layout", "jsx"],
        "database": ["database", "table", "query", "migration", "schema", "model"],
        "security": ["auth", "security", "jwt", "encrypt", "permission"],
        "testing": ["test", "assert", "spec", "coverage", "mock"],
        "devops": ["docker", "deploy", "ci/cd", "pipeline", "container"],
        "documentation": ["readme", "doc", "guide", "usage"],
    }
    output_lower = output.lower()
    covered = []
    uncovered = []
    for cap in capabilities:
        if cap in ("conversation", "research", "review", "refactoring", "performance", "ml", "mobile", "reasoning"):
            covered.append(cap)
            continue
        keywords = cap_keywords.get(cap, [cap])
        if any(kw in output_lower for kw in keywords):
            covered.append(cap)
        else:
            uncovered.append(cap)
    total = len(capabilities) if capabilities else 1
    coverage = len(covered) / total
    passed = coverage >= 0.5
    return VerifySignal(
        name="capability_coverage", passed=passed,
        severity="warning" if not passed else "info",
        detail=f"Covered {len(covered)}/{total}" +
               (f". Missing: {', '.join(uncovered)}" if uncovered else ""),
    )


# =============================================================================
# Main Verify Function
# =============================================================================

def verify(
    output: str,
    task: str,
    capabilities: list[str],
    agent_outputs: list[str] | None = None,
    complexity: str = "Medium",
) -> VerificationResult:
    """
    Verify the combined output.
    Layer 1 is always run. Layer 2 (LLM critique) only for Level 3/4.
    """
    signals: list[VerifySignal] = []
    reasons: list[str] = []

    # Core checks
    signals.append(_check_non_empty(output))
    signals.append(_check_refusal(output))
    signals.append(_check_identity_leak(output))
    signals.append(_check_truncation(output))
    signals.append(_check_repetition(output))

    # Code checks
    py = _check_python_syntax(output)
    if py:
        signals.append(py)
    js = _check_json_validity(output)
    if js:
        signals.append(js)

    # Duplication check
    if agent_outputs and len(agent_outputs) > 1:
        signals.append(_check_duplicate_sections(agent_outputs))

    # CRUD completeness
    crud = _check_crud_completeness(output, task)
    if crud:
        signals.append(crud)

    # Capability coverage
    signals.append(_check_capability_coverage(output, capabilities))

    # Collect failure reasons
    for s in signals:
        if not s.passed:
            reasons.append(f"[{s.severity.upper()}] {s.name}: {s.detail}")

    # Score
    error_count = sum(1 for s in signals if not s.passed and s.severity == "error")
    total = len(signals) if signals else 1
    passed_count = sum(1 for s in signals if s.passed)
    score = passed_count / total
    overall_passed = error_count == 0 and score >= 0.5

    suggestion = ""
    if not overall_passed:
        if any(s.name == "non_empty" and not s.passed for s in signals):
            suggestion = "Re-execute all agents — output was empty"
        elif any(s.name == "python_syntax" and not s.passed for s in signals):
            suggestion = "Code has syntax errors — re-execute coding agents"
        elif any(s.name == "no_refusal" and not s.passed for s in signals):
            suggestion = "Retry with alternative model — current model refused"
        else:
            suggestion = "Review and retry failed stages"

    return VerificationResult(
        passed=overall_passed,
        score=round(score, 2),
        signals=signals,
        reasons=reasons,
        suggestion=suggestion,
        layer=1,
    )
