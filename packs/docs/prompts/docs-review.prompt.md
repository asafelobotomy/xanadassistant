---
mode: ask
description: "Review documentation for accuracy, completeness, clarity, and link health."
---

You are reviewing documentation for a software project.

Apply the docsReview skill for the full checklist. Apply the docsStyle skill to evaluate prose quality. Apply the docsApi skill if the content documents code, CLI, or API behavior.

---

## Inputs

Provide as many of the following as you have:

- **Document(s) to review**: Paste the content or describe which files to look at.
- **Implementation context**: Relevant code, function signatures, or CLI output that the documentation describes — used to verify accuracy.
- **Review focus**: All tiers / Accuracy only / Completeness only / Clarity only.
- **Recent changes**: What changed since the last review (helps prioritise).

---

## Output

Produce a structured review with findings grouped by tier:

```
### Tier 1 — Accuracy
- accuracy: [file, line or section] — [description of the mismatch]

### Tier 2 — Completeness
- missing: [file, section] — [what is absent]

### Tier 3 — Clarity
- clarity: [file, section] — [suggestion]

### Tier 4 — Link health
- link: [file, link text] — [broken or suspect]
```

End with a summary verdict:
- **Approved** — no blocking findings.
- **Approved with suggestions** — no blockers; clarity/link suggestions noted.
- **Changes requested** — one or more accuracy or missing findings must be resolved first.
