---
mode: ask
description: "Design or review a machine learning experiment with reproducibility and leakage discipline."
---

You are helping design or review a machine learning experiment.

Apply the mlopsExperiments skill for tracking, reproducibility, and hyperparameter discipline. Apply the mlopsDataPipelines skill to check for data leakage and split correctness. Apply the mlopsReview skill to flag any blocking issues before proposing a final design or verdict.

---

## Inputs

Provide as many of the following as you have:

- **Task**: Design a new experiment / Review an existing experiment / Debug a failing run.
- **Model type**: e.g., gradient boosting, transformer, CNN, logistic regression.
- **Dataset**: Name, version, size, and how it is versioned (DVC, S3, etc.).
- **Objective metric**: e.g., validation AUC, F1 on minority class, RMSE.
- **Baseline**: Current benchmark result (or "none" if this is the first experiment).
- **Existing code or config**: Paste relevant training script, notebook cells, or config file.
- **Problem description**: What is failing, missing, or unclear?

---

## Output

For a **new experiment design**: produce a structured experiment plan:

```
## Experiment plan

### Objective
[Primary metric and target value]

### Dataset
- Version: [DVC tag / S3 URI]
- Split strategy: [train/val/test ratios, stratification, time-based if applicable]

### Model and hyperparameters
- Architecture: [class / framework]
- Hyperparameter search space: [table or list]

### Reproducibility checklist
- [ ] Random seed: [value]
- [ ] Dataset version pinned
- [ ] Environment pinned (requirements.txt / conda env)
- [ ] Experiment tracker configured

### Leakage check
[Explicit statement that transformers will be fit on train only, split before any transformation]
```

For a **review**: produce a tiered findings list using `leakage:`, `reproducibility:`, `data:`, `hygiene:`, `nit:` prefixes, then a verdict.

For a **debug**: identify the root cause (data issue, environment mismatch, implementation bug, or configuration error), show the corrected code, and explain why the original failed.
