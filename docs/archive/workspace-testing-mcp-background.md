# workspaceTesting MCP — Background Notes

## Status

- Archived from `docs/workspace-testing-mcp.md` on 2026-06-01 to keep the current-state document within the repo LOC budget
- Related current-state document: `docs/workspace-testing-mcp.md`

## Historical Audit Notes

The 2026-05-31 audit originally found these issues, both now fixed and covered by focused regression tests.

### Invalid `scope` values were accepted

The contract documents `scope` as the enum `default | full`, and `testing_run_tests` now rejects other values with `status="unavailable"`.

Why it mattered:

- runtime behavior was looser than the documented contract
- callers could not rely on schema-level validation for this field

Resolution recorded by the tests:

- reject any scope outside `default` and `full`
- keep focused regression coverage for invalid enum values

### Unittest skipped cases were overcounted as passed

`parse_test_summary()` now subtracts skipped unittest cases from the reported pass count for output shaped like `OK (skipped=1)`.

Why it mattered:

- agent-readable summaries became inaccurate
- downstream reasoning about test health could be misleading

Resolution recorded by the tests:

- parse skipped counts in the unittest branch
- subtract skipped tests from `passed`

## Capability Gaps Worth Future Design Work

### Runner compatibility remains deliberately narrow

The current executable allowlist supports common direct runners and currently implemented wrapper forms, but it does not cover many common entrypoints such as `tox`, `nox`, `make test`, `just test`, `dotnet test`, or `bundle exec rspec`.

### Targeted execution is argv-appending only

`targetFiles` and `testNames` are appended to the resolved command, but there is no framework-aware targeting layer or separate capability signal for every command shape.

## Coverage Gaps Recorded During the Audit Cycle

Focused test gaps that were identified at the time:

- no positive success-path test proving `scope="full"` runs the declared command exactly
- no skipped-unittest parser coverage
- no malformed XML coverage-parser test
- no missing in-workspace coverage-file test
- no explicit negative regression test asserting `xanadTools` no longer exports testing tools

Eval gaps noted at the time:

- `evals/testing/` was still a narrow prompt smoke test
- no eval coverage for invalid input handling
- no eval coverage for full-scope behavior
- no eval coverage for coverage parsing
- no eval coverage for unavailable-state behavior

## External Research Sources

1. MCP tools specification (2025-06-18): <https://modelcontextprotocol.io/specification/2025-06-18/server/tools>
2. MCP progress specification: <https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress>
3. MCP roots specification: <https://modelcontextprotocol.io/specification/2025-06-18/client/roots>
4. FastMCP tools docs: <https://gofastmcp.com/servers/tools>
5. FastMCP progress and context docs: <https://gofastmcp.com/servers/progress> and <https://gofastmcp.com/servers/context>
6. pytest usage docs: <https://docs.pytest.org/en/stable/how-to/usage.html>
7. pytest exit codes: <https://docs.pytest.org/en/stable/reference/exit-codes.html>
8. pytest-json-report README: <https://github.com/numirias/pytest-json-report>
9. coverage.py API docs: <https://coverage.readthedocs.io/en/latest/api_coverage.html>

## Research-Backed Enhancement Ideas

### Richer runner exit semantics

Pytest defines distinct exit codes for failed tests, interruption, internal errors, usage errors, and no-tests-collected.

Potential additions:

- map exit codes into richer statuses such as `failed`, `interrupted`, `runner_error`, and `no_tests`
- add a `runnerExitReason` field to the structured result

### Typed keyword and marker filters

Pytest supports `-k` keyword filtering and `-m` marker filtering. These are currently possible only through raw `extraArgs`.

Potential additions:

- add `keywordFilter`
- add `markerFilter`
- gate them on detected pytest-style commands

### Test discovery tool

Pytest supports `--collect-only -q --no-header`, and modern unittest supports dry-run discovery.

Potential additions:

- add `testing_list_tests`
- return `testIds` and `total`
- let agents reason about scope before invoking a full run

Status at archive time:

- implemented conservatively for pytest-family commands only
- unittest discovery remained unsupported in this workspace because the available interpreter rejected `unittest discover --dry-run`

### Typed output schemas

Recent MCP and FastMCP guidance supports structured tool outputs and declared `outputSchema` generation from typed return models.

Potential additions:

- replace open-ended result payloads with explicit Pydantic models such as `RunTestsResult`, `CoverageResult`, and `ListCommandsResult`
- make outputs machine-verifiable for clients

### Coverage JSON support

coverage.py supports JSON output with richer line and branch coverage detail than Cobertura XML.

Potential additions:

- add `testing_parse_coverage_json`
- or extend `testing_parse_coverage` with a `format` parameter
- expose branch-coverage fields when available

### Progress reporting for long-running tests

The current tool blocks until subprocess completion. MCP and FastMCP support progress updates through context-aware reporting.

