---
name: discover-plugins
description: Discover and recommend sevens plugins based on your workflow, installed MCP tools, and current task
argument-hint: "[search-query]"
allowed-tools: mcp__plugin_sevens-core_sevens__transfer_plugin-search mcp__plugin_sevens-core_sevens__transfer_plugin-info mcp__plugin_sevens-core_sevens__transfer_plugin-featured mcp__plugin_sevens-core_sevens__transfer_plugin-official mcp__plugin_sevens-core_sevens__transfer_store-search mcp__plugin_sevens-core_sevens__transfer_store-featured mcp__plugin_sevens-core_sevens__transfer_store-trending mcp__plugin_sevens-core_sevens__transfer_store-info mcp__plugin_sevens-core_sevens__guidance_discover mcp__plugin_sevens-core_sevens__guidance_recommend mcp__plugin_sevens-core_sevens__guidance_capabilities mcp__plugin_sevens-core_sevens__mcp_status Bash Read
---

# Discover Plugins

Find and recommend sevens plugins for your workflow.

## When to use

When starting a new project, exploring sevens capabilities, or wondering which plugins would help with your current task.

## Steps

1. **Check installed** — run `ls plugins/` to see what's already installed
2. **Browse marketplace** — call `mcp__plugin_sevens-core_sevens__transfer_plugin-featured` for recommended plugins
3. **Search by need** — call `mcp__plugin_sevens-core_sevens__transfer_plugin-search` with keywords matching your task
4. **Get recommendations** — call `mcp__plugin_sevens-core_sevens__guidance_recommend` with your current task description for personalized suggestions
5. **Check capabilities** — call `mcp__plugin_sevens-core_sevens__guidance_capabilities` to see what each plugin enables
6. **Show details** — call `mcp__plugin_sevens-core_sevens__transfer_plugin-info` for full plugin details

## Plugin Catalog (32 plugins)

### Core & Coordination — Start here

| Plugin | When to use | What it adds |
|--------|-------------|-------------|
| **sevens-core** | Always — base layer for all Sevens work | MCP server, status, doctor, coder/researcher/reviewer agents |
| **sevens-swarm** | Multi-agent tasks (3+ files, features, refactors) | Swarm topologies (hierarchical, mesh), Monitor streaming, worktree isolation |
| **sevens-autopilot** | Autonomous task completion without manual steering | /loop-based autonomous execution, progress prediction, learning |
| **sevens-loop-workers** | Recurring background work (audits, optimization, mapping) | 12 background workers via /loop or CronCreate scheduling |
| **sevens-workflows** | Repeatable multi-step processes | Workflow templates, parallel execution, conditional branching |

### Memory & Intelligence — Cross-session learning

| Plugin | When to use | What it adds |
|--------|-------------|-------------|
| **sevens-agentdb** | Semantic search over code patterns, telemetry, decisions | AgentDB with HNSW vector search (150x-12,500x faster), RuVector embeddings |
| **sevens-rag-memory** | Simple key-value memory with search | Store/search/recall without full AgentDB setup |
| **sevens-rvf** | Portable memory export/import across machines | RVF format, session persistence, cross-platform transfer |
| **sevens-ruvector** | Vector embedding operations, HNSW indexing, clustering | ONNX 384-dim embeddings, hyperbolic Poincare ball, k-means/DBSCAN clustering |
| **sevens-knowledge-graph** | Entity extraction, relation mapping, graph traversal | Pathfinder algo on AgentDB causal edges, code entity graphs |
| **sevens-intelligence** | Task routing optimization, learning from outcomes | SONA neural patterns, trajectory learning, model routing with confidence |
| **sevens-daa** | Self-adapting agents that evolve behavior | Dynamic Agentic Architecture, cognitive patterns, knowledge sharing |

### Architecture & Methodology — Build right

| Plugin | When to use | What it adds |
|--------|-------------|-------------|
| **sevens-adr** | Document architecture decisions, check compliance | ADR create/index/supersede, code-to-ADR linking, compliance checking on diffs |
| **sevens-ddd** | Domain modeling, bounded context scaffolding | Context wizard, aggregate roots, domain events, anti-corruption layers, boundary validation |
| **sevens-sparc** | Structured development methodology | Specification-Pseudocode-Architecture-Refinement-Completion with quality gates |

