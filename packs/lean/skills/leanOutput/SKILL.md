---
name: leanOutput
description: "Output discipline — lean factual responses with no filler, summaries as counts, and omitted routine narration."
---

# Lean Output

## When to use

- Workspaces with the lean pack selected, when generating responses, summaries, receipts, or reports

## When NOT to use

- Outside workspaces with the lean pack selected
- When the user explicitly requests expanded or detailed output

## Rules

- Prefer one-line descriptions over multi-sentence explanations.
- Summarize plan writes as counts only (added: N, replaced: N) without per-file listings unless explicitly asked.
- Omit receipt detail when the action is routine and the status is ok.
- Keep validation output to pass/fail with the error only; skip success narration.
- Omit unchanged-state commentary unless ambiguity exists (e.g., skip "no changes needed" when it is obvious).
- Drop filler phrases such as "I will now", "Here is", and "As requested".

## Verify

- [ ] One-line descriptions used; plan writes summarised as counts only (added: N, replaced: N)
- [ ] No filler phrases (`I will now`, `Here is`, `As requested`)
- [ ] No unchanged-state commentary where state is obvious
