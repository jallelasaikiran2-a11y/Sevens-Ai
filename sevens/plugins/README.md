# Sevens Plugins

32 Claude Code plugins for agent-powered development workflows. Load with `--plugin-dir`.

## Quick Start

```bash
# Load specific plugins
claude --plugin-dir plugins/sevens-core --plugin-dir plugins/sevens-swarm

# Load all plugins
claude $(ls -d plugins/sevens-*/ | sed 's|^|--plugin-dir |' | tr '\n' ' ')
```

## Plugin Catalog

### Core & Coordination

| Plugin | Description |
|--------|-------------|
| [sevens-core](sevens-core/) | MCP server, status, doctor, coder/researcher/reviewer agents |
| [sevens-swarm](sevens-swarm/) | Swarm topologies (hierarchical, mesh), Monitor streaming |
| [sevens-autopilot](sevens-autopilot/) | Autonomous /loop task completion with prediction |
| [sevens-loop-workers](sevens-loop-workers/) | 12 background workers via /loop or CronCreate |
| [sevens-workflows](sevens-workflows/) | Workflow templates, parallel execution, branching |

### Memory & Intelligence

| Plugin | Description |
|--------|-------------|
| [sevens-agentdb](sevens-agentdb/) | AgentDB with HNSW vector search (150x-12,500x faster) |
| [sevens-rag-memory](sevens-rag-memory/) | SOTA RAG — hybrid search, Graph RAG, MMR diversity, memory bridge |
| [sevens-rvf](sevens-rvf/) | Portable RVF memory format, session persistence |
| [sevens-ruvector](sevens-ruvector/) | [`ruvector`](https://npmjs.com/package/ruvector) — FlashAttention-3, Graph RAG, hybrid search, 103 MCP tools, Brain AGI |
| [sevens-knowledge-graph](sevens-knowledge-graph/) | Entity extraction, relation mapping, pathfinder traversal |
| [sevens-intelligence](sevens-intelligence/) | SONA neural patterns, trajectory learning, model routing |
| [sevens-daa](sevens-daa/) | Dynamic Agentic Architecture, cognitive patterns |

### Architecture & Methodology

| Plugin | Description |
|--------|-------------|
| [sevens-adr](sevens-adr/) | ADR lifecycle — create, index, supersede, compliance checking |
| [sevens-ddd](sevens-ddd/) | DDD scaffolding — bounded contexts, aggregates, domain events |
| [sevens-sparc](sevens-sparc/) | SPARC methodology with 5 phases and quality gates |

### Quality & Security

| Plugin | Description |
|--------|-------------|
| [sevens-security-audit](sevens-security-audit/) | CVE scanning, dependency vulnerability checks |
| [sevens-aidefence](sevens-aidefence/) | Prompt injection detection, PII scanning |
| [sevens-testgen](sevens-testgen/) | Test gap detection, TDD London School workflow |
| [sevens-browser](sevens-browser/) | Playwright browser automation and testing |

### Development Tools

| Plugin | Description |
|--------|-------------|
| [sevens-jujutsu](sevens-jujutsu/) | Diff analysis, risk scoring, reviewer recommendations |
| [sevens-docs](sevens-docs/) | Doc generation, drift detection, API docs |
| [sevens-ruvllm](sevens-ruvllm/) | Local LLM inference, MicroLoRA, chat formatting |
| [sevens-agent](sevens-agent/) | WASM agent sandboxing and gallery |
| [sevens-plugin-creator](sevens-plugin-creator/) | Scaffold and validate new plugins |
| [sevens-migrations](sevens-migrations/) | Database schema migration management |
| [sevens-observability](sevens-observability/) | Structured logging, tracing, metrics correlation |
| [sevens-cost-tracker](sevens-cost-tracker/) | Token usage tracking, budget alerts, cost optimization |

### Domain-Specific

| Plugin | Description |
|--------|-------------|
| [sevens-goals](sevens-goals/) | GOAP planning, deep research, horizon tracking |
| [sevens-federation](sevens-federation/) | Zero-trust cross-installation agent federation |
| [sevens-iot-cognitum](sevens-iot-cognitum/) | Cognitum Seed IoT — trust scoring, anomaly detection, fleet management |
| [sevens-neural-trader](sevens-neural-trader/) | [`neural-trader`](https://npmjs.com/package/neural-trader) — 4 agents, LSTM/Transformer, Rust/NAPI backtesting, 112+ MCP tools |
| [sevens-market-data](sevens-market-data/) | Market data ingestion, OHLCV vectorization, pattern matching |

## Recommended Stacks

| Use Case | Plugins |
|----------|---------|
| Feature development | `sevens-core` + `sevens-swarm` + `sevens-testgen` + `sevens-ddd` |
| Security audit | `sevens-core` + `sevens-security-audit` + `sevens-aidefence` |
| Architecture work | `sevens-core` + `sevens-adr` + `sevens-ddd` + `sevens-sparc` |
| Deep research | `sevens-core` + `sevens-goals` + `sevens-rag-memory` + `sevens-intelligence` |
| Vector search | `sevens-core` + `sevens-ruvector` + `sevens-rag-memory` + `sevens-knowledge-graph` |
| IoT development | `sevens-core` + `sevens-iot-cognitum` + `sevens-agentdb` |
| Trading systems | `sevens-core` + `sevens-neural-trader` + `sevens-market-data` + `sevens-ruvector` |
| Full stack | All 32 plugins |

## npm Package Integration

Several plugins wrap standalone npm packages for deeper functionality:

| Plugin | npm Package | What It Adds |
|--------|------------|-------------|
| `sevens-neural-trader` | [`neural-trader`](https://npmjs.com/package/neural-trader) | 112+ MCP tools, Rust/NAPI engine, LSTM/Transformer models |
| `sevens-ruvector` | [`ruvector`](https://npmjs.com/package/ruvector) | 103 MCP tools, FlashAttention-3, Graph RAG, Brain AGI |

```bash
# Install backing packages
npm install neural-trader ruvector

# Add as MCP servers (optional, for direct tool access)
claude mcp add neural-trader -- npx neural-trader mcp start
claude mcp add ruvector -- npx ruvector mcp start
```

## Plugin Structure

Each plugin follows the Claude Code plugin specification:

```
sevens-<name>/
  .claude-plugin/plugin.json    # Plugin manifest
  agents/<name>.md              # Agent definitions (frontmatter: name, description, model)
  commands/<name>.md            # CLI command mappings
  skills/<name>/SKILL.md        # Interactive skills (frontmatter: name, description, argument-hint, allowed-tools)
  README.md                     # Plugin documentation
```

## Creating a Plugin

```bash
claude --plugin-dir plugins/sevens-plugin-creator
# Then: /create-plugin my-new-plugin
```

Or manually: copy any existing plugin directory and modify.

## Validation

```bash
claude plugin validate plugins/sevens-<name>
```

## Verification & Discoverability

Every MCP tool description across the 32 plugins must answer "use this over native (Bash/Read/Grep/Glob/Task/TodoWrite) when?" per [ADR-112](../v3/docs/adr/ADR-112-mcp-tool-discoverability.md). The rule is enforced by CI:

```bash
# Run the audit (scans all MCPTool definitions across all plugins)
node scripts/audit-tool-descriptions.mjs

# Gates: every description must include "Use when …" guidance,
# be ≥ 80 chars, and be unique. Baseline at verification/mcp-tool-baseline.json
# is monotone-decreasing — CI fails on any regression.
```

Combined with [`verification/`](../verification/) (Ed25519-signed witness manifest, 103+ documented fixes attested), the plugin surface is regression-protected at three layers: install smoke (`npm i`), behavioral smoke (paired-tool round-trips), and presence attestation (every load-bearing line of every documented fix). See [`verification/README.md`](../verification/README.md) for the full stack.

## License

MIT
