---
name: mlopsModelServing
description: "Model serving — registry, versioning, A/B testing, canary deployments, and drift monitoring."
---

# mlopsModelServing

Use this skill when deploying, versioning, or monitoring ML models in production.

## Core serving principles

1. **Register before serving** — every production model must be registered in a model registry with a version tag.
2. **Stage gates are mandatory** — models must progress through Staging → Production, not straight to Production.
3. **Canary before full rollout** — route a small traffic slice to the new model before full promotion.
4. **Monitor continuously** — data drift and prediction drift are inevitable; detect them early.
5. **Rollback must be one command** — always keep the previous model version registered and ready to serve.

## Model registry conventions

### MLflow model registry

```python
import mlflow

# Register a model
result = mlflow.register_model(
    model_uri=f"runs:/{run_id}/model",
    name="my-classifier",
)

# Transition to Staging
client = mlflow.MlflowClient()
client.transition_model_version_stage(
    name="my-classifier",
    version=result.version,
    stage="Staging",
)
```

### Versioning contract

| Field | Required | Example |
|---|---|---|
| Model name | Yes | `fraud-detector` |
| Version | Yes | Semantic (`v1.2.0`) or auto-incremented |
| Stage | Yes | `None → Staging → Production → Archived` |
| Dataset version | Yes | DVC tag or S3 URI |
| Training run ID | Yes | Links to experiment metadata |
| Champion metric | Yes | e.g., `val_auc=0.94` |

## Canary deployment pattern

```yaml
# Example: route 10% of traffic to new model
- model: fraud-detector-v2
  traffic: 10
- model: fraud-detector-v1
  traffic: 90
```

- Canary period: minimum 24 hours (longer for low-traffic services).
- Promotion criteria: new model must match or exceed champion on live traffic metrics.
- Rollback trigger: error rate increase > 1% or primary metric degradation > 2%.

## A/B testing

- Use a stable hash of the request ID (not random) to ensure consistent assignment.
- Log which model version served each prediction — required for post-hoc analysis.
- Define the success metric and minimum detectable effect before starting.

## Drift monitoring

| Drift type | What to monitor | Alert threshold |
|---|---|---|
| Data drift | Input feature distributions vs. training baseline | PSI > 0.2 or KS p-value < 0.05 |
| Prediction drift | Output distribution vs. baseline | Distribution shift by > 5% |
| Concept drift | Model accuracy vs. ground-truth labels | Primary metric drops > 3% |
| Serving drift | Latency percentiles (p50, p95, p99) | p99 > 2× baseline |

## Rollback procedure

```bash
# MLflow: transition previous version back to Production
mlflow models set-version-tag -n my-classifier -v <prev-version> --key stage --value Production
# Or via client:
client.transition_model_version_stage(name="my-classifier", version=<prev-version>, stage="Production")
```

## Anti-patterns

| Anti-pattern | Fix |
|---|---|
| Deploying directly to Production | Always go through Staging |
| No model registry | Use MLflow, Vertex AI, or SageMaker Model Registry |
| Model artefact committed to git | Store in object storage; log URI in registry |
| Serving the same model version for months without drift check | Schedule weekly drift evaluation |
