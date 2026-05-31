# xanadAssistant Tool MCP V1

This document defines the first practical implementation slice for the xanadAssistant first-party tooling MCP.

## Status

This file is normative for the first executable slice of the tooling MCP.

## Transport

V1 transport is delegated to FastMCP via `uvx --from "mcp[cli]" mcp run`. Tool names must use the `[a-z0-9_-]` charset only; dots are not valid. The tool naming, I/O, and security contracts in this document remain normative.

## V1 Goal

Ship a small first-party MCP surface that is useful in consumer workspaces without requiring the full xanadAssistant package checkout to be present for every tool.

## Controlling Constraint

The managed MCP server script is installed into the consumer workspace as a local file under `.github/mcp/scripts/`.

That script must not assume that:

- the xanadAssistant repository checkout exists locally
- `xanadAssistant.py` is importable as a Python module
- the original package root can be rediscovered later

Because of that, V1 must avoid lifecycle tools that directly wrap the lifecycle CLI unless the workspace records a stable package-source contract for the MCP server to use.

## V1 Source Of Truth

V1 tools should derive workspace-approved commands from machine-readable or directly parseable files already managed into the workspace.

The primary source is the rendered `.github/copilot-instructions.md` file, especially the `Key Commands` section.

If a command is not present there, the tool must report `unavailable` rather than guessing.

Agent and prompt guidance should therefore treat MCP tools as the preferred path only when the matching server id is connected and the exported tool name is known exactly. If that condition is not met, the caller should use the documented fallback path instead of inventing a shell command.

## V1 Server Identity

The lifecycle-oriented workspace-local stdio server uses the concise first-party name `xanadTools`.

Generic test execution now lives in the separate `workspaceTesting` server because test running and coverage parsing are workspace-generic rather than xanadAssistant-specific.

The configured server id is part of the public integration surface. Agents and docs should reference exact server ids such as `xanadTools`, `workspaceTesting`, `security`, `devDocs`, `memory`, `time`, and `filesystem`, not internal implementation names or wildcard-style shorthand.

Resources, prompts, and apps are out of scope for the first executable slice.

## V1 Tools

### `testing_run_tests`

Purpose: run the workspace test command declared in `.github/copilot-instructions.md`.

Input schema:

- `scope`: optional enum: `default`, `full`
- `extraArgs`: optional string array, default empty
- `targetFiles`: optional string array, default empty; argv-safe file or test target paths
- `testNames`: optional string array, default empty; argv-safe framework test names
- `parseOutput`: optional boolean, default `true`; include a best-effort `testSummary`

Behavior: read the `Run tests` command from the instructions file; execute in the workspace root; return `unavailable` if the command is absent or unresolved (for example `(not detected)`); reject if typed target inputs are not string arrays; reject if `scope=full` is combined with `extraArgs`, `targetFiles`, or `testNames` because full scope runs the declared command exactly.

Output: `status` (`ok`, `failed`, `unavailable`), `command`, `exitCode`, `summary`, `stdoutTail`, `stderrTail`, and when `parseOutput=true`, `testSummary` with best-effort `format`, `passed`, `failed`, `errors`, `total`, and `firstFailure` fields.

### `workspace_run_check_loc`

Purpose: run the repo LOC gate when explicitly present.

Input schema: no arguments.

Behavior: prefer a known repo-local command from the instructions file; in xanadAssistant's own repo this resolves to `python3 scripts/check_loc.py`; return `unavailable` in consumer workspaces without a declared LOC command.

Output: `status`, `command`, `exitCode`, `summary`.

### `testing_parse_coverage`

Purpose: parse a workspace-local Cobertura `coverage.xml` artifact into a structured summary.

Input schema:

- `coveragePath`: optional string, default `coverage.xml`; must resolve to a file inside the workspace root

Behavior: parse the coverage XML locally; return `unavailable` if the path is missing or outside the workspace; return `failed` if the XML is malformed.

Output: `status`, `summary`, `coveragePath`, `lineRate`, `percentCovered`, `linesValid`, `linesCovered`, `zeroCoverageFiles`.

### `testing_show_key_commands`

Purpose: return commands from `.github/copilot-instructions.md` so the agent can reason from explicit workspace policy instead of scraping markdown ad hoc.

Input schema: no arguments.

Behavior: parse the `Key Commands` table; return discovered entries as structured name/value pairs; return `unavailable` if the file is absent or malformed.

Output: `status`, `commands` (array of `{label, command}`), `summary`.

### `workspace_show_key_commands`

Purpose: return commands from `.github/copilot-instructions.md` for repo-maintenance workflows owned by `xanadTools`.

Input schema: no arguments.

Behavior: parse the `Key Commands` table; return discovered entries as structured name/value pairs; return `unavailable` if the file is absent or malformed.

Output: `status`, `commands` (array of `{label, command}`), `summary`.

### Lifecycle Tools — Shared Contract

