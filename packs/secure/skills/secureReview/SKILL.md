---
name: secureReview
description: "Security-focused code review against OWASP Top 10:2025 — finding classification and output format."
---

# Secure Review

Use this skill in workspaces with the secure pack selected.

Perform security-focused code review against the OWASP Top 10:2025. For each finding, map it to a specific OWASP category.

## OWASP Top 10:2025 categories

| ID | Category | Common patterns to look for |
|---|---|---|
| A01 | Broken Access Control | Missing authorization checks, IDOR, path traversal, privilege escalation |
| A02 | Security Misconfiguration | Default credentials, overly permissive CORS, debug endpoints in production, unnecessary features enabled |
| A03 | Software Supply Chain Failures | Unpinned dependencies, unsigned artifacts, build system trust issues |
| A04 | Cryptographic Failures | Plaintext sensitive data, weak algorithms (MD5/SHA1 for secrets), hardcoded keys, insufficient key length |
| A05 | Injection | SQL injection, command injection, LDAP injection, template injection, XSS |
| A06 | Insecure Design | Missing rate limiting, no fraud controls, unsafe business logic, design decisions that assume trust |
| A07 | Authentication Failures | Weak password policy, missing MFA, session fixation, predictable session tokens |
| A08 | Software or Data Integrity Failures | Deserialization of untrusted data, unsigned updates, missing integrity checks |
| A09 | Security Logging and Alerting Failures | No audit trail, logging sensitive data, no alerting on critical events |
| A10 | Mishandling of Exceptional Conditions | Stack traces exposed to users, unsafe exception paths, resource leaks on error |

## Review output format

Produce a table for every code review:

| Severity | OWASP | File:Line | Finding | Recommended fix |
|---|---|---|---|---|

- Severity: Critical / High / Medium / Low
- OWASP: category ID (A01–A10) or "N/A" if not an OWASP category
- If zero findings: output one line — "No security findings."

## Secure-by-default writing rules

When writing new code (not reviewing), apply these without annotation unless they expand scope:
- Parameterized queries for all database access (never string concatenation)
- Input validation at all trust boundaries
- Least-privilege defaults for IAM, file permissions, and service accounts
- No sensitive data in logs, URLs, or error messages
- Dependency versions pinned to a specific release, not a range that includes major versions

## What to skip

Do not report findings that are purely stylistic, have no security relevance, or require access to runtime configuration you cannot see. Speculation is not a finding.

## Review comment format

Use these prefixes when giving code review feedback:

- `critical:` — Critical severity finding (A01–A10)
- `high:` — High severity finding
- `medium:` — Medium severity finding
- `low:` — Low severity finding, accepted risk, or informational
- `nit:` — Style or formatting issue with no security relevance
