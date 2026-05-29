---
name: testCoverage
description: "Use when: analyzing test coverage as a diagnostic tool, identifying gaps, or evaluating assertion strength."
type: reference
---

# Test Coverage

> Skill metadata: version "1.0"; tags [tdd, coverage, testing]; recommended tools [].

Use this skill in workspaces with the tdd pack selected.

Coverage is a diagnostic tool, not a goal. High line coverage with weak assertions is worse than targeted coverage with strong assertions.

## When to use

- Workspaces with the tdd pack selected, when analyzing coverage gaps, interpreting coverage reports, or deciding on coverage targets

## When NOT to use

- When writing new tests from scratch — prefer `tddCycle`
- When reviewing test architecture decisions — prefer `testArchitecture`

## What coverage tells you

- **Line/statement coverage**: which code was executed. Tells you what was NOT tested; says nothing about test quality.
- **Branch coverage**: which conditional paths were taken. A stronger signal — aim for branch coverage over line coverage.
- **Mutation coverage**: whether tests can detect introduced bugs. The most meaningful signal; use mutation testing (e.g., `mutmut`, `PIT`) to validate test quality when coverage targets are met.

## Coverage targets

There are no universal targets. Use these as starting heuristics:

| Code type | Branch coverage target | Notes |
| --- | --- | --- |
| Core business logic | ≥ 90% | Test all decision points; high value, high risk |
| Public API layer | ≥ 80% | Focus on contract behavior, not internal wiring |
| Infrastructure / adapters | ≥ 70% | Integration tests often cover more than unit tests here |
| Generated / boilerplate | Excluded | No value in testing generated code |
| Error handling paths | ≥ 80% | Untested error paths fail in production |

## When to check coverage

- After each Red-Green-Refactor cycle — check that the new test added coverage for the target behavior
- Before committing — run the full suite and check for regressions in coverage
- In CI — gate on minimum branch coverage, not line coverage

## Coverage anti-patterns to flag

- Tests that increase coverage but assert nothing (no assertion statements)
- Tests that test getter/setter trivially without exercising business logic
- Artificially inflating coverage with trivially-satisfied paths to reach a percentage target
- Missing tests for error paths, boundary conditions, and empty/null inputs

## Verify

- [ ] Branch coverage reported, not only line coverage
- [ ] Meaningful gaps identified (untested paths, not just low-count lines)
- [ ] Coverage treated as a diagnostic signal, not as a target metric
