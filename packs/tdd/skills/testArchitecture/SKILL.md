---
name: testArchitecture
description: >
  Test isolation, modular test design, and test boundary conventions. Use when structuring a
  test suite, separating unit from integration tests, or deciding what a test should and should
  not cross as a boundary.
---

# Test Architecture

A well-structured test suite is maintainable, fast to run, and clearly signals what broke and
why. Poor test architecture creates slow, brittle, or duplicated suites that developers learn
to distrust.

## Test Pyramid

| Layer | Scope | Count | Speed |
|---|---|---|---|
| **Unit** | One function or class, all dependencies doubled | Many | Milliseconds |
| **Integration** | A group of real components together | Fewer | Seconds |
| **End-to-end** | Full system through public API or UI | Few | Tens of seconds |

The pyramid is a ratio, not an absolute count. A codebase with ten integration tests and one
unit test is inverted. Add unit tests until the pyramid stabilizes.

## Test Isolation Rules

- A unit test must not touch the filesystem, network, database, or clock without explicit
  doubling (use fakes or mocks for those dependencies).
- A test that depends on another test's state is not a unit test — it is a script. Refactor
  to eliminate shared mutable state between tests.
- Each test should be able to run alone and in any order. If it can't, the test is revealing
  a coupling problem in the production code, not a test problem.

## Boundary Decisions

Decide what the test's subject is, then double everything outside that boundary:

| Inside the boundary | Outside the boundary |
|---|---|
| The class or function under test | External services (HTTP, DB, filesystem) |
| Pure helper functions it calls | Clocks and random sources |
| In-memory data structures | Other modules if testing this module in isolation |

## Test Naming Conventions

Test names are specification statements. They describe behavior, not implementation:

- **Good**: `test_payment_is_rejected_when_card_is_expired`
- **Bad**: `test_payment_method_3`

Use the pattern: `test_<subject>_<action>_when_<condition>` or `test_<subject>_<result>_given_<state>`.

## Test File Organization

- One test file per source module (mirrors the source tree).
- Group tests by behavior cluster using inner classes or comment sections, not by method name.
- Keep test helpers and fixtures local to the test file unless at least three test files share them.
- Do not share mutable state between test classes.

## When to Write Integration Tests

Write an integration test when:
- The correctness depends on two components working together correctly (not just individually).
- The integration point has a contract that can drift (e.g., a database schema or an external API shape).
- The unit tests pass but something still fails in practice — that is an integration gap.

Do not write integration tests as a substitute for missing unit tests.

## Comment Prefixes

Use these prefixes when reviewing test architecture:

- `isolation:` — test crosses a boundary it should not (network, filesystem, shared state)
- `pyramid:` — test belongs at a different layer (too broad for a unit, too narrow for e2e)
- `naming:` — test name describes implementation rather than behavior
- `coupling:` — test depends on execution order or another test's state
- `nit:` — minor organization or style issue
