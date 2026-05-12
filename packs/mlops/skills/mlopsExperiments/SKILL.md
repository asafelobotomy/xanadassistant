---
name: mlopsExperiments
description: "ML experiment tracking — reproducibility, hyperparameter discipline, and metric logging conventions."
---

# mlopsExperiments

Use this skill when designing, running, or reviewing machine learning experiments.

## Core experiment principles

1. **Reproducibility is non-negotiable** — every run must be fully reproducible from logged parameters alone.
2. **Track everything before tuning** — log hyperparameters, dataset versions, random seeds, and environment specs at run start.
3. **One metric is the north star** — choose a primary metric before the experiment; do not cherry-pick after.
4. **Compare against a baseline** — every experiment needs a documented baseline run to compare against.
5. **Don't commit notebook outputs** — strip outputs before committing; use experiment tracking for results.

## Required logged artifacts

| Artifact | Examples |
|---|---|
| Dataset version | DVC tag, S3 URI with hash, dataset registry entry |
| Model architecture | Config file, architecture class name + parameter count |
| Hyperparameters | Learning rate, batch size, scheduler, optimizer |
| Random seeds | `random.seed()`, `np.random.seed()`, `torch.manual_seed()` |
| Environment | Python version, library versions (`pip freeze` or `conda env export`) |
| Evaluation metrics | All primary and secondary metrics on validation set |
| Run duration | Wall-clock time and compute spec (GPU type, count) |

## Experiment tracking tools

### MLflow

```python
import mlflow

with mlflow.start_run(run_name="baseline-lr-0.001"):
    mlflow.log_params({"lr": 0.001, "batch_size": 32, "seed": 42})
    mlflow.log_metrics({"val_loss": 0.23, "val_acc": 0.91}, step=epoch)
    mlflow.log_artifact("model.pkl")
```

### Weights & Biases

```python
import wandb

run = wandb.init(project="my-project", config={"lr": 0.001, "batch_size": 32})
wandb.log({"val_loss": 0.23, "val_acc": 0.91})
wandb.finish()
```

## Hyperparameter discipline

- Define the search space before the sweep — do not add ranges mid-run.
- Use a structured config file (YAML/JSON) rather than inline constants.
- Log the config file as an artifact alongside model weights.
- Prefer grid search for ≤3 parameters; random or Bayesian search for larger spaces.

## Notebook hygiene

| Rule | Why |
|---|---|
| Strip cell outputs before commit | Prevents binary diffs, potential data leakage |
| One notebook per experiment | Avoids cell-ordering bugs |
| Pin cell execution order | Use `nbconvert --execute` to verify clean re-run |
| Parameterise with Papermill or Hydra | Enables reproducible batch runs |

## Anti-patterns

| Anti-pattern | Fix |
|---|---|
| Hardcoded dataset path (`/home/user/data`) | Use a config file or env variable |
| Result reported only on test set | Always validate on held-out val set; reserve test for final eval |
| No seed set | Set all random seeds at experiment start |
| Hyperparameters edited after seeing results | Lock config before evaluating; new config = new run |
