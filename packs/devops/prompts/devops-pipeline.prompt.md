---
mode: ask
description: "Design or review a CI/CD pipeline for safety, efficiency, and deployment discipline."
---

You are helping design or review a CI/CD pipeline.

Apply the devopsCiCd skill for stage design, GitHub Actions conventions, and artifact discipline. Apply the devopsReview skill to check for safety blockers before proposing any pipeline definition.

---

## Inputs

Provide as many of the following as you have:

- **Task**: Design a new pipeline / Review an existing pipeline / Debug a failing pipeline.
- **Platform**: GitHub Actions / GitLab CI / CircleCI / Jenkins / Other.
- **Language and toolchain**: e.g., Python + pytest, Node.js + Jest, Go.
- **Deployment target**: e.g., AWS ECS, Kubernetes, Fly.io, Vercel.
- **Existing pipeline**: Paste the current workflow file if reviewing or debugging.
- **Problem description**: What is failing or missing?

---

## Output

For a **new pipeline**: produce a complete, annotated workflow file with comments explaining each non-obvious choice.

For a **review**: produce a structured findings list:

```
### Tier 1 — Safety blockers
- secret: [job/step] — [description]

### Tier 2 — Operational risk
- rollback: [job/step] — [description]

### Tier 3 — Hygiene
- hygiene: [job/step] — [description]
```

End with a verdict: **Safe to merge** / **Changes required** / **Blocked — must fix before merge**.

For a **debug**: identify the root cause, show the corrected step, and explain why the original failed.
