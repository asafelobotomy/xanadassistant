---
name: ossCodeReview
description: "OSS code review discipline — PR review standards, review comment etiquette, and contribution gate criteria."
---

# ossCodeReview

Use this skill when reviewing OSS pull requests or when a maintainer needs structured guidance on what to check before merging.

## Review tiers

Run through all tiers before leaving a verdict.

| Tier | What to check | Block merge? |
|---|---|---|
| **Correctness** | Logic is sound; edge cases handled; no regressions | Yes |
| **Tests** | New behavior has tests; tests actually fail before the fix | Yes |
| **API compatibility** | No unannounced breaking changes to public surface | Yes |
| **Documentation** | Public API changes are documented; changelog entry present | Yes if API changed |
| **License & DCO** | All new files have SPDX header; DCO sign-off present if required | Yes if required |
| **Security** | No new injection vectors, hardcoded secrets, or insecure defaults | Yes |
| **Style** | Matches project conventions; linter clean | Suggest only |
| **Performance** | No obvious O(n²) regressions in hot paths | Suggest only |

## Review comment etiquette

Use the following prefixes to make severity obvious:

| Prefix | Meaning |
|---|---|
| `nit:` | Non-blocking style preference |
| `suggest:` | Non-blocking improvement idea |
| `question:` | Clarification needed; may block if unanswered |
| `request:` | Change required before merge |
| `blocker:` | Must-fix; do not merge until resolved |

Example:
```
blocker: This is vulnerable to SQL injection — use a parameterized query.
suggest: Consider extracting this loop into a named helper for readability.
nit: Trailing whitespace on line 42.
```

## PR gate criteria (recommend)

A PR is ready to merge when:

- [ ] All CI checks pass.
- [ ] At least one approving review from a maintainer.
- [ ] No unresolved `request:` or `blocker:` comments.
- [ ] Changelog entry present under `## [Unreleased]` (for user-visible changes).
- [ ] DCO sign-off present on all commits (if project requires it).
- [ ] No new lint warnings introduced.

## Feedback framing

- Be specific: cite the file and line, not just the concept.
- Separate "what" from "why": explain the reason for a required change, not just that it must change.
- Acknowledge the work: start threads with neutral language, not judgment.
- Distinguish opinion from requirement: use prefixes consistently so contributors know what is blocking and what is optional.

## Handling first-time contributors

- Apply the same gate criteria, but weight mentorship over throughput.
- Suggest, don't demand, style fixes on a first PR.
- If a PR needs significant work, offer to pair or provide an example rather than just listing what is wrong.
- Approve once criteria are met — do not hold a PR for minor nits that can be addressed in a follow-up.
