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

The `xanadTools` workspace MCP must expose semantic workflow tools, not arbitrary shell access.

Good MCP tools for `xanadTools` express a stable repo-owned action such as `lifecycle_inspect` or `workspace_run_check_loc`.

Bad `xanadTools` tools simply proxy generic host capabilities such as:

- arbitrary shell execution
- generic file read or file write
- generic web fetch
- generic git command passthrough

Those capabilities should remain native agent tools or domain-specific companion servers (e.g. `xanadWeb`, `xanadGit`) unless a narrower xanadAssistant-owned contract is required. Companion servers (`gitMcp.py`, `webMcp.py`, etc.) are separately scoped and security-reviewed under the tool-mcp-v1 contract — this Core Rule governs the `xanadTools` server only.

## Scope Rule

The first-party MCP surface should begin with one small local server and only split into multiple servers when domain boundaries become meaningfully different.

Recommended first domains:

- `lifecycle_*` for lifecycle engine entrypoints (implemented: `xanadTools`)
- `workspace_*` for repo-approved validation commands (implemented: `xanadTools`)
- `package_*` for generation and freshness workflows (deferred)

## V1 Server Shape

The initial shape is one workspace-local stdio MCP server (`xanadTools`), managed by the lifecycle engine and referenced from `.vscode/mcp.json`. Companion servers (`xanadGit`, `xanadWeb`, `xanadTime`, `xanadSecurity`, `xanadSQLite`, `xanadGitHub`, `xanadSequentialThinking`) are shipped alongside it and registered in the same MCP config.

The `xanadTools` initial tool set is:

- `lifecycle_inspect`
- `lifecycle_check`
- `lifecycle_interview`
- `lifecycle_plan_setup`
- `lifecycle_apply`
- `lifecycle_update`
- `lifecycle_repair`
- `lifecycle_factory_restore`
- `workspace_run_tests`
- `workspace_run_check_loc`
- `workspace_show_key_commands`
- `workspace_show_install_state`
- `workspace_validate_lockfile`

## Input Rule

Each MCP tool must accept structured inputs for the workflow it owns.

It must not accept a free-form command string when a narrower typed input can express the operation.

Examples:

- `quality.run_targeted_tests` may accept test module paths.
- `lifecycle_plan_setup` may accept workspace, package root, and non-interactive flags.
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