# secure pack

The secure pack installs security-first coding defaults — OWASP Top 10:2025
review coverage, dependency vulnerability scanning, and secret-hygiene
enforcement — without requiring you to ask for them on every task.

## Purpose

Install this pack when security is a first-class concern for the workspace.
Agents will apply secure-by-default choices silently (parameterized queries,
validated inputs, least-privilege defaults) and proactively flag findings during
code review and before every commit.

## Surfaces

| Surface | Contents |
|---|---|
| **Skills** | `dependencyAudit`, `secretScanning`, `secureReview`, `threatModel` |
| **Prompts** | `/security-review`, `/threat-model` |
| **Tool scripts** | `.github/mcp/scripts/secureOsv.py` when the secure pack is installed — OSV database dependency vulnerability lookups. Not part of the default core MCP server roster. |

## Token overrides

| Token | Secure behavior |
|---|---|
| `{{pack:review-depth}}` | Always report Critical and High; flag all OWASP Top 10:2025 entries regardless of severity; report Medium and lower only when actionable |
| `{{pack:scope-discipline}}` | Apply secure-by-default choices without annotation; surface rationale only when the choice might surprise the user |
| `{{pack:secret-guard}}` | Refuse to stage any file containing a probable secret; name the exact file and line |

## Interview customization

During setup you can narrow the OWASP reporting scope:

- **Full OWASP Top 10** (default) — flag all Top 10:2025 entries regardless of
  severity, in addition to all Critical and High findings.
- **Critical and High only** — flag OWASP Top 10:2025 entries only when they
  are Critical or High severity.

Both options override `{{pack:review-depth}}`.
