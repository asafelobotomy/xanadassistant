---
name: ossContributing
description: "OSS contributing workflow — CONTRIBUTING.md structure, DCO/CLA guidance, and contributor onboarding checklist."
---

# ossContributing

Use this skill when a user asks about contribution workflows, CONTRIBUTING.md structure, or how to prepare a first contribution to an open-source project.

## CONTRIBUTING.md structure

A complete `CONTRIBUTING.md` should cover these sections in order:

| Section | Required | Purpose |
|---|---|---|
| Code of Conduct reference | Yes | Link to CODE_OF_CONDUCT.md or inline CoC |
| Getting started | Yes | Fork, clone, branch naming, local setup |
| Development workflow | Yes | How to build, test, lint before opening a PR |
| Commit message format | Yes | Conventional Commits or project-specific format |
| Pull request checklist | Yes | What a PR must include before review |
| DCO / CLA | If applicable | Sign-off requirement or contributor license |
| Release process | Recommended | How maintainers tag and publish releases |
| Issue reporting | Recommended | Bug report template link, reproduction steps expectation |

## Branch naming convention (recommend)

```
feat/<short-description>
fix/<issue-number>-<short-description>
docs/<topic>
chore/<task>
```

## Developer Certificate of Origin (DCO)

If the project uses DCO instead of a CLA, every commit must include a sign-off line:

```
Signed-off-by: Name <email@example.com>
```

Add it automatically with: `git commit --signoff`

Verify with: `git log --oneline | head -5` — confirm each has `(Signed-off-by:)` in the full log.

## PR checklist (recommend including in PR template)

- [ ] Tests added or updated for changed behavior
- [ ] Documentation updated if public API changed
- [ ] Changelog entry added under `## [Unreleased]`
- [ ] No new lint warnings introduced
- [ ] DCO sign-off present on all commits (if required)

## Onboarding checklist for a first contributor

1. Fork and clone the repo.
2. Run `git remote add upstream <project-url>` to track the source.
3. Create a branch: `git checkout -b feat/my-change`.
4. Make changes; run tests before pushing.
5. Open a PR against the project's default branch (usually `main` or `develop`).
6. Address review feedback with additional commits (do not force-push unless asked).
7. Squash or rebase when the maintainer requests it.
