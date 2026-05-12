---
mode: ask
description: "Draft a pull request title and body for an OSS contribution."
---

You are helping draft a GitHub pull request for an open-source project.

Apply the ossCodeReview skill to verify the PR meets the project's gate criteria, and apply the ossChangelog skill if the change needs a changelog entry.

---

## Inputs

Provide as many of the following as you have:

- **What changed**: A brief description of the change.
- **Why**: The motivation or linked issue number (e.g., `Closes #42`).
- **Breaking change**: Yes / No / Unsure.
- **Tests added**: Yes / No / What's covered.
- **Changelog entry**: Yes / No / Draft text.

---

## Output format

### PR title

Follow Conventional Commits format:
```
<type>(<optional-scope>): <summary in imperative mood, ≤72 chars>
```

Examples:
- `feat(auth): add OAuth2 PKCE support`
- `fix(parser): handle empty input without panic`
- `docs: update CONTRIBUTING with DCO instructions`
- `feat!: remove deprecated v1 API endpoints`

### PR body

```markdown
## Summary

<!-- One paragraph: what this changes and why. -->

## Changes

<!-- Bullet list of the specific changes made. -->

## Related issues

Closes #<!-- issue number -->

## Testing

<!-- Describe what tests were added or updated. -->

## Changelog

<!-- Paste the changelog entry you added, or write "No user-facing change." -->

## Checklist

- [ ] Tests pass locally
- [ ] Changelog entry added under `## [Unreleased]`
- [ ] Documentation updated (if public API changed)
- [ ] DCO sign-off on all commits (if required)
- [ ] No new lint warnings
```

---

Draft the PR title and body now.
