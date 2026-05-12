---
mode: ask
description: "Generate a CHANGELOG entry for the current release from git history."
---

You are helping generate a CHANGELOG entry for an open-source project release.

Apply the ossChangelog skill for formatting rules and how to categorize conventional commit types into changelog sections.

If the ossGitLog tool is available, use it to fetch structured commit history for the release range.

---

## Inputs

Provide as many of the following as you have:

- **Version number**: The new version being released (e.g., `1.3.0`).
- **Release date**: Today's date, or leave blank to use today.
- **Commit range**: e.g., `v1.2.0..HEAD` — or leave blank and I will use the last tag.
- **Git log output**: Paste raw `git log --oneline` output if you have it.

---

## Output format

Produce a `CHANGELOG.md` entry block ready to paste:

```markdown
## [VERSION] - YYYY-MM-DD

### Added
- (new features with PR or issue references where available)

### Changed
- (changes to existing behavior; prefix breaking changes with **BREAKING:**)

### Fixed
- (bug fixes with issue references)

### Security
- (security fixes — always include even if short)

### Removed
- (removed features)

### Deprecated
- (features deprecated in this release)
```

Omit empty sections. Put `Security` first when present.

Also output the comparison link to add at the bottom of CHANGELOG.md:

```
[VERSION]: https://github.com/OWNER/REPO/compare/vPREV...vVERSION
```

---

Generate the changelog entry now.
