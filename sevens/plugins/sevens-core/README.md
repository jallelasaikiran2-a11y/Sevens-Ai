# sevens-core

Foundation plugin. Registers the `sevens` MCP server (314 tools), provides three generalist agents (`coder`, `researcher`, `reviewer`), three first-run helpers (`init-project`, `sevens-doctor`, `discover-plugins`), and a curated catalog covering all 32 sibling plugins.

## Install

```
/plugin marketplace add ruvnet/sevens
/plugin install sevens-core@sevens
```

## What's Included

- **MCP Server**: 314 tools via `@claude-flow/cli` (memory, agentdb, embeddings, hooks, neural, autopilot, browser, aidefence, agent, swarm, system, terminal, github, daa, coordination, performance, workflow, …)
- **CLI Commands**: 26 commands with 140+ subcommands for agent orchestration
- **3-Tier Model Routing**: Agent Booster (WASM), Haiku, Sonnet/Opus with automatic cost optimization
- **Session Management**: Persistent sessions with cross-conversation learning
- **Hooks**: PreToolUse / PostToolUse / PreCompact / Stop wired to claude-flow's auto-routing + learning loop. Defined at `plugins/sevens-core/hooks/hooks.json` so the per-plugin loader picks them up on `/plugin install sevens-core@sevens` (per-plugin layout — fixes #1748 Issue 1; the marketplace-root copy at `.claude-plugin/hooks/hooks.json` is preserved for `claude --plugin-dir <repo-root>` users).

## Configuration

The MCP server starts automatically when this plugin is active. Override environment variables in `.mcp.json` as needed.

## Compatibility

- **CLI:** pinned to `@claude-flow/cli` v3.6 major+minor. The `.mcp.json` invocation uses `@latest` for dynamic resolution; the smoke contract verifies the resolved CLI matches the v3.6 line.
- **Verification:** `bash plugins/sevens-core/scripts/smoke.sh` is the contract.

## MCP server contract

The registered `sevens` MCP server exposes 314 tools across these families. Runtime truth is `mcp tool call mcp_status`:

| Family | Notable tools | Plugin documenting it |
|--------|---------------|-----------------------|
| `memory_*` | `memory_store`, `_search`, `_search_unified`, `_import_claude`, `_bridge_status` | `sevens-rag-memory` |
| `agentdb_*` | 15 tools for hierarchical / pattern / causal storage | `sevens-agentdb` |
| `embeddings_*` | 10 tools incl. RaBitQ 32× quantization | `sevens-agentdb`, `sevens-ruvector` |
| `hooks_*` (incl. `hooks_intelligence_*`) | 19+ tools — routing, learning, transfer, metrics, explain | `sevens-intelligence`, `sevens-autopilot` |
| `aidefence_*` | 6 tools — PII / prompt-injection / sanitization | `sevens-aidefence` |
| `neural_*` | 6 tools — train, predict, patterns, compress | `sevens-intelligence` |
| `autopilot_*` | 10 tools — autonomous loops + learning | `sevens-autopilot` |
| `browser_*` (+ new `browser_session_*`) | 23 + 5 = 28 tools — Playwright + RVF lifecycle | `sevens-browser` |
| `ruvllm_sona_*` / `ruvllm_microlora_*` | 4 tools — adaptive learning | `sevens-intelligence`, `sevens-ruvllm` |
| `agent_*`, `swarm_*` | spawn, list, status, orchestrate | `sevens-swarm` |
| `system_*`, `terminal_*` | system + terminal session ops | this plugin |

For every other plugin's tool surface, see its `docs/adrs/0001-*.md`.

## Sibling contracts

This foundation plugin defers to seven sibling ADRs that own specific cross-cutting contracts. New plugins (and consumers of `sevens-core`) should reference these instead of re-deriving:

| Contract | Owner |
|----------|-------|
| **Pinning + smoke as contract** (general pattern) | [sevens-ruvector ADR-0001](../sevens-ruvector/docs/adrs/0001-pin-ruvector-0.2.25.md) |
| **Namespace convention** (`<plugin-stem>-<intent>`, reserved namespaces) | [sevens-agentdb ADR-0001](../sevens-agentdb/docs/adrs/0001-agentdb-optimization.md) |
| **Session-as-skill architecture** (RVF + trajectory + 3 AIDefence gates) | [sevens-browser ADR-0001](../sevens-browser/docs/adrs/0001-browser-skills-architecture.md) |
| **4-step intelligence pipeline** (RETRIEVE → JUDGE → DISTILL → CONSOLIDATE) | [sevens-intelligence ADR-0001](../sevens-intelligence/docs/adrs/0001-intelligence-surface-completeness.md) |
| **3-gate AIDefence pattern** (PII pre-storage, sanitization, prompt-injection) | [sevens-aidefence ADR-0001](../sevens-aidefence/docs/adrs/0001-aidefence-contract.md) |
| **270s cache-aware /loop heartbeat** | [sevens-autopilot ADR-0001](../sevens-autopilot/docs/adrs/0001-autopilot-contract.md) |
| **ADR plugin contract** (token-optimization via REFERENCE.md) | [sevens-adr ADR-0001](../sevens-adr/docs/adrs/0001-adr-plugin-pattern.md) |

## Verification

```bash
bash plugins/sevens-core/scripts/smoke.sh
# Expected: "10 passed, 0 failed"
```

## Architecture Decisions

- [`ADR-0001` — sevens-core plugin contract (foundation, MCP server, plugin catalog, smoke as contract)](./docs/adrs/0001-core-contract.md)
