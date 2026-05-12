---
name: mlopsReview
description: "ML code review checklist — data leakage, bias, reproducibility, and serving risk."
---

# mlopsReview

Use this skill when reviewing ML code, notebooks, pipeline definitions, or model deployment PRs.

## Review tiers

### Tier 1 — Safety blockers (block merge)

- [ ] No training data or model weights committed to git (check for `.pkl`, `.pt`, `.h5`, `.onnx`, `.csv` > 1 MB).
- [ ] No data leakage: transformers fitted only on training split, not on validation or test data.
- [ ] No test set evaluation during model selection — test set is reserved for final evaluation only.
- [ ] Random seeds set for all stochastic operations (`random`, `numpy`, framework-specific).
- [ ] No hardcoded absolute file paths (`/home/`, `/Users/`, `C:\`).
- [ ] No API keys, credentials, or tokens in notebooks, configs, or pipeline scripts.

### Tier 2 — Reproducibility risk (block merge for production-facing changes)

- [ ] Dataset version is pinned (DVC tag, S3 URI with hash, or registry entry).
- [ ] Model is registered in the model registry before any production deploy.
- [ ] Preprocessing transformers are serialised alongside model weights.
- [ ] Experiment metadata (hyperparameters, metrics, run ID) is logged to an experiment tracker.
- [ ] Canary or A/B rollout plan exists for new model versions going to Production.
- [ ] Rollback procedure is documented and the previous model version is still registered.

### Tier 3 — Hygiene (suggest)

- [ ] Notebook outputs are stripped before commit.
- [ ] Hyperparameters are in a config file, not hardcoded in notebook cells.
- [ ] Feature engineering steps are documented and covered by unit tests.
- [ ] Drift monitoring is configured for the new model version.
- [ ] Model card or documentation is updated alongside the code change.

## Data leakage checklist

Flag any of these patterns:

| Pattern | Risk |
|---|---|
| `scaler.fit(X)` before `train_test_split` | Leaks test statistics into training |
| Same file used as both input and ground truth | Label leakage |
| Time-series data split randomly (not by time) | Future data leaks into training |
| `fillna(df.mean())` applied before split | Leaks global statistics |
| Feature derived from target variable | Target leakage |

## Bias and fairness flags

When the model makes decisions affecting people, flag for review:

- [ ] Protected attributes (race, gender, age) are not used as features unless legally required and documented.
- [ ] Model performance is evaluated across demographic subgroups.
- [ ] Training data source and collection method are documented.

## Review comment format

| Prefix | Meaning |
|---|---|
| `leakage:` | Data leakage detected — must fix |
| `reproducibility:` | Cannot reproduce this result — must fix |
| `bias:` | Potential fairness or bias concern — requires review |
| `data:` | Data versioning or pipeline discipline issue |
| `hygiene:` | Non-blocking improvement |
| `nit:` | Minor style preference |
