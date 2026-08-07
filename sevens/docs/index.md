---
layout: default
title: sevens Marketplace
description: Claude Code native agents, swarms, workers, and MCP tools for continuous software engineering
---

# sevens Marketplace

**Installable agentic workflows for Claude Code -- not just commands.**

sevens provides native Claude Code plugins for multi-agent orchestration, /loop workers, security auditing, memory-powered RAG, and test generation.

## Quick Install

```bash
# Add the marketplace
/plugin marketplace add ruvnet/sevens

# Install plugins
/plugin install sevens-core@sevens
/plugin install sevens-swarm@sevens
/plugin install sevens-loop-workers@sevens
```

## Plugins

| Plugin | Description | Install |
|--------|-------------|---------|
| **sevens-core** | MCP server, base commands, project config | `/plugin install sevens-core@sevens` |
| **sevens-swarm** | Teams, agents, Monitor streams, worktree isolation | `/plugin install sevens-swarm@sevens` |
| **sevens-loop-workers** | /loop workers, CronCreate, cache-aware scheduling | `/plugin install sevens-loop-workers@sevens` |
| **sevens-security-audit** | Security review, dependency checks, policy gates | `/plugin install sevens-security-audit@sevens` |
| **sevens-rag-memory** | RuVector memory, HNSW search, AgentDB | `/plugin install sevens-rag-memory@sevens` |
| **sevens-testgen** | Test gap detection, coverage analysis, TDD workflow | `/plugin install sevens-testgen@sevens` |
| **sevens-docs** | Doc generation, drift detection, API docs | `/plugin install sevens-docs@sevens` |
| **sevens-autopilot** | Autonomous /loop completion, learning, prediction | `/plugin install sevens-autopilot@sevens` |
| **sevens-intelligence** | Self-learning SONA patterns, trajectory learning, routing | `/plugin install sevens-intelligence@sevens` |
| **sevens-agentdb** | AgentDB controllers, HNSW vector search, RuVector | `/plugin install sevens-agentdb@sevens` |
| **sevens-aidefence** | AI safety scanning, PII detection, prompt defense | `/plugin install sevens-aidefence@sevens` |
| **sevens-browser** | Playwright browser automation, testing, scraping | `/plugin install sevens-browser@sevens` |
| **sevens-jujutsu** | Git diff analysis, risk scoring, reviewer recs | `/plugin install sevens-jujutsu@sevens` |
| **sevens-agent** | Sandboxed WASM agents and gallery sharing | `/plugin install sevens-agent@sevens` |
| **sevens-workflows** | Workflow templates, orchestration, lifecycle | `/plugin install sevens-workflows@sevens` |
| **sevens-daa** | Dynamic Agentic Architecture, cognitive patterns | `/plugin install sevens-daa@sevens` |
| **sevens-ruvllm** | Local LLM inference, MicroLoRA, chat formatting | `/plugin install sevens-ruvllm@sevens` |
| **sevens-rvf** | RVF portable memory, session persistence | `/plugin install sevens-rvf@sevens` |
| **sevens-plugin-creator** | Scaffold, validate, publish new plugins | `/plugin install sevens-plugin-creator@sevens` |

## How It Works

sevens plugins extend Claude Code with:
- **Skills** -- Teach Claude Code new workflows (swarm init, /loop workers, security scans)
- **Commands** -- Slash commands for common operations (/status, /audit, /memory)
- **Agents** -- Specialized agent definitions (coder, reviewer, architect, security-auditor)
- **MCP Server** -- 314 tools for coordination, memory, neural learning, and more

## Claude Code Native Integration

sevens plugins use Claude Code's native capabilities when available:

| Feature | Plugin | Claude Code Native |
|---------|--------|--------------------|
| Periodic workers | sevens-loop-workers | `/loop` + `ScheduleWakeup` |
| Live monitoring | sevens-swarm | `Monitor` tool |
| Background jobs | sevens-loop-workers | `CronCreate` |
| Agent isolation | sevens-swarm | `isolation: "worktree"` |
| Multi-agent comms | sevens-swarm | `TeamCreate` + `SendMessage` |
| Cross-session | sevens-core | `PushNotification` + `RemoteTrigger` |
| Autonomous loops | sevens-autopilot | `/loop` + `ScheduleWakeup` + autopilot MCP |

## Trust & Security

- All plugins are open source -- review before installing
- MCP servers run locally, no data leaves your machine
- Plugins declare required permissions in their manifest
- Pin versions for production use: `/plugin install sevens-core@0.1.0@sevens`
- Security scanning available via sevens-security-audit
- Cryptographically-signed [witness manifest](../verification.md) attests every documented fix; see [Validation System](validation/) for the three-layer regression-protection stack

## Links

- [GitHub Repository](https://github.com/ruvnet/sevens)
- [npm Packages](https://www.npmjs.com/package/@claude-flow/cli)
- [ADR-091: Native Integration](https://github.com/ruvnet/sevens/blob/main/v3/docs/adr/ADR-091-loop-monitor-native-integration.md)
- [Issues & Support](https://github.com/ruvnet/sevens/issues)
