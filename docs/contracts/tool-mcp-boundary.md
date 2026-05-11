# xanadAssistant Tool MCP Boundary

This document defines the boundary for xanadAssistant first-party MCP tooling.

## Status

This file is normative for first-party MCP design and future implementation slices.

## Purpose

xanadAssistant may provide its own concise library of first-party MCP servers so the package owns:

- tool names
- tool input and output schemas
- trust and security assumptions
- compatibility across supported Copilot surfaces
- versioned behavior tied to package releases

The goal is not to collect generic third-party tools. The goal is to expose stable, repo-owned workflows through a small, inspectable MCP surface.

## Core Rule

A xanadAssistant MCP must expose semantic workflow tools, not arbitrary shell access.

Good MCP tools express a stable repo-owned action such as `lifecycle.inspect` or `quality.check_loc`.

Bad MCP tools simply proxy generic host capabilities such as:

- arbitrary shell execution
- generic file read or file write
- generic web fetch
- generic git command passthrough

Those capabilities should remain native agent tools unless a narrower xanadAssistant-owned contract is required.

## Scope Rule

The first-party MCP surface should begin with one small local server and only split into multiple servers when domain boundaries become meaningfully different.

Recommended first domains:

- `lifecycle.*` for lifecycle engine entrypoints
- `quality.*` for repo-approved validation commands
- `package.*` for generation and freshness workflows

## V1 Server Shape

The initial shape should be one workspace-local stdio MCP server, managed by the lifecycle engine and referenced from `.vscode/mcp.json`.

The recommended identity is a first-party name such as `xanad-tools` or `xanad-workspace-tools`.

V1 should stay intentionally small. A suitable initial tool set is:

- `lifecycle.inspect`
- `lifecycle.check`
- `lifecycle.plan_setup`
- `lifecycle.apply`
- `lifecycle.update`
- `lifecycle.repair`
- `lifecycle.factory_restore`
- `quality.run_targeted_tests`
- `quality.run_full_tests`
- `quality.check_loc`
- `package.generate`
- `package.check_manifest_freshness`

## Input Rule

Each MCP tool must accept structured inputs for the workflow it owns.

It must not accept a free-form command string when a narrower typed input can express the operation.

Examples:

- `quality.run_targeted_tests` may accept test module paths.
- `lifecycle.plan_setup` may accept workspace, package root, and non-interactive flags.
- `package.generate` should not accept arbitrary subprocess arguments.

## Output Rule

Each MCP tool must return machine-readable structured output.

At minimum, tool outputs should make these states explicit when relevant:

- whether the tool succeeded
- exit code or equivalent status
- which canonical workflow was executed
- key artifacts produced
- concise summaries safe for agent consumption

Tool outputs should not require Copilot to scrape decorative terminal text.

## Security Rule

First-party MCP tools must be narrowly privileged and explicitly documented.

Requirements:

- no hardcoded secrets in MCP configuration or server code
- no undocumented outbound network access
- no arbitrary path traversal outside the intended workspace or package boundary
- no implicit execution of user-provided shell fragments
- trust assumptions documented for local and sandboxed execution

If a tool needs network access, that access must be explicit in the server documentation and configuration assumptions.

## Installation Rule

Lifecycle correctness must not depend on the MCP server being available.

- The lifecycle CLI remains authoritative for inspect, check, plan, apply, update, repair, and restore.
- A default install may include a managed first-party MCP entry.
- Disabling or removing the MCP server must not make the workspace lifecycle state incorrect.

## Anti-Bloat Rule

Do not use a first-party MCP to reintroduce the old heartbeat or pulse architecture through a different transport.

The MCP must not become:

- a hidden routing engine
- a large background state tracker
- a catch-all utility drawer
- a second lifecycle authority parallel to the CLI

If a capability is large, noisy, or optional, prefer a skill, pack, or dedicated server later rather than bloating the initial tooling MCP.

## Evolution Rule

Add a new first-party MCP tool only when all of the following are true:

- the workflow is repo-specific or package-specific
- the behavior is stable enough to deserve a named contract
- the security boundary is narrower than a generic host tool
- the tool improves cross-surface reuse or agent reliability

If those conditions are not met, keep the workflow as native agent behavior instead.