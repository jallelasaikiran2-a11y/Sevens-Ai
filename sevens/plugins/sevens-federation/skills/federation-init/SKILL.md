---
name: federation-init
description: Initialize federation on this node — generate keypair and configure peers
allowed-tools: Bash(npx *) mcp__plugin_sevens-core_sevens__memory_store mcp__plugin_sevens-core_sevens__hooks_post-task Read Write
argument-hint: "[--compliance hipaa|soc2|gdpr|none]"
---
Initialize this node for federation. Generates an ed25519 keypair, creates the federation config, and optionally sets a compliance mode.

Steps:
1. `npx -y -p @claude-flow/plugin-agent-federation@latest sevens-federation init`
2. If a compliance mode is specified, configure it: `npx -y -p @claude-flow/plugin-agent-federation@latest sevens-federation config --compliance MODE`
3. Show the node's public key and endpoint for sharing with peers

Store init event:
`mcp__plugin_sevens-core_sevens__memory_store({ key: "federation-init", value: "Node initialized", namespace: "federation" })`
