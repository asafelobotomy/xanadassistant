# workspaceTesting MCP — Current State and Enhancement Opportunities

## Status

- Last reviewed: 2026-05-31
- Status: informative maintainer document
- Related contracts:
  - `docs/contracts/tool-mcp-boundary.md`
  - `docs/contracts/tool-mcp-v1.md`

## Purpose

This document captures the current `workspaceTesting` MCP surface, the findings from the latest testing-infrastructure audit, and source-backed enhancement ideas for future implementation.

It is intended for xanadAssistant maintainers working on the MCP surface, contributors extending workspace-generic testing support, and authors of skills, prompts, or evals that reference `workspaceTesting`.

## Architecture and Split Rationale

`workspaceTesting` exists because generic workspace test execution is a different domain from xanadAssistant lifecycle and repo-maintenance workflows.

- `xanadTools` keeps lifecycle and repo-owned maintenance tools such as `lifecycle_*` and `workspace_run_check_loc`.
- `workspaceTesting` owns generic test-running and coverage-parsing behavior.
- Source files live under `mcp/scripts/` and are mirrored into `.github/mcp/scripts/` by the lifecycle update flow.

Current source files:

- `mcp/scripts/workspaceTestingMcp.py`
- `mcp/scripts/_workspace_testing_shared.py`

Current focused tests:

- `tests/mcp_servers/test_workspace_testing_mcp.py`
- `tests/mcp_servers/_workspace_testing_mcp_support.py`
- `tests/mcp_servers/test_xanad_workspace_mcp_tools.py`

## Current Tool Surface

### `testing_show_key_commands`

Reads the `## Key Commands` table from `.github/copilot-instructions.md` and returns discovered commands as structured entries.

Current behavior:

- returns `ok` with `commands` and `summary` when commands are present
- returns `unavailable` when the workspace root is missing or the table cannot be found

### `testing_show_capabilities`

Reports `workspaceTesting` runtime facts so agents can choose test scope and output handling intentionally.

Current behavior:

- returns `ok` with detected runner and static feature flags when the workspace root is valid
- reports whether a declared `Run tests` command is available
- reports timeout policy, typed-targeting mode, test-discovery support, coverage formats, and parsed output formats

Current discovery rule:

- `supportsTestDiscovery` is intentionally conservative and is currently `true` only for pytest-family commands

### `testing_list_tests`

Lists discovered test ids only when the declared runner supports deterministic argv-safe collection.

Current behavior:

- returns `ok` with `testIds` and `total` for pytest-family commands using `--collect-only -q --no-header`
- returns `unavailable` for runners without a proven safe discovery mode, including the repo's current unittest command
- accepts optional `targetFiles` as argv-safe path filters

### `testing_run_tests`

Runs the workspace-declared `Run tests` command from `.github/copilot-instructions.md`.

Current inputs:

- `scope`: intended contract is `default | full`
- `extraArgs`: string array
- `targetFiles`: string array
- `testNames`: string array
- `parseOutput`: boolean

Current safeguards:

- rejects shell metacharacters in the declared command
- restricts execution to an allowlist of runner executables
- prefers `.venv/bin/python` when the declared command uses Python
- rejects `scope=full` when extra typed targets are also provided

Current output shape:

- `status`
- `summary`
- `command`
- `exitCode`
- `runnerExitReason`
- `stdoutTail`
- `stderrTail`
- `testSummary` when `parseOutput=true`

Current `testSummary` fields:

- `format`
- `passed`
- `failed`
- `errors`
- `total`
- `firstFailure`

Current `runnerExitReason` values:

- `completed`
- `tests_failed`
- `interrupted`
- `internal_error`
- `usage_error`
- `no_tests_collected`
- `runner_error`
- `timeout`

### `testing_parse_coverage`

Parses a workspace-local Cobertura XML artifact into a structured summary.

Current inputs:

- `coveragePath`, default `coverage.xml`

Current output shape:

- `status`
- `summary`
- `coveragePath`
- `lineRate`
- `percentCovered`
- `linesValid`
- `linesCovered`
- `zeroCoverageFiles`

## Current Test and Validation Coverage

Current automated checks cover:

- source and managed-copy loading for the new MCP server
- exported tool docstrings
- unresolved `Run tests` command handling
- shell-metacharacter rejection
- executable allowlist rejection
- `.venv` Python preference
- coverage XML success path
- out-of-workspace coverage path rejection
- prompt-contract and interview references to `workspaceTesting`
- split-boundary behavior in the remaining `xanadTools` MCP tests

