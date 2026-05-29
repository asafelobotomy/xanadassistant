# tdd pack

The tdd pack installs test-driven development defaults — Red→Green→Refactor
discipline, test double guidance, coverage analysis, and test architecture
conventions — and keeps agents in the TDD cycle throughout each session.

## Purpose

Install this pack when you want agents to write failing tests before
implementation code, name the current TDD phase at each step, and avoid
over-implementing beyond what the current test requires.

## Surfaces

| Surface | Contents |
|---|---|
| **Skills** | `tddCycle`, `testArchitecture`, `testCoverage`, `testDoubles` |
| **Prompts** | `/tdd-session`, `/tdd-review` |
| **MCP** | `tddTestRunner.py` — runs the test suite and surfaces structured pass/fail output |

## Token overrides

| Token | TDD behavior |
|---|---|
| `{{pack:review-depth}}` | Flag test correctness issues at all severities: wrong assertions, tests that can never fail, missing coverage for critical paths |
| `{{pack:scope-discipline}}` | Write the failing test before implementation; do not expand beyond what is needed to make the current test pass; refactor only after green |
| `{{pack:step-size}}` | One failing test at a time; Red→Green→Refactor is a complete step |
| `{{pack:reasoning-mode}}` | Name the current TDD phase explicitly at the start of each step (Red / Green / Refactor) |

## Interview customization

During setup you can set the cycle strictness:

- **Strict** — one failing test at a time; no implementation before the test
  exists and fails for the correct reason; no behavior beyond the current test.
- **Guided** (default) — prefer test-first and name the phase; allow scoping
  multiple related behaviors upfront when explicitly stated.

Both options override `{{pack:scope-discipline}}`.
