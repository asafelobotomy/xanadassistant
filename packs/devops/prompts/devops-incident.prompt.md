---
mode: ask
description: "Generate a structured incident response runbook for a service or deployment."
---

You are helping create or fill out an incident response runbook.

Apply the devopsReview skill to identify risk surfaces and rollback options. Apply the devopsCiCd skill when the incident involves a pipeline or deployment.

---

## Inputs

Provide as many of the following as you have:

- **Service name**: The service or component affected.
- **Incident type**: Deployment failure / Performance degradation / Data loss / Security breach / Dependency outage / Other.
- **Current symptoms**: What is the observable failure (error messages, metrics, alerts)?
- **Recent changes**: Deploys, config changes, or infrastructure changes in the last 24 hours.
- **Environment**: Production / Staging / Both.

---

## Output

Produce a structured runbook in Markdown:

```markdown
# Incident Runbook: [Service] — [Incident Type]

## Severity
P1 / P2 / P3 (with criteria)

## Immediate triage (first 15 minutes)
1. Verify the symptom is real (not a monitoring false-positive).
2. Check recent deploys: `git log --oneline -10` or deployment dashboard.
3. Check error rates and latency in observability dashboard.

## Rollback procedure
1. Identify the last known-good version.
2. [Platform-specific rollback command]
3. Verify rollback succeeded: [health check command or URL]

## Mitigation steps
[Ordered steps specific to the incident type]

## Root cause investigation
- Logs to check: [log sources]
- Metrics to review: [metric names]
- Queries to run: [SQL / PromQL / log filter]

## Post-incident
- [ ] Write post-mortem within 48 hours.
- [ ] File follow-up tickets for permanent fixes.
- [ ] Update this runbook with new findings.
```

If the incident type is a deployment failure, include the specific rollback command for the deployment platform. If it involves a database, flag whether the migration is reversible.
