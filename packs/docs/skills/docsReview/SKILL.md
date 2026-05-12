---
name: docsReview
description: "Documentation review checklist — accuracy, completeness, clarity, and link health."
---

# docsReview

Use this skill when reviewing documentation before it is merged or published. Run through all tiers; report findings with the tier and a brief description.

## Review tiers

### Tier 1 — Accuracy (block merge)

- [ ] Every code example runs without modification.
- [ ] All parameter names, types, and defaults match the current implementation.
- [ ] No documented behavior contradicts the current behavior.
- [ ] API endpoints, CLI flags, and env var names are correct.
- [ ] Version numbers in "Since version X" or "Deprecated in X" annotations are correct.

### Tier 2 — Completeness (block merge if API changed)

- [ ] All public parameters, fields, and return values are documented.
- [ ] All error / exception conditions are listed.
- [ ] Breaking changes include a migration path.
- [ ] New features added since the last release have a changelog entry.
- [ ] No undocumented `required` parameters.

### Tier 3 — Clarity (suggest)

- [ ] Sentences are active voice and ≤25 words.
- [ ] Terms are used consistently throughout (no synonym drift).
- [ ] Code examples are complete and realistic (no `<placeholder>` values).
- [ ] Headings follow the section order from docsStructure.
- [ ] Acronyms are defined on first use.

### Tier 4 — Link health (suggest)

- [ ] All internal (relative) links resolve to existing files.
- [ ] All anchor links (`#section-name`) match actual headings.
- [ ] External links use HTTPS, not HTTP.

## Review comment format

Use these prefixes consistently:

| Prefix | Meaning |
|---|---|
| `accuracy:` | Documented behavior does not match implementation — must fix |
| `missing:` | Required content absent — must fix if API changed |
| `clarity:` | Prose or example could be clearer — suggest |
| `link:` | Broken or suspect link — suggest |
| `nit:` | Minor style preference — non-blocking |

## Approval criteria

A documentation PR is ready to merge when:

- All `accuracy:` and `missing:` findings are resolved.
- No unresolved `blocker:` comments from other reviewers.
- At least one approving review from someone who can verify accuracy (ideally the author of the code being documented).
