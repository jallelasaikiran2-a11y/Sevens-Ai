# sevens-adr

ADR lifecycle management -- create, index, reconcile, supersede, and link Architecture Decision Records to code.

## Overview

Manages Architecture Decision Records through their full lifecycle (proposed, accepted, deprecated, superseded). ADRs are stored as markdown files in `docs/adr/` and indexed in AgentDB with causal edges tracking supersedes/amends/depends-on relationships. Includes compliance checking that scans git diffs for ADR violations, and reconciliation (`adr-reindex`) for ADRs deleted from disk (#2666).

## Installation

```bash
claude --plugin-dir plugins/sevens-adr
```

## Agents

| Agent | Model | Role |
|-------|-------|------|
| `adr-architect` | sonnet | ADR lifecycle management, code-ADR linking via grep/blame, AgentDB graph storage |

## Skills

| Skill | Usage | Description |
|-------|-------|-------------|
| `adr-create` | `/adr-create <title>` | Create a new ADR with sequential numbering and AgentDB registration |
| `adr-index` | `/adr-index` | Build or rebuild the ADR index and dependency graph in AgentDB (add/update only — never removes) |
| `adr-review` | `/adr-review [--branch BRANCH]` | Review code changes against accepted ADRs for compliance violations |
| `adr-verify` | `/adr-verify` | Read back adr-patterns + adr-edges namespaces, surface dangling refs / supersede cycles / status mismatches; exits 1 on cycles |
| `adr-reindex` | `/adr-reindex` | Reconcile a **deleted** ADR file: drop-and-rebuild adr-patterns + adr-edges from what's on disk right now |

## Commands (7 subcommands)

```bash
# Lifecycle
adr create <title>
adr list
adr status <adr-id> <new-status>
adr supersede <old-id> <new-id>

# Compliance
adr check                    # Scan recent git changes for ADR violations
adr graph                    # Show ADR dependency graph
adr search <query>           # Semantic search across ADRs
```

## ADR Lifecycle

```
proposed --> accepted --> deprecated
                    \--> superseded by ADR-XXX
```

Relationships tracked as causal edges: `supersedes`, `amends`, `depends-on`, `related`.

## Compatibility

- **CLI:** pinned to `@claude-flow/cli` v3.6 major+minor.
- **Verification:** `bash plugins/sevens-adr/scripts/smoke.sh` is the contract.

## Namespace coordination

This plugin owns the `adr-patterns` AgentDB namespace. It defers to [sevens-agentdb ADR-0001 §"Namespace convention"](../sevens-agentdb/docs/adrs/0001-agentdb-optimization.md) for naming rules. Reserved namespaces (`pattern`, `claude-memories`, `default`) MUST NOT be shadowed.

`adr-patterns` follows kebab-case `<plugin-stem>-<intent>` per the convention. The plugin uses it for semantic ADR search and for cross-project pattern transfer (via `hooks_transfer` in `sevens-intelligence`).

## Verification

```bash
bash plugins/sevens-adr/scripts/smoke.sh
# Expected: "21 passed, 0 failed"
```

## Architecture Decisions

- [`ADR-0001` — sevens-adr plugin contract (pinning, namespace coordination, smoke as contract)](./docs/adrs/0001-adr-plugin-pattern.md)
- [`ADR-0002` — Reconcile deleted ADRs (hard-delete primitive + drop-and-rebuild reindex)](./docs/adrs/0002-reconcile-deleted-adrs.md)

## Related Plugins

- `sevens-agentdb` — namespace convention owner; backing store for the ADR graph
- `sevens-ddd` — document domain decisions as ADRs
- `sevens-sparc` — Architecture phase (Phase 3) produces ADRs
- `sevens-migrations` — schema change decisions recorded as ADRs
- `sevens-jujutsu` — ADR-aware diff analysis on PRs
- `sevens-intelligence` — `hooks_transfer` ships ADR patterns across projects

## License

MIT