Potential additions:

- emit progress bookends for long-running commands
- optionally move to async subprocess handling for incremental output and progress events

### Tool annotations

Recent MCP guidance supports behavioral tool annotations such as `readOnlyHint`, `idempotentHint`, and `openWorldHint`.

Potential additions:

- annotate `testing_show_key_commands` and `testing_parse_coverage` as read-only or idempotent
- mark `testing_run_tests` appropriately as non-read-only because test runs may write artifacts

### Per-test result granularity

`pytest-json-report` can emit structured per-test results including outcomes, durations, and failure text.

Potential additions:

- add optional JSON-report integration for pytest
- expose `testDetails` when the plugin is present
- fall back cleanly when it is not installed

### Workspace-root discovery via MCP roots

The current server infers workspace root by scanning parent directories for `.github`. MCP roots support would give the server an explicit client-provided root when available.

Potential additions:

- use client roots when supported
- keep the current heuristic as fallback

### Subprocess environment sanitization

The current subprocess inherits the server environment wholesale.

Potential additions:

- pass a minimized explicit environment allowlist to subprocesses
- reduce accidental leakage of unrelated credentials or tokens

### Capability discovery

The current server exposes declared workspace commands but not its own runtime capabilities.

Potential additions:

- add `testing_show_capabilities`
- report facts such as detected runner, venv availability, supported coverage formats, or optional report support

## Archived Phased Plan

### Blast Radius

Primary implementation work should stay in:

- `mcp/scripts/workspaceTestingMcp.py`
- `mcp/scripts/_workspace_testing_shared.py`
- `tests/mcp_servers/test_workspace_testing_mcp.py`

Any MCP source change also cascades into:

- `.github/mcp/scripts/workspaceTestingMcp.py`
- `.github/mcp/scripts/_workspace_testing_shared.py`
- `template/setup/install-manifest.json`

Later capability phases were expected to touch:

- `skills/testing/SKILL.md`
- `evals/testing/eval.yaml`
- `evals/testing/tasks/basic-invocation.yaml`
- `docs/contracts/tool-mcp-v1.md`
- `docs/contracts/tool-mcp-boundary.md`

### Phase 1: Correctness and Contract Conformance

Scope:

- reject any `scope` outside `default` and `full`
- fix unittest skipped counting so `OK (skipped=1)` does not overstate passed tests
- add focused regression tests for both behaviors

Focused verification:

- `python3 -m unittest tests.mcp_servers.test_workspace_testing_mcp`
- a direct regression probe for `tool_testing_run_tests({"scope": "bogus"})` expecting `status="unavailable"`

### Phase 2: Safety and Observability Hardening

Scope:

- add subprocess timeout handling
- decide whether richer exit classification remains internal or becomes part of the public contract
- add malformed and missing coverage-file tests
- preserve existing shell-metacharacter and runner-allowlist protections

Focused verification:

- `python3 -m unittest tests.mcp_servers.test_workspace_testing_mcp`
- `python3 -m unittest tests.mcp_servers.test_xanad_workspace_mcp_tools`

### Phase 3: Capability Discovery and Planning Support

Scope:

- add `testing_show_capabilities`
- add `testing_list_tests` only for runners that support deterministic collection without unsafe shell expansion
- update the testing skill and evals so agents can use capability signals intentionally

Status at archive time:

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

Focused verification:

- `python3 -m unittest tests.mcp_servers.test_workspace_testing_mcp`
- `python3 scripts/check_loc.py`
- `python3 -m unittest tests.repo.test_prompt_contracts`

### Phase 5: Broader Runner Compatibility

Scope:

- decide whether to broaden support for wrappers such as `uv run`, `poetry run`, `tox`, `nox`, `make test`, and `just test`, or narrow the documentation claims instead
- if broadening, implement wrapper-aware parsing conservatively rather than weakening execution controls

Focused verification:

- one mocked regression per newly supported wrapper in `tests/mcp_servers/test_workspace_testing_mcp.py`
- `python3 -m unittest tests.mcp_servers.test_workspace_testing_mcp`
- `python3 scripts/drift_preflight.py`

### Stop Conditions

Stop and get explicit maintainer approval if:

- a phase changes the normative public contract in `docs/contracts/tool-mcp-v1.md` or `docs/contracts/tool-mcp-boundary.md`
- `mcp/scripts/workspaceTestingMcp.py` approaches the repo's MCP LOC budget and needs helper extraction
- wrapper support would require arbitrary shell execution or materially weaken the allowlist and metacharacter guard

## Archived Recommendation

The original recommendation sequence was:

1. fix concrete correctness defects first and add focused tests
2. then improve timeout and richer exit semantics
3. then layer on discovery, coverage JSON, and more structured outputs

Runner-breadth expansion remained the highest-risk backlog area because it directly affects the subprocess trust boundary.
