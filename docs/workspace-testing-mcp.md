# workspaceTesting MCP — Current State

## Status

- Last reviewed: 2026-06-01
- Status: informative maintainer document
- Related contracts:
  - `docs/contracts/tool-mcp-boundary.md`
  - `docs/contracts/tool-mcp-v1.md`
- Background notes and prior planning have moved to `docs/archive/workspace-testing-mcp-background.md`

## Purpose

This document records the current `workspaceTesting` MCP surface and the constraints maintainers should preserve when changing it. It is intentionally limited to shipped behavior, current safeguards, and the validation surface that protects those behaviors.

## Architecture

`workspaceTesting` owns generic workspace test-running and coverage-parsing behavior.

- `xanadTools` keeps lifecycle and repo-maintenance tools such as `lifecycle_*` and `workspace_run_check_loc`
- `workspaceTesting` source lives in `mcp/scripts/` and is mirrored into `.github/mcp/scripts/` by the normal lifecycle update flow
- the current implementation is primarily in `mcp/scripts/workspaceTestingMcp.py` and `mcp/scripts/_workspace_testing_shared.py`

Focused coverage for this surface lives in:

- `tests/mcp_servers/test_workspace_testing_mcp.py`
- `tests/mcp_servers/_workspace_testing_mcp_support.py`
- `tests/mcp_servers/test_xanad_workspace_mcp_tools.py`

## Current Tool Surface

### `testing_show_key_commands`

Reads the `## Key Commands` table from `.github/copilot-instructions.md` and returns structured command entries.

- returns `ok` with `commands` and `summary` when commands are present
- returns `unavailable` when the workspace root is missing or the table cannot be found

### `testing_show_capabilities`

Reports runtime facts so agents can choose test scope intentionally.

- reports whether a declared `Run tests` command is available
- reports the detected runner, timeout policy, typed-targeting mode, coverage formats, and parsed output formats
- reports `supportsTestDiscovery=true` only for pytest-family commands

### `testing_list_tests`

Lists discovered test ids only when the declared runner supports deterministic argv-safe collection.

- returns `ok` with `testIds` and `total` for pytest-family commands using `--collect-only -q --no-header`
- returns `unavailable` for runners without a proven safe discovery mode, including this repo's current unittest command
- accepts optional `targetFiles` as argv-safe path filters

### `testing_run_tests`

Runs the workspace-declared `Run tests` command from `.github/copilot-instructions.md`.

Inputs:

- `scope` with the documented enum `default | full`
- `extraArgs`, `targetFiles`, and `testNames` as string arrays
- `parseOutput` as a boolean

Safeguards:

- rejects shell metacharacters in the declared command
- restricts execution to an allowlist of runner executables
- prefers `.venv/bin/python` when the declared command uses Python
- rejects `scope=full` when typed targets are also provided
- enforces a 300-second subprocess timeout and reports `runnerExitReason="timeout"` on expiry

Structured result fields:

- `status`
- `summary`
- `command`
- `exitCode`
- `runnerExitReason`
- `stdoutTail`
- `stderrTail`
- `testSummary` when `parseOutput=true`

`runnerExitReason` values currently include `completed`, `tests_failed`, `interrupted`, `internal_error`, `usage_error`, `no_tests_collected`, `runner_error`, and `timeout`.

### `testing_parse_coverage`

Parses a workspace-local Cobertura XML artifact into a structured summary.

- input: `coveragePath`, default `coverage.xml`
- output fields: `status`, `summary`, `coveragePath`, `lineRate`, `percentCovered`, `linesValid`, `linesCovered`, and `zeroCoverageFiles`

## Current Regression Coverage

The current automated checks cover these behaviors directly:

- source and managed-copy loading for the MCP server
- exported tool docstrings
- unresolved `Run tests` command handling
- shell-metacharacter rejection
- executable allowlist rejection
- `.venv` Python preference
- timeout classification for stuck subprocesses
- coverage XML success and out-of-workspace path rejection
- prompt-contract and interview references to `workspaceTesting`
- split-boundary behavior in remaining `xanadTools` MCP tests

The current regression history worth preserving is:

- invalid `scope` values are rejected instead of being treated as loosely accepted strings
- unittest skipped cases are not counted as passed in parsed summaries

## Maintainer Notes

- Keep this file limited to current behavior and durable maintainer guidance. Time-sensitive audit notes, research dumps, and phased implementation plans belong in archive docs.
- When changing MCP source files, refresh mirrored/generated artifacts through the normal repo flow before closing the work.
- Be cautious when expanding wrapper support or command execution breadth because this surface sits on the trust boundary for subprocess execution.

## Known Follow-up Areas

The main backlog items still worth separate design work are:

- richer runner compatibility beyond the current conservative allowlist and wrapper handling
- stronger capability signaling for targeted execution semantics
- richer structured outputs or artifact formats such as coverage JSON or per-test detail
- possible subprocess environment minimization and MCP roots integration

The archived background document keeps the prior audit notes, research links, and phased plan for those follow-up areas.
