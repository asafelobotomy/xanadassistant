---
name: shapeupCycleWork
description: >
  Execute and track work during a Shape Up cycle. Use when managing in-cycle scope, using hill
  charts, applying scope hammering, or deciding whether to invoke the circuit breaker.
---

# Shape Up — Cycle Execution

A Shape Up cycle is a fixed time box (typically 6 weeks) in which a team builds the pitched
solution. The team owns how they get there; the key disciplines are scope management and progress
visibility.

## Hill Charts

Hill charts track tasks on two halves:
- **Uphill** (left): figuring out — the task still has unknowns.
- **Downhill** (right): executing — the approach is settled, the team is building.

Tasks move uphill as design and unknowns are resolved, then downhill as implementation proceeds.
A task stuck on the uphill side is a risk signal.

Use hill charts to:
- Surface hidden unknowns early
- Identify tasks that are stalling before they become blockers
- Distinguish "we know what to do" from "we know how to do it"

## Scoping During a Cycle

Scope is not fixed at the start of a cycle. The team scopes as they discover the real shape of
the work:

1. Break the pitch into tasks at the start.
2. Expect the task list to change — that is normal.
3. When scope grows, apply **scope hammering**: ask "is this strictly necessary to ship?"
4. Move non-essential work to future pitches. Do not silently expand cycle scope.

## Scope Hammering Questions

- Is this required for the core use case described in the pitch?
- Does removing this break anything the user explicitly needs?
- Can we ship without it and add it later without penalty?

If the answer to the last two is "yes", cut it.

## Circuit Breaker

Shape Up uses a circuit breaker instead of deadlines: **if work is not done at the end of the
cycle, it does not automatically roll over.** The team stops, the work is evaluated, and only
a re-bet puts it back into a cycle.

Invoke the circuit breaker when:
- The cycle ends and the work is significantly incomplete
- New scope has expanded the work beyond the original appetite
- A rabbit hole was hit that would require a new bet to resolve

## Cooldown

The two weeks between cycles are for slack, fixes, and exploration — not continuation of cycle
work. Do not use cooldown to finish incomplete cycle work without a new bet.
