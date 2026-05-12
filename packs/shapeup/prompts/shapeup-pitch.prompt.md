---
mode: ask
description: Draft or review a Shape Up pitch using the five-element structure.
---

Draft or review a Shape Up pitch.

## Instructions

Use the shapeupPitching skill to structure the output.

If the user is **drafting** a new pitch, ask for:
1. The problem to solve (one or two sentences of raw friction, not a solution)
2. The appetite (Small: 1-2 weeks, Medium: 4 weeks, Large: 6 weeks)
3. Any known constraints, rabbit holes, or things the solution will not do

Then produce a complete pitch document with all five elements:
- **Problem** — what is broken or painful
- **Appetite** — the time box commitment
- **Solution** — a fat-marker sketch or short prose describing the approach
- **Rabbit holes** — at least one named risk and its mitigation, or explicit "none found"
- **No-gos** — at least one explicit boundary, or explicit "none required"

If the user is **reviewing** an existing pitch, apply the shapeupReview skill checklist:
- Tier 1 (Blocking): problem clarity, appetite, solution, rabbit holes, no-gos
- Tier 2 (Warning): scope vs. appetite, rabbit hole mitigations, no-go vagueness
- Tier 3 (Advisory): problem grounding, sketch clarity, audience fit

Prefix each finding with the appropriate comment prefix from shapeupReview.

## Output Format

For drafts: produce the pitch in Markdown with each of the five sections as a heading.
For reviews: produce a numbered finding list grouped by tier, then a summary verdict:
`READY FOR BETTING TABLE`, `NEEDS REVISION`, or `NOT ELIGIBLE`.
