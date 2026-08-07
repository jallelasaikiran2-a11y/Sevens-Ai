"""
sevens Capability Analyzer

Extracts CAPABILITIES from a user prompt — not just keywords.

User says: "Build a SaaS CRM"
Capabilities become:
    architecture, backend, database, security, testing, documentation, frontend

The Agent Selector then works from capabilities, not keywords.
This makes routing much more reliable.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CapabilityAnalysis:
    """Result of analyzing a user prompt for required capabilities."""
    prompt: str
    intent: str                          # High-level intent description
    domain: str                          # web, mobile, ml, devops, security, docs, general
    complexity: str                      # Low, Medium, High, Critical
    capabilities: list[str]              # e.g. ["architecture", "backend", "database", ...]
    keywords_matched: list[str]          # Debug: which keywords triggered which capabilities
    estimated_agents: int                # Rough count of agents needed
    requires_verification: bool = True   # Almost always True
    requires_humanization: bool = True


# =============================================================================
# Capability detection rules
# =============================================================================
# Each rule maps keywords → capabilities. A single prompt can trigger many.

CAPABILITY_RULES: list[dict] = [
    # --- Reasoning (Low/Medium complexity bypass) ---
    {
        "capability": "reasoning",
        "keywords": [
            "explain", "what is", "how does", "why is", "tell me about",
            "summarize", "analyze", "break down", "jwt", "token", "concept",
        ],
        "domain_hint": "general",
    },
    # --- Conversation (Low complexity bypass) ---
    {
        "capability": "conversation",
        "keywords": [
            "hello", "hi", "hey", "how are you", "what's up", "good morning",
            "good evening", "thanks", "thank you", "bye", "goodbye", "help",
            "joke", "translate", "funny", "who are you",
        ],
        "domain_hint": "general",
    },
    # --- Architecture ---
    {
        "capability": "architecture",
        "keywords": [
            "architect", "design", "system design", "microservice", "monolith",
            "saas", "platform", "scalable", "distributed", "event-driven",
            "infrastructure", "schema", "erd", "database design", "api design",
            "production", "enterprise", "high availability", "load balancer",
            "build netflix", "netflix architecture",
        ],
        "domain_hint": "web",
    },
    # --- Backend ---
    {
        "capability": "backend",
        "keywords": [
            "fastapi", "django", "flask", "express", "nestjs", "backend",
            "api", "rest", "graphql", "grpc", "server", "endpoint",
            "middleware", "route", "controller", "service layer",
            "crud", "todo", "auth", "jwt", "oauth", "webhook", "websocket",
        ],
        "domain_hint": "web",
    },
    # --- Frontend ---
    {
        "capability": "frontend",
        "keywords": [
            "react", "vue", "svelte", "angular", "next", "nuxt", "vite",
            "frontend", "ui", "component", "tailwind", "css", "html",
            "responsive", "dashboard", "landing page", "form", "modal",
            "sidebar", "navbar", "animation", "dark mode",
        ],
        "domain_hint": "web",
    },
    # --- Database ---
    {
        "capability": "database",
        "keywords": [
            "database", "postgres", "mysql", "mongodb", "redis", "sqlite",
            "supabase", "firebase", "prisma", "orm", "migration", "schema",
            "query", "sql", "nosql", "table", "index", "foreign key",
            "relationship", "seed", "data model",
        ],
        "domain_hint": "web",
    },
    # --- Security ---
    {
        "capability": "security",
        "keywords": [
            "security", "auth", "jwt", "oauth", "encryption", "hash",
            "password", "rbac", "permission", "role", "cors", "csrf",
            "xss", "injection", "vulnerability", "audit", "penetration",
            "cve", "ssl", "tls", "https", "firewall", "rate limit",
        ],
        "domain_hint": "security",
    },
    # --- Testing ---
    {
        "capability": "testing",
        "keywords": [
            "test", "pytest", "jest", "vitest", "cypress", "playwright",
            "unit test", "integration test", "e2e", "coverage", "tdd",
            "bdd", "mock", "fixture", "assertion", "spec",
        ],
        "domain_hint": "web",
    },
    # --- DevOps / CI/CD ---
    {
        "capability": "devops",
        "keywords": [
            "docker", "kubernetes", "k8s", "container", "ci/cd", "github actions",
            "pipeline", "deploy", "deployment", "nginx", "terraform", "ansible",
            "aws", "gcp", "azure", "cloud", "serverless", "lambda",
            "compose", "dockerfile", "helm", "monitoring", "logging",
        ],
        "domain_hint": "devops",
    },
    # --- Documentation ---
    {
        "capability": "documentation",
        "keywords": [
            "document", "documentation", "readme", "wiki", "api docs",
            "swagger", "openapi", "changelog", "guide", "tutorial",
            "describe", "write", "specification", "spec",
        ],
        "domain_hint": "docs",
    },
    # --- ML / AI ---
    {
        "capability": "ml",
        "keywords": [
            "machine learning", "ml", "ai", "model", "training", "inference",
            "neural", "deep learning", "pytorch", "tensorflow", "scikit",
            "nlp", "computer vision", "embedding", "fine-tune", "dataset",
            "prediction", "classification", "regression", "llm",
        ],
        "domain_hint": "ml",
    },
    # --- Mobile ---
    {
        "capability": "mobile",
        "keywords": [
            "mobile", "ios", "android", "react native", "flutter", "expo",
            "swift", "kotlin", "app store", "push notification",
        ],
        "domain_hint": "mobile",
    },
    # --- Performance ---
    {
        "capability": "performance",
        "keywords": [
            "performance", "optimize", "speed", "latency", "cache", "caching",
            "benchmark", "profiling", "memory leak", "bottleneck", "load test",
            "concurrent", "parallel", "async", "queue", "worker",
        ],
        "domain_hint": "web",
    },
    # --- Refactoring ---
    {
        "capability": "refactoring",
        "keywords": [
            "refactor", "clean", "restructure", "reorganize", "decouple",
            "solid", "dry", "kiss", "technical debt", "legacy",
            "modernize", "upgrade", "migrate",
        ],
        "domain_hint": "web",
    },
    # --- Research ---
    {
        "capability": "research",
        "keywords": [
            "research", "compare", "evaluate", "survey", "benchmark",
            "best practice", "state of the art", "alternative", "pros and cons",
            "tradeoff", "recommendation", "analysis",
        ],
        "domain_hint": "general",
    },
    # --- Code Review ---
    {
        "capability": "review",
        "keywords": [
            "review", "code review", "pull request", "pr", "feedback",
            "improve", "suggestion", "lint", "static analysis", "quality",
        ],
        "domain_hint": "web",
    },
]


def analyze(prompt: str) -> CapabilityAnalysis:
    """
    Analyze a user prompt and extract all required capabilities.

    This is a $0, <5ms operation — no LLM calls.
    """
    lower = prompt.lower()
    matched_capabilities: list[str] = []
    keywords_matched: list[str] = []
    domain_votes: dict[str, int] = {}

    for rule in CAPABILITY_RULES:
        cap = rule["capability"]
        for kw in rule["keywords"]:
            if kw in lower:
                if cap not in matched_capabilities:
                    matched_capabilities.append(cap)
                keywords_matched.append(f"{kw} → {cap}")
                # Vote for domain
                hint = rule.get("domain_hint", "general")
                domain_votes[hint] = domain_votes.get(hint, 0) + 1
                break  # One keyword match is enough per rule

    # If nothing matched, default to conversation (basic chat)
    if not matched_capabilities:
        matched_capabilities = ["conversation"]
        keywords_matched = ["(no match → default conversation)"]

    # Determine primary domain from votes
    domain = max(domain_votes, key=domain_votes.get) if domain_votes else "general"

    # Determine complexity from number of capabilities + keywords
    word_count = len(prompt.split())
    cap_count = len(matched_capabilities)
    production_keywords = {"production", "enterprise", "saas", "platform", "scalable", "microservice"}
    has_production = bool(production_keywords & set(lower.split()))

    if "conversation" in matched_capabilities and cap_count == 1:
        complexity = "Low"
    elif cap_count >= 5 or has_production:
        complexity = "High"
    elif cap_count >= 3 or word_count > 25:
        complexity = "Medium"
    elif cap_count == 1 and word_count < 10:
        complexity = "Low"
    else:
        complexity = "Medium"

    # Build intent description
    intent = _build_intent(matched_capabilities, domain)

    # Estimate agent count
    complexity_agent_map = {"Low": 1, "Medium": 3, "High": 5, "Critical": 8}
    estimated_agents = max(cap_count, complexity_agent_map.get(complexity, 3))

    is_simple_chat = complexity == "Low" and "conversation" in matched_capabilities

    return CapabilityAnalysis(
        prompt=prompt,
        intent=intent,
        domain=domain,
        complexity=complexity,
        capabilities=matched_capabilities,
        keywords_matched=keywords_matched,
        estimated_agents=estimated_agents,
        requires_verification=not is_simple_chat,
        requires_humanization=not is_simple_chat,
    )


def _build_intent(capabilities: list[str], domain: str) -> str:
    """Build a human-readable intent string from capabilities."""
    cap_labels = {
        "architecture": "System Architecture",
        "backend": "Backend Development",
        "frontend": "Frontend Development",
        "database": "Database Engineering",
        "security": "Security Engineering",
        "testing": "Quality Assurance",
        "devops": "DevOps & Deployment",
        "documentation": "Documentation",
        "ml": "Machine Learning",
        "mobile": "Mobile Development",
        "performance": "Performance Optimization",
        "refactoring": "Code Refactoring",
        "research": "Research & Analysis",
        "review": "Code Review",
    }

    labels = [cap_labels.get(c, c.title()) for c in capabilities[:3]]
    suffix = f" (+{len(capabilities) - 3} more)" if len(capabilities) > 3 else ""
    return " + ".join(labels) + suffix