Recent directly relevant validation passed during the audit cycle:

- focused MCP tests
- prompt-contract tests
- interview question tests
- full `scripts/drift_preflight.py`

## Resolved Audit Findings

The 2026-05-31 audit originally found these issues. Both have since been fixed and are kept here as historical context for the regression coverage.

### 1. Invalid `scope` values were accepted

Severity: medium

The contract documents `scope` as the enum `default | full`, and `testing_run_tests` now rejects other values with `status="unavailable"`.

Current status:

- `scope="bogus"` is rejected and covered by focused regression tests

Why it matters:

- runtime behavior is looser than the documented contract
- callers cannot rely on schema-level validation for this field

Resolution:

- reject any scope outside `default` and `full`
- keep the focused regression test for an invalid enum value

### 2. Unittest skipped cases were overcounted as passed

Severity: medium

`parse_test_summary()` now subtracts skipped unittest cases from the reported pass count for output shaped like `OK (skipped=1)`.

Why it matters:

- agent-readable summaries become inaccurate
- downstream reasoning about test health can be misleading

Resolution:

- parse skipped counts in the unittest branch
- subtract skipped tests from `passed`

## Missing Capabilities

### Runner compatibility is narrower than the server's "generic" positioning

The current executable allowlist supports common direct runners and the currently implemented wrapper forms, but it does not cover many common test entrypoints such as:

- `tox`
- `nox`
- `make test`
- `just test`
- `dotnet test`
- `bundle exec rspec`

This is not a bug for the current repo, but it is a capability gap relative to the broader "generic workspace testing" description.

### Targeted execution is argv-appending only

`targetFiles` and `testNames` are appended to the resolved command, but there is no framework-aware targeting layer or capability signal.

Implications:

- some declared commands may not interpret appended targets meaningfully
- the tool does not advertise whether a command supports typed targeting well

## Coverage Gaps

The current test and eval surface is good for the split itself but still misses some behavioral edges.

Focused test gaps:

- no positive success-path test proving `scope="full"` runs the declared command exactly
- no skipped-unittest parser coverage
- no malformed XML coverage-parser test
- no missing in-workspace coverage-file test
- no explicit negative regression test asserting `xanadTools` no longer exports testing tools

Eval gaps:

- `evals/testing/` is still a narrow prompt smoke test
- no eval coverage for invalid input handling
- no eval coverage for full-scope behavior
- no eval coverage for coverage parsing
- no eval coverage for unavailable-state behavior

## External Research

This section summarizes source-backed ideas gathered from current MCP, FastMCP, and test-tool documentation.

### Sources

1. MCP tools specification (2025-06-18): <https://modelcontextprotocol.io/specification/2025-06-18/server/tools>
2. MCP progress specification: <https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress>
3. MCP roots specification: <https://modelcontextprotocol.io/specification/2025-06-18/client/roots>
4. FastMCP tools docs: <https://gofastmcp.com/servers/tools>
5. FastMCP progress and context docs: <https://gofastmcp.com/servers/progress> and <https://gofastmcp.com/servers/context>
6. pytest usage docs: <https://docs.pytest.org/en/stable/how-to/usage.html>
7. pytest exit codes: <https://docs.pytest.org/en/stable/reference/exit-codes.html>
8. pytest-json-report README: <https://github.com/numirias/pytest-json-report>
9. coverage.py API docs: <https://coverage.readthedocs.io/en/latest/api_coverage.html>

## Research-Backed Enhancement Opportunities

### 1. Richer runner exit semantics

Pytest defines distinct exit codes for failed tests, interruption, internal errors, usage errors, and no-tests-collected.

Potential addition:

- map exit codes into richer statuses such as `failed`, `interrupted`, `runner_error`, and `no_tests`
- add a `runnerExitReason` field to the structured result

### 2. Typed keyword and marker filters

Pytest supports `-k` keyword filtering and `-m` marker filtering. These are currently possible only through raw `extraArgs`.

Potential addition:

- add `keywordFilter`
- add `markerFilter`
- gate them on detected pytest-style commands

### 3. Test discovery tool

Pytest supports `--collect-only -q --no-header`, and modern unittest supports dry-run discovery.

Potential addition:

- add `testing_list_tests`
- return `testIds` and `total`
- let agents reason about scope before invoking a full run

Status:

