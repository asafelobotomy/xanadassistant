---
name: testDoubles
description: "Test double selection — stubs, mocks, fakes, and spies for test isolation and determinism."
type: reference
---

# Test Doubles

> Skill metadata: version "1.0"; tags [tdd, test-doubles, mocking]; recommended tools [].

Use this skill in workspaces with the tdd pack selected.

Choose the right test double for the job. The wrong double makes tests brittle; the right one makes them fast and deterministic.

## When to use

- Workspaces with the tdd pack selected, when choosing the right test double type for isolation or interaction verification

## When NOT to use

- Outside workspaces with the tdd pack selected
- When the component under test has no external dependencies to isolate

## The five kinds

| Kind | What it does | Use when |
| --- | --- | --- |
| **Dummy** | Passed but never used | Satisfying a parameter list when the argument doesn't matter |
| **Stub** | Returns pre-programmed values | Isolating the unit from a dependency's return value |
| **Fake** | Working implementation with shortcuts | Replacing a heavy dependency (e.g., an in-memory DB instead of a real one) |
| **Spy** | Records calls; optionally stubs | Verifying that a dependency was called correctly |
| **Mock** | Pre-programmed with call expectations | Strictly verifying interaction contracts with a dependency |

## Decision guidance

- **Prefer stubs over mocks** for most isolation. Mocks couple tests to implementation detail (the call sequence); stubs couple only to the return value.
- **Use fakes** when the real implementation is too slow or requires external infrastructure (database, filesystem, HTTP), but the logic it encapsulates is complex enough to need real behavior.
- **Use spies** when you need to verify that a side-effecting dependency (logger, event bus, mailer) was invoked — but only assert on the interactions that matter to the behavior under test.
- **Avoid mocking what you don't own.** Mock your own interfaces; use fakes or integration tests for third-party libraries.

## Placement rules

- Test doubles belong in test files or a dedicated test-support module. Never ship doubles to production.
- Name doubles clearly: `FakeUserRepository`, `StubMailer`, `SpyAuditLog`.
- Keep fake implementations minimal — only the behavior the tests actually exercise.

## Fragility warning

If changing an implementation detail (not the public contract) breaks a test that uses a mock, the mock is over-specified. Replace it with a stub or a spy asserting only the observable outcome.

## Verify

- [ ] Most minimal double type chosen for the test goal (dummy < stub < fake < spy < mock)
- [ ] No over-mocking; flagged if more than 3 mocks appear in a single test
