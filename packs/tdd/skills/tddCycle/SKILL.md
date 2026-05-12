---
name: tddCycle
description: "Red-Green-Refactor cycle discipline — one failing test at a time, minimal implementation, commit on green."
---

# TDD Cycle

Use this skill in workspaces with the tdd pack selected.

Apply the Red-Green-Refactor cycle as the fundamental unit of work. Each cycle is complete and verifiable before the next begins.

## The three phases

**Red** — Write a failing test that captures exactly one new behavior. The test must fail for the right reason (assertion failure on behavior, not a compile or import error). Do not write implementation code during this phase.

**Green** — Write the minimum code needed to make the failing test pass. Correctness matters; elegance does not. Duplication and hardcoded returns are acceptable at this phase. Do not refactor during this phase.

**Refactor** — Restructure the code and tests without changing behavior. All tests must remain green throughout. This is the only phase where cleanup is appropriate.

## What makes a good test (Red phase discipline)

- Tests exactly one behavior per test method
- Has a descriptive name that reads as a specification: `test_returns_zero_for_empty_input`, not `test_1`
- Follows Arrange-Act-Assert (AAA) structure: set up state, call the unit, assert the outcome
- Fails with a clear assertion error — not an exception from missing infrastructure
- Does not depend on external state (file system, network, clock) without explicit control via a test double

## What makes good minimal implementation (Green phase discipline)

- Do the simplest thing that makes the test pass
- Fake it if necessary — return a hardcoded value, then generalize in the next cycle
- Do not add behavior that is not yet tested
- Do not write defensive code for untested scenarios

## Commit discipline

Commit after each complete Red-Green-Refactor cycle. A commit with a failing test is only acceptable if explicitly marked `wip:` and immediately followed by Green.