- implemented conservatively for pytest-family commands only
- unittest discovery remains unsupported in this workspace because the available interpreter rejects `unittest discover --dry-run`

### 4. Typed output schemas

Recent MCP and FastMCP guidance supports structured tool outputs and declared `outputSchema` generation from typed return models.

Potential addition:

- replace open-ended result payloads with explicit Pydantic models such as `RunTestsResult`, `CoverageResult`, and `ListCommandsResult`
- make outputs machine-verifiable for clients

### 5. Coverage JSON support

coverage.py supports JSON output with richer line and branch coverage detail than Cobertura XML.

Potential addition:

- add `testing_parse_coverage_json`
- or extend `testing_parse_coverage` with a `format` parameter
- expose branch-coverage fields when available

### 6. Progress reporting for long-running tests

The current tool blocks until subprocess completion. MCP and FastMCP support progress updates through context-aware reporting.

Potential addition:

- emit progress bookends for long-running commands
- optionally move to async subprocess handling for incremental output and progress events

### 7. Tool timeout

The current subprocess execution path has no timeout and can hang indefinitely on stuck test runs.

Potential addition:

- add a subprocess timeout
- return a structured `timeout` status
- optionally add a FastMCP tool-level timeout as a second guardrail

### 8. Tool annotations

Recent MCP guidance supports behavioral tool annotations such as `readOnlyHint`, `idempotentHint`, and `openWorldHint`.

Potential addition:

- annotate `testing_show_key_commands` and `testing_parse_coverage` as read-only/idempotent
- mark `testing_run_tests` appropriately as non-read-only because test runs may write artifacts

### 9. Per-test result granularity

`pytest-json-report` can emit structured per-test results including outcomes, durations, and failure text.

Potential addition:

- add optional JSON-report integration for pytest
- expose `testDetails` when the plugin is present
- fall back cleanly when it is not installed

### 10. Workspace-root discovery via MCP roots

The current server infers workspace root by scanning parent directories for `.github`. MCP roots support would give the server an explicit client-provided root when available.

Potential addition:

- use client roots when supported
- keep the current heuristic as fallback

### 11. Subprocess environment sanitization

The current subprocess inherits the server environment wholesale.

Potential addition:

- pass a minimized explicit environment allowlist to subprocesses
- reduce accidental leakage of unrelated credentials or tokens

### 12. Capability discovery

The current server exposes declared workspace commands but not its own runtime capabilities.

Potential addition:

- add `testing_show_capabilities`
- report facts such as detected runner, venv availability, supported coverage formats, or optional report support

## Phased Implementation Plan

### Blast Radius

Primary implementation work should stay in:

- `mcp/scripts/workspaceTestingMcp.py`
- `mcp/scripts/_workspace_testing_shared.py`
- `tests/mcp_servers/test_workspace_testing_mcp.py`

Any MCP source change also cascades into:

- `.github/mcp/scripts/workspaceTestingMcp.py`
- `.github/mcp/scripts/_workspace_testing_shared.py`
- `template/setup/install-manifest.json`

Later capability phases are also likely to touch:

- `skills/testing/SKILL.md`
- `evals/testing/eval.yaml`
- `evals/testing/tasks/basic-invocation.yaml`
- `docs/contracts/tool-mcp-v1.md`
- `docs/contracts/tool-mcp-boundary.md`

After source edits, refresh managed and generated artifacts through the normal repo flow.

### Phase 1: Correctness and Contract Conformance

Scope:

- reject any `scope` outside `default` and `full`
- fix unittest skipped counting so `OK (skipped=1)` does not overstate passed tests
- add focused regression tests for both behaviors

Likely files:

- `mcp/scripts/workspaceTestingMcp.py`
- `mcp/scripts/_workspace_testing_shared.py`
- `tests/mcp_servers/test_workspace_testing_mcp.py`

Risks:

- adding a new public `skipped` field would widen the result contract; the safer first cut is to correct `passed` without changing the public shape

Dependencies:

- none

Focused verification:

- `python3 -m unittest tests.mcp_servers.test_workspace_testing_mcp`
- a direct regression probe for `tool_testing_run_tests({"scope": "bogus"})` expecting `status="unavailable"`

### Phase 2: Safety and Observability Hardening

Scope:

- add subprocess timeout handling
- decide whether richer exit classification remains internal or becomes part of the public contract
- add malformed and missing coverage-file tests
- preserve the existing shell-metacharacter and runner-allowlist protections

