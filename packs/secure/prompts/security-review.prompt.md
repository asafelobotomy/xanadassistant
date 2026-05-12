---
mode: ask
description: "Review the attached code or diff for OWASP Top 10:2025 security issues."
---

Review the attached code or diff for OWASP Top 10:2025 security issues.

Use the `secureReview` skill for category definitions and output format.

Output a table:

| Severity | OWASP | File:Line | Finding | Recommended fix |
|---|---|---|---|---|

If zero findings: output one line — "No security findings."

Do not include style, performance, or maintainability observations in this review. Security findings only.