All supported lifecycle tools share the same package-resolution rules.

**Shared input schema** (all fields optional):

- `packageRoot`: path to a local xanadAssistant checkout
- `source`: package source string such as `github:owner/repo`
- `version`: release version for GitHub release resolution
- `ref`: Git ref for GitHub ref resolution

**Package-root resolution order:**

1. `packageRoot` argument — validate as local xanadAssistant checkout
2. `.github/xanadAssistant-lock.json` `package.packageRoot`
3. `source` + `version`/`ref` from tool input or lockfile `package` block

If the caller explicitly passes `packageRoot` and that path is invalid, return `unavailable` instead of falling back to later resolution steps.

For GitHub sources, use the package cache when present; otherwise download the release tarball or perform a shallow clone into the cache. Return `unavailable` when no usable local package root or supported remote source can be resolved safely.

**Shared output fields:** `status` (`ok`, `failed`, `unavailable`), `command`, `exitCode`, `payload` (parsed lifecycle JSON), `summary`.

### `lifecycle_inspect`

Run `xanadAssistant.py inspect --workspace <workspace-root> --package-root <resolved-root> --json`. No additional inputs beyond the shared schema.

### `lifecycle_interview`

Additional input: `mode` — optional enum: `setup`, `update`, `repair`, `factory-restore`.

Run `xanadAssistant.py interview --mode <mode> --json`.

### `lifecycle_plan_setup`

Additional inputs: `answersPath` (string path), `nonInteractive` (boolean).

Run `xanadAssistant.py plan setup --json` with optional `--answers` / `--non-interactive` flags.

### `lifecycle_setup`

Additional inputs: `planPath` (string path), `dryRun` (boolean).

Run `xanadAssistant.py setup --json` with optional `--plan`, `--dry-run` flags.

### `lifecycle_check`

Run `xanadAssistant.py health-check --json`. No additional inputs beyond the shared schema.

### Retired Tool Tombstones

`lifecycle_apply` is retired from the supported MCP contract.

If a runtime compatibility stub remains present, it must return `unavailable` with migration guidance pointing callers to `lifecycle_setup`, `lifecycle_update`, `lifecycle_repair`, or `lifecycle_factory_restore`.

## Extended Tools

These tools were originally deferred from the initial V1 slice but are now fully implemented
in `xanadWorkspaceMcp.py` and registered in the MCP config.

### `lifecycle_update`

Run `xanadAssistant.py update --json`. No additional inputs beyond the shared schema.

### `lifecycle_repair`

Run `xanadAssistant.py repair --json`. No additional inputs beyond the shared schema.

### `lifecycle_factory_restore`

Run `xanadAssistant.py factory-restore --json`. No additional inputs beyond the shared schema.

### `workspace_show_install_state`

Return the current lifecycle install state for the workspace without the full `health-check` payload. Input: no arguments beyond optional `packageRoot`. Output should include `installState` and the lifecycle `status` (`clean` or `drift`).

### `workspace_validate_lockfile`

Validate the xanadAssistant lockfile at `.github/xanadAssistant-lock.json`. Input: no arguments.

The following tools from the original deferred list remain unimplemented:

- `package_generate` — requires contributor-repo assets not available in consumer workspaces
- `package_check_manifest_freshness` — same constraint as `package_generate`

## xanadMemory Companion Server

`memoryMcp.py` (`xanadMemory`) is a managed companion server providing persistent, scoped, SQLite-backed agent memory — advisory facts, authoritative rules, and FTS-indexed diary. It ships as `.github/mcp/scripts/memoryMcp.py` and is registered as the `memory` server in `.vscode/mcp.json`.

Transport: stdio via `uvx --from "mcp[cli]" mcp run`. DB: `WORKSPACE_ROOT/.github/xanadAssistant/memory/memory.db`. Security assumptions follow the `tool-mcp-boundary.md` companion server contract.

## Security Rules

V1 tools must follow these restrictions:

- only execute commands discovered from managed workspace instructions or hardcoded first-party repo contracts
- never accept an arbitrary command string from the agent
- execute from the workspace root only
- return bounded output excerpts rather than full unbounded terminal dumps
- only make outbound network calls for explicit or lockfile-recorded lifecycle source resolution

## Failure Model

When a tool cannot safely resolve its underlying command, it must return `unavailable` with an explanation.

It must not fall back to inferred shell commands.

That rule applies symmetrically to agent guidance: when the preferred MCP tool is unavailable, the fallback must be an explicit documented native tool or CLI path, not an improvised shell equivalent.

## Upgrade Path

Lifecycle tools may be added in a later slice only after xanadAssistant records a stable package-source contract that the workspace-local MCP server can use safely and deterministically.

The current lifecycle MCP slice supports explicit local package roots, installed lockfiles that record `package.packageRoot`, and explicit or lockfile-recorded GitHub `source` plus `version` or `ref` values.