Likely files:

- `mcp/scripts/workspaceTestingMcp.py`
- `tests/mcp_servers/test_workspace_testing_mcp.py`
- `docs/workspace-testing-mcp.md`

Risks:

- introducing new `status` values or top-level result fields can drift from `docs/contracts/tool-mcp-v1.md`

Dependencies:

- phase 1 should land first so timeout and error reporting build on a correct baseline

Focused verification:

- `python3 -m unittest tests.mcp_servers.test_workspace_testing_mcp`
- `python3 -m unittest tests.mcp_servers.test_xanad_workspace_mcp_tools`

### Phase 3: Capability Discovery and Planning Support

Scope:

- add `testing_show_capabilities`
- add `testing_list_tests` only for runners that support deterministic collection without unsafe shell expansion
- update the testing skill and evals so agents can use capability signals intentionally

Likely files:

- `mcp/scripts/workspaceTestingMcp.py`
- `tests/mcp_servers/test_workspace_testing_mcp.py`
- `skills/testing/SKILL.md`
- `evals/testing/eval.yaml`
- `evals/testing/tasks/basic-invocation.yaml`
- `docs/workspace-testing-mcp.md`

Risks:

- new tool names and capability signals are public contract surface changes

Dependencies:

- phases 1 and 2 first

Status:

- `testing_show_capabilities` implemented
- `testing_list_tests` implemented conservatively for pytest-family commands only

Focused verification:

- `python3 -m unittest tests.mcp_servers.test_workspace_testing_mcp`
- `python3 -m unittest tests.repo.test_prompt_contracts`

### Phase 4: Richer Structured Outputs and Artifact Support

Scope:

- replace open-ended result dicts with explicit Pydantic models
- add MCP tool annotations where they improve client-side reasoning
- implement one bounded artifact enrichment path: coverage JSON support, optional pytest JSON reporting, or both behind explicit capability checks

Likely files:

- `mcp/scripts/workspaceTestingMcp.py`
- `mcp/scripts/_workspace_testing_shared.py`
- `tests/mcp_servers/test_workspace_testing_mcp.py`
- `docs/contracts/tool-mcp-v1.md`
- `docs/workspace-testing-mcp.md`

Risks:

- contract churn
- LOC growth in the MCP server file
- optional dependency policy if pytest plugin support is added

Dependencies:

- explicit contract review after phase 3

Focused verification:

- `python3 -m unittest tests.mcp_servers.test_workspace_testing_mcp`
- `python3 scripts/check_loc.py`
- `python3 -m unittest tests.repo.test_prompt_contracts`

### Phase 5: Broader Runner Compatibility

Scope:

- decide whether to broaden support for wrappers such as `uv run`, `poetry run`, `tox`, `nox`, `make test`, and `just test`, or narrow the documentation claims instead
- if broadening, implement wrapper-aware parsing conservatively rather than weakening execution controls

Likely files:

- `mcp/scripts/workspaceTestingMcp.py`
- `tests/mcp_servers/test_workspace_testing_mcp.py`
- `skills/testing/SKILL.md`
- `docs/contracts/tool-mcp-v1.md`
- `docs/workspace-testing-mcp.md`

Risks:

- this phase pushes directly on the command trust boundary and is the highest security-risk phase in the backlog

Dependencies:

- phase 3 should land first so capability reporting can describe supported wrappers honestly

Focused verification:

- one mocked regression per newly supported wrapper in `tests/mcp_servers/test_workspace_testing_mcp.py`
- `python3 -m unittest tests.mcp_servers.test_workspace_testing_mcp`
- `python3 scripts/drift_preflight.py`

### Stop Conditions

Stop and get explicit maintainer approval if:

- a phase changes the normative public contract in `docs/contracts/tool-mcp-v1.md` or `docs/contracts/tool-mcp-boundary.md`
- `mcp/scripts/workspaceTestingMcp.py` approaches the repo's MCP LOC budget and needs helper extraction
- wrapper support would require arbitrary shell execution or materially weaken the allowlist and metacharacter guard

## Current Recommendation

The most defensible next step is to fix the two concrete defects first and add the missing focused tests before expanding the tool surface.

After that, the best value additions are:

1. timeout and richer exit semantics
2. test discovery and capability discovery
3. coverage JSON support and typed structured outputs

Runner-breadth expansion should be deliberate because it directly affects the server's execution trust boundary.
