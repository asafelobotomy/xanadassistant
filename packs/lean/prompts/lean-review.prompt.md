---
description: Code review scoped to Critical and High severity only — blockers, security vulnerabilities, and clear runtime bugs.
---

Review the current changes (or the specified file/diff) for Critical and High severity issues only.

**Severity definitions:**
- **Critical**: security vulnerability, data loss, broken API contract, unsafe/irreversible operation without guard
- **High**: clear bug that fails at runtime, missing null/error check on a reachable code path, incorrect logic that produces wrong output

**Output format — a Markdown table:**

| Severity | File:Line | Finding | Suggested fix |
|---|---|---|---|

If zero Critical or High issues: one line only — `Review: clean (Critical/High)`

**Omit entirely:**
- Advisory feedback
- Style or naming suggestions
- Refactoring opportunities
- Performance observations unless order-of-magnitude regression
- Anything you would prefix with "consider", "you might", or "it would be nice"
- Missing tests unless the absence of a test is itself a Critical/High issue
