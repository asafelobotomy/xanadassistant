---
mode: ask
description: "Investigate model or data drift in a production ML service."
---

You are helping investigate drift in a production machine learning service.

Apply the mlopsModelServing skill for drift monitoring thresholds and rollback procedures. Apply the mlopsDataPipelines skill to identify data quality or schema issues. Apply the mlopsReview skill to flag any leakage or reproducibility risks in the proposed remediation.

---

## Inputs

Provide as many of the following as you have:

- **Service name**: The model or service showing drift.
- **Drift type**: Data drift / Prediction drift / Concept drift / Serving latency drift / Unknown.
- **Symptoms**: Observable signals — metric degradation, alert name, distribution shift magnitude.
- **Model version in production**: Current version and when it was deployed.
- **Recent changes**: Data pipeline updates, upstream schema changes, traffic pattern shifts.
- **Monitoring output**: Paste relevant PSI scores, KS test results, metric dashboards, or latency percentiles.

---

## Output

Produce a structured drift investigation report:

```markdown
# Drift Investigation: [Service] — [Drift Type]

## Observed signals
[Summary of symptoms and metric values]

## Probable root causes (ranked)
1. [Most likely cause with evidence]
2. [Second candidate]

## Immediate actions
- [ ] Verify drift is real (not a monitoring false-positive)
- [ ] Check upstream data schema for recent changes
- [ ] Compare current input distribution vs. training baseline
- [ ] Review model serving logs for errors or outliers

## Mitigation options

### Option A — Rollback
- When to use: [condition]
- Command: [rollback command or registry operation]
- Risk: [what you lose by rolling back]

### Option B — Retrain
- When to use: [condition]
- Data requirements: [what new data is needed]
- Estimated timeline: [rough estimate]

### Option C — Targeted patch
- When to use: [condition]
- Change: [specific preprocessing or threshold adjustment]

## Recommended next step
[Single concrete action to take right now]

## Post-resolution
- [ ] Update drift thresholds if current ones are too sensitive or too loose.
- [ ] Document root cause in model card or runbook.
- [ ] Schedule retraining cadence review.
```