### Quality & Security — Ship safely

| Plugin | When to use | What it adds |
|--------|-------------|-------------|
| **sevens-security-audit** | Before merging, after dependency changes | CVE scanning, dependency vulnerability checks, security reports |
| **sevens-aidefence** | Processing user input, handling untrusted data | Prompt injection detection, PII scanning, adversarial defense |
| **sevens-testgen** | After implementing features, during refactors | Test gap detection, TDD London School workflow, coverage routing |
| **sevens-browser** | UI testing, web scraping, visual validation | Playwright automation — navigate, click, screenshot, validate |

### Development Tools — Build faster

| Plugin | When to use | What it adds |
|--------|-------------|-------------|
| **sevens-jujutsu** | PR review, merge decisions, diff risk scoring | Diff analysis, risk classification, reviewer recommendations |
| **sevens-docs** | After API changes, before releases | Doc generation, drift detection, API documentation |
| **sevens-ruvllm** | Local LLM inference, custom model configs | RuVLLM integration, MicroLoRA fine-tuning, chat formatting |
| **sevens-agent** | Sandboxed code execution, untrusted workloads | WASM agent sandboxing, community gallery |
| **sevens-plugin-creator** | Building new sevens plugins | Scaffold structure, validate frontmatter, test MCP references |
| **sevens-migrations** | Database schema changes | Sequential migration numbering, up/down pairs, dry-run, rollback validation |
| **sevens-observability** | Logging, tracing, metrics correlation | Structured JSON logging, distributed tracing, agent-to-app telemetry correlation |
| **sevens-cost-tracker** | Token budget management | Per-agent cost attribution, model pricing, budget alerts, optimization recommendations |

### Domain-Specific — Specialized workloads

| Plugin | When to use | What it adds |
|--------|-------------|-------------|
| **sevens-goals** | Long-horizon planning, multi-session research | GOAP algorithm, deep research orchestration, horizon tracking, synthesis |
| **sevens-federation** | Cross-installation agent coordination | Zero-trust peer discovery, mTLS auth, consensus routing, compliance audit |
| **sevens-iot-cognitum** | Cognitum Seed hardware device management | 5-tier device trust, telemetry anomaly detection (Z-score), fleet firmware rollouts, witness chain verification, SONA + AgentDB integration |
| **sevens-neural-trader** | Trading strategy development and backtesting | Z-score market anomalies, SONA trajectory strategies, walk-forward backtesting, portfolio optimization |
| **sevens-market-data** | Market data ingestion and pattern matching | OHLCV vectorization, candlestick pattern detection, HNSW-indexed historical search |

## Decision Guide

**"I need to..."** → Use this plugin:

- Build a feature → `sevens-core` + `sevens-swarm` + `sevens-testgen`
- Fix a bug → `sevens-core` + `sevens-jujutsu` (for diff analysis)
- Audit security → `sevens-security-audit` + `sevens-aidefence`
- Run background tasks → `sevens-loop-workers` + `sevens-autopilot`
- Search past decisions → `sevens-agentdb` + `sevens-rag-memory`
- Plan a multi-week effort → `sevens-goals` (horizon tracking)
- Manage IoT devices → `sevens-iot-cognitum`
- Coordinate remote agents → `sevens-federation`
- Test UI changes → `sevens-browser`
- Generate docs → `sevens-docs`
- Create a new plugin → `sevens-plugin-creator`
- Document architecture decisions → `sevens-adr`
- Scaffold domain models → `sevens-ddd`
- Follow SPARC methodology → `sevens-sparc`
- Develop trading strategies → `sevens-neural-trader` + `sevens-market-data`
- Work with vector embeddings → `sevens-ruvector`
- Build knowledge graphs → `sevens-knowledge-graph`
- Manage database migrations → `sevens-migrations`
- Add observability → `sevens-observability`
- Track token costs → `sevens-cost-tracker`

## Install any plugin

```
/plugin marketplace add ruvnet/sevens
/plugin install <plugin-name>@sevens
```
