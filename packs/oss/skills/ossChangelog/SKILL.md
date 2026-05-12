---
name: ossChangelog
description: "OSS changelog workflow — Keep a Changelog format, versioning discipline, and generating entries from git history."
---

# ossChangelog

Use this skill when a user asks about maintaining a CHANGELOG, generating release notes, or formatting version entries.

## Keep a Changelog format

Follow https://keepachangelog.com/en/1.1.0/ — the most widely adopted OSS changelog convention.

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- (new features)

### Changed
- (changes to existing behavior)

### Deprecated
- (features that will be removed)

### Removed
- (features removed in this release)

### Fixed
- (bug fixes)

### Security
- (security-related fixes — always promote to top of section)

## [1.2.0] - 2024-11-15

### Added
- Feature X (#42)
...

[Unreleased]: https://github.com/owner/repo/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/owner/repo/compare/v1.1.0...v1.2.0
```

## Semantic Versioning rules

| Change type | Version bump | Example |
|---|---|---|
| Breaking change | MAJOR | 1.2.0 → 2.0.0 |
| New backward-compatible feature | MINOR | 1.2.0 → 1.3.0 |
| Bug fix (backward-compatible) | PATCH | 1.2.0 → 1.2.1 |
| Pre-release | Pre-release suffix | 2.0.0-alpha.1 |

**Rule**: `## [Unreleased]` always exists and collects changes since the last tag. At release time, rename it to `## [X.Y.Z] - YYYY-MM-DD` and open a fresh `## [Unreleased]` block.

## Generating entries from git history

Use the `ossGitLog` tool (if the hook is enabled) to get structured commit history for a range.

Manual approach:
```bash
# Commits since last tag
git log $(git describe --tags --abbrev=0)..HEAD --oneline --no-merges

# With conventional commit types
git log $(git describe --tags --abbrev=0)..HEAD --pretty=format:"%s" --no-merges \
  | grep -E "^(feat|fix|docs|refactor|perf|security)(\(.+\))?(!)?:"
```

## Categorizing conventional commits into changelog sections

| Commit type prefix | Changelog section |
|---|---|
| `feat:` | Added |
| `feat!:` or `BREAKING CHANGE:` | Changed (with breaking notice) |
| `fix:` | Fixed |
| `docs:` | (omit unless user-facing) |
| `perf:` | Changed |
| `security:` | Security |
| `refactor:`, `chore:`, `ci:` | (omit unless user-facing) |
| `deprecate:` | Deprecated |
| `remove:` | Removed |

## Do not include

- Merge commits (`--no-merges` flag).
- CI, test, and toolchain commits unless they affect the user.
- Internal refactors unless they affect the public API.
