---
name: leanVerification
description: "Use when: reporting test and validation results with pass/fail status, minimal passing output, and concise failure triage."
type: reference
version: "1.0"
license: MIT
---

# Lean Verification

> Skill metadata: version "1.0"; tags [lean, verification, testing]; recommended tools [].

Use this skill in workspaces with the lean pack selected.

Apply when running or reporting on tests, linters, type checkers, or any validation step.

## When to use

- Workspaces with the lean pack selected, when running or reporting on tests, linters, type checkers, or validation steps

## When NOT to use

- Outside workspaces with the lean pack selected
- When the user explicitly requests verbose test output or a full run transcript

## Passing runs

Single line only:

```
Ran: N — pass  (M skipped)
```

No per-test narration. No success confirmations. No "all tests passed" prose. No timing breakdown unless explicitly requested.

## Failing runs

For each failure, one block:

```
FAIL  <test-name>
  <file>:<line>  <error-message>
```

Follow all failures with a count summary:

```
Ran: N — failed: F, passed: P, skipped: S
```

Stack traces: include only the immediate error line plus the assertion line. Omit unrelated framework frames unless the error is ambiguous without them.

## Linters and type checkers

- Passing: `<tool>: clean`
- Failing: one line per issue in `<file>:<line>  <code>  <message>` format, followed by `<tool>: F error(s)`

## What to omit

- Individual passing test names
- Full stack traces when the failing line is sufficient
- Verbose runner output: progress dots, timing breakdowns, deprecation warnings from test infrastructure
- "No issues found" narration when a clean result is expected

## What to always include

- Full error messages verbatim — never truncate or paraphrase failure text
- File and line references — every failure must be immediately locatable
- Total counts — always, even on a clean run

## Verify

- [ ] Passing runs reported as a single summary line only
- [ ] Failing runs include file, line, and message only — no stack-trace prose
- [ ] No per-test narration for passing tests
