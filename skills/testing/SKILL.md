---
name: testing
description: "Use when: running targeted or full tests in any workspace, choosing the safest available test command, summarizing test results, or deciding when to hand failing tests to Debugger."
---

# Testing

> Skill metadata: version "1.1"; tags [testing, validation, mcp, workflow, generic]; recommended tools [testing_show_key_commands, testing_run_tests, testing_parse_coverage, run_in_terminal].

Procedural skill for running tests through the workspace's declared testing apparatus before, during, or after code changes.

## When to use

- When a task needs targeted tests, full tests, or a validation summary
- When the workspace's test command should be discovered instead of assumed
- When deciding whether a failing test needs Debugger handoff

## When NOT to use

- When the user asks for a full CI-equivalent pre-commit or pre-push gate — prefer `ciPreflight`
- When tests are already failing and root-cause diagnosis is the main task — prefer `Debugger`
- When the task is test coverage adequacy or regression-risk review — prefer `Review`
- When strict Red-Green-Refactor coaching is needed and the TDD pack is installed — prefer the TDD pack skill or prompt
- When the workspace has no declared test apparatus and the task is to define one — prefer direct repo maintenance or documentation updates over this runtime workflow

## Steps

1. Discover the workspace test apparatus.
   - Prefer `testing_show_key_commands` from the `workspaceTesting` MCP server.
   - Confirm a declared `Run tests` command exists and is not `(not detected)`.
   - If `workspaceTesting` is unavailable, read the workspace instructions or project docs for the documented test command; do not invent a shell command.

2. Choose the narrowest useful scope.
   - For a localized code change, run targeted tests first with safe argv-style target arguments.
   - For shared infrastructure, generated surfaces, or task completion, run the full declared test command.
   - If target arguments are uncertain or framework-specific, prefer a full run over guessing unsafe flags.

3. Execute through the safest available runner.
   - Prefer `testing_run_tests(scope="default", extraArgs=[...])` for targeted runs.
   - Prefer `testing_run_tests(scope="full")` for full runs.
   - Use the documented native command only when the `workspaceTesting` server is unavailable.
   - Do not use arbitrary command strings, shell interpolation, pipes, redirects, or commands requiring secrets unless the workspace documentation explicitly requires them.

4. Summarize the result in an agent-readable form.
   - Report status, command or tool used, exit code, and the relevant stdout/stderr tail.
   - Identify first failing test, failing file, or failure class when the output makes that clear.
   - State whether the check is targeted, full, skipped, unavailable, or blocked.

5. Parse coverage artifacts when they are part of the workspace's test apparatus.
   - Prefer `testing_parse_coverage(coveragePath="coverage.xml")` for Cobertura-style coverage output when the file exists or is documented by the workspace.
   - Report percent covered, valid/covered line counts, and zero-coverage files when available.
   - If no coverage artifact is declared or produced, state that coverage was not assessed rather than guessing.

6. Act on failures deliberately.
   - If the failure is clearly caused by the current edit slice, fix that slice and rerun the same test.
   - If root cause is unclear, delegate to `Debugger` with the exact command, output tail, changed files, and why the test was selected.
   - If a test cannot run because the workspace lacks a declared test command, report the missing apparatus and suggest adding one to workspace instructions.

## Verify

- [ ] A declared workspace test command or explicit unavailable state has been observed this session
- [ ] `workspaceTesting.testing_run_tests` was preferred when available, with documented native fallback only when needed
- [ ] Targeted runs used safe argv-style arguments; full runs used the command exactly
- [ ] Output summary includes status, command/tool, exit code when available, and relevant output tail
- [ ] Coverage artifact was parsed with `testing_parse_coverage` when present or explicitly reported as not assessed
- [ ] Failing tests were either repaired in the current slice or handed to `Debugger` with exact evidence