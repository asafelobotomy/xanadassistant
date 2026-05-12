---
name: shapeupPitching
description: >
  Write, review, and refine Shape Up pitches. Use when drafting a new pitch, critiquing an
  existing pitch for completeness, or preparing a pitch for the betting table.
---

# Shape Up — Pitching

Shape Up pitches are the unit of work proposed for a betting table. A pitch answers five questions
before any cycle time is committed.

## The Five Elements

| Element | What it covers |
|---|---|
| **Problem** | The raw customer pain or business friction — not a solution in disguise. |
| **Appetite** | How much time the team is willing to spend: S (1-2 weeks), M (4 weeks), or L (6 weeks). |
| **Solution** | A concrete enough sketch to convey the approach — fat-marker sketch, breadboard, or short prose. Enough to bet on, not a full spec. |
| **Rabbit holes** | Specific technical or design traps that would blow the appetite if unaddressed. |
| **No-gos** | Explicit things the solution will not do — used to define the boundary of the bet. |

## Writing Discipline

- Lead with the problem. A pitch that opens with a solution hides the real value question.
- Set the appetite before designing. Appetite frames the solution, not the other way around.
- Rabbit holes are written as risks, not tasks. "The date-picker widget is a known rabbit hole — we
  will use a plain text input instead."
- No-gos are commitments, not wish-lists. State them plainly so the team can say "yes, we agree
  not to do that."
- Fat-marker sketches belong in the pitch if they convey the approach faster than prose. Detailed
  wireframes do not belong — they pre-answer decisions that should be left to the team.

## Pitch Review Checklist

Before presenting to the betting table, confirm:

- [ ] Problem is stated as a problem, not a solution
- [ ] Appetite is explicit and justified
- [ ] Solution sketch is present and clear enough to estimate feasibility
- [ ] At least one rabbit hole is named (if none exist, state why)
- [ ] At least one no-go is named (if none exist, scope is likely unbounded)
- [ ] Pitch is self-contained — a reader with no prior context can understand the bet

## Comment Prefixes

Use these prefixes when giving pitch feedback:

- `problem:` — the problem statement is unclear, hidden, or a solution in disguise
- `appetite:` — the appetite is missing, unjustified, or inconsistent with scope
- `scope:` — the solution exceeds the stated appetite or introduces unbounded work
- `rabbit-hole:` — a likely rabbit hole is unaddressed
- `no-go:` — scope boundary is unclear or missing
- `nit:` — minor wording or formatting issue
