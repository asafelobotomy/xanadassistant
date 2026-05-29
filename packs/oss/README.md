# oss pack

The oss pack installs open-source contribution defaults — Conventional Commits
enforcement, license compliance review, changelog discipline, DCO/semver
guidance, and structured git history for release notes.

## Purpose

Install this pack when the workspace is an open-source project that receives
external contributions. Agents will use strict Conventional Commits format,
flag license incompatibilities and breaking changes as blockers, and suggest
changelog entries for any user-visible change.

## Surfaces

| Surface | Contents |
|---|---|
| **Skills** | `ossChangelog`, `ossCodeReview`, `ossContributing`, `ossLicensing` |
| **Prompts** | `/oss-changelog`, `/oss-pr` |
| **MCP** | `ossGitLog.py` — formats git log for changelog generation; `ossLicenseCheck.py` — checks dependency licenses for compatibility |

## Token overrides

| Token | OSS behavior |
|---|---|
| `{{pack:review-depth}}` | Flag license incompatibilities, breaking API changes, and missing changelog entries as blocking issues |
| `{{pack:commit-style}}` | Conventional Commits 1.0 with optional scope; breaking changes require `!` suffix and `BREAKING CHANGE:` footer; summary ≤72 chars, imperative mood, no period |
| `{{pack:scope-discipline}}` | Flag any change affecting contributors (API, CLI, config format, behavior) and suggest a changelog entry or migration note |

## Interview customization

During setup you can choose the breaking change policy:

- **Require version bump confirmation** — do not proceed with a breaking change
  until the major version bump is confirmed.
- **Flag and proceed** (default) — flag the breaking change with the correct
  Conventional Commits footer but proceed without blocking.

Both options override `{{pack:commit-style}}`.
