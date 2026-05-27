---
name: tddCycle
description: "Red-Green-Refactor cycle discipline — one failing test at a time, minimal implementation, optional commit boundary on green."
---

# TDD Cycle

> Skill metadata: version "1.0"; tags [tdd, red-green-refactor]; recommended tools [].

Use this skill in workspaces with the tdd pack selected.

Apply the Red-Green-Refactor cycle as the fundamental unit of work. Each cycle is complete and verifiable before the next begins.

## When to use

- Workspaces with the tdd pack selected, when applying Red-Green-Refactor as the fundamental unit of work

## When NOT to use

- Outside workspaces with the tdd pack selected
- When reviewing existing test architecture — prefer `testArchitecture`

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

Treat a complete Red-Green-Refactor cycle as a natural commit boundary, not an automatic commit requirement. Only make a commit when the user asks for one or the repository workflow explicitly requires it. If local instructions route git actions through a specialist workflow or agent, follow that route instead of committing directly. A commit with a failing test is only acceptable if the user explicitly wants a `wip:` checkpoint and understands the state being recorded.

## Verify

- [ ] Test written before implementation confirmed (Red phase)
- [ ] Minimal implementation only — no premature abstraction (Green phase)
- [ ] Refactor left all tests green; one new behavior per cycle
