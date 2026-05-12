---
name: shapeupReview
description: >
  Review pitches, cycle work, and betting table decisions for Shape Up compliance. Use when
  auditing a pitch for completeness, reviewing in-cycle scope discipline, or validating that
  a betting table decision meets Shape Up principles.
---

# Shape Up — Review

Shape Up review checks whether work follows the core Shape Up disciplines: bounded appetite,
identified rabbit holes, explicit no-gos, and scope hammering during cycles.

## Pitch Review

### Tier 1 — Blocking

These issues must be resolved before a pitch is eligible for the betting table.

| Check | Fail condition |
|---|---|
| **Problem clarity** | The problem section describes a solution, not a problem. |
| **Appetite present** | No appetite stated, or appetite is a range ("4-8 weeks"). |
| **Solution present** | No sketch, breadboard, or prose sketch of the approach. |
| **Rabbit holes absent** | No rabbit holes listed and no explicit statement that none were found. |
| **No-gos absent** | No no-gos listed and scope appears unbounded. |

### Tier 2 — Warning

These issues reduce confidence in the bet.

| Check | Warning condition |
|---|---|
| **Scope vs. appetite** | The described solution seems to exceed the stated appetite. |
| **Rabbit hole mitigations** | A rabbit hole is named but no mitigation is described. |
| **No-go completeness** | No-gos listed are vague ("we won't over-engineer it"). |

### Tier 3 — Advisory

Suggestions for pitch quality improvements.

| Check | Advisory condition |
|---|---|
| **Problem grounding** | Problem is stated abstractly without a concrete example. |
| **Sketch clarity** | Fat-marker sketch is absent when prose is ambiguous. |
| **Audience fit** | Pitch assumes technical context the betting table may not have. |

## In-Cycle Scope Review

When reviewing work in progress during a cycle:

- Flag tasks added after cycle start that are not in the original pitch scope.
- Flag scope that has grown without an explicit scope-hammering decision.
- Flag tasks stuck on the uphill side of the hill chart mid-cycle.
- Flag any "we'll handle that in cooldown" plans — cooldown is not overflow.

## Betting Table Review

When reviewing a betting table outcome:

- [ ] Every bet has a complete pitch (not an idea or backlog item)
- [ ] Every bet has a named team with no team assigned to more than one bet
- [ ] No carry-over bets from the previous cycle without a fresh bet
- [ ] Every bet has a stated appetite that fits the cycle length

## Comment Prefixes

Use these prefixes when giving review feedback:

- `problem:` — problem statement issue
- `appetite:` — appetite missing, vague, or inconsistent
- `scope:` — scope exceeds appetite or grows without hammering
- `rabbit-hole:` — unaddressed rabbit hole or missing mitigation
- `no-go:` — missing or vague no-go
- `carry-over:` — work carried over without a fresh bet
- `nit:` — minor style or completeness issue
