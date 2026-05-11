---
name: Test Files
applyTo: "**/tests/**,**/test_*.py,**/*_test.py"
description: "Conventions for test files in this repository — Python unittest patterns, fixture approach, and verification discipline"
---

# Test File Instructions

- Testing framework: **Python `unittest`** — `python3 -m unittest discover -s tests -p 'test_*.py'`
- Run the narrowest targeted test module during intermediate work. Example: `python3 -m unittest tests.lifecycle.test_inspect_check`
- Run the full suite only at task completion or when shared helpers are touched.
- Test layout: `tests/lifecycle/`, `tests/manifest/`, `tests/hooks/`, `tests/tools/` for domain-grouped tests; `tests/_test_base.py`, `tests/_mcp_test_utils.py`, `tests/schema_validation.py`, `tests/fixtures/` at root.
- Fixtures are inline in test methods — no external test data files.
- `tempfile.TemporaryDirectory()` for any test that needs a filesystem workspace; clean up is automatic.
- Use `self.run_command_in_workspace(workspace, "<subcommand>", "--json")` to invoke the lifecycle CLI in tests; assert on `result.returncode` and `json.loads(result.stdout)`.
- Never mock the lifecycle engine internals — test through the CLI surface.
- When fixing a bug, write a failing test first, then fix the code.
- Each test class covers one logical concern; test method names describe the expected behaviour, not the implementation.
- Network-gated tests: set `XANAD_NETWORK_TESTS=1` and use `@unittest.skipUnless(os.environ.get("XANAD_NETWORK_TESTS"), "network tests disabled")`.
- 4 network-gated tests are expected to skip in normal runs — this is correct behaviour.
