---
name: mlopsDataPipelines
description: "Data pipeline conventions — versioning, feature engineering discipline, and leakage prevention."
---

# mlopsDataPipelines

Use this skill when designing, reviewing, or debugging ML data pipelines.

## Core data pipeline principles

1. **Version data, not just code** — a model is only reproducible if its training data is versioned.
2. **No leakage across splits** — train, validation, and test sets must be split before any transformation.
3. **Pipelines are code** — data transformations belong in version-controlled, testable pipeline stages.
4. **Fail fast on schema drift** — validate schema and statistics at pipeline entry, not at model training time.
5. **Document every transformation** — every feature engineering step must be documented and reversible.

## Data versioning with DVC

```bash
# Track a dataset
dvc add data/raw/dataset.csv
git add data/raw/dataset.csv.dvc .gitignore
git commit -m "data: add raw dataset v1"

# Push to remote
dvc push

# Reproduce a specific version
git checkout <commit>
dvc checkout
```

### .dvc remote configuration

```ini
[core]
    remote = myremote
[remote "myremote"]
    url = s3://my-bucket/dvc-store
```

Never commit raw data files directly. Always use `.dvc` pointer files.

## Train/validation/test split discipline

```python
from sklearn.model_selection import train_test_split

# CORRECT — split first, then fit transformers only on train
X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.3, random_state=42)
X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)   # fit only on train
X_val_scaled   = scaler.transform(X_val)          # transform only
X_test_scaled  = scaler.transform(X_test)
```

```python
# WRONG — fitting on all data leaks test statistics into training
scaler.fit(X)                          # ← data leakage
X_scaled = scaler.transform(X)
X_train, X_test = train_test_split(X_scaled, ...)
```

## Schema validation

Validate at pipeline entry using Great Expectations or a lightweight custom check:

```python
def validate_schema(df: pd.DataFrame, expected_columns: list[str], expected_dtypes: dict) -> None:
    missing = set(expected_columns) - set(df.columns)
    if missing:
        raise ValueError(f"Schema drift: missing columns {missing}")
    for col, dtype in expected_dtypes.items():
        if df[col].dtype != dtype:
            raise TypeError(f"Column '{col}' expected {dtype}, got {df[col].dtype}")
```

## Feature engineering discipline

| Rule | Why |
|---|---|
| All transformers fitted on train only | Prevents leakage |
| Transformers serialised with model | Ensures identical preprocessing at serving time |
| No manual edits to raw data | Use a reproducible transform stage instead |
| Feature importance logged per run | Documents which features matter |

## Anti-patterns

| Anti-pattern | Fix |
|---|---|
| Raw CSV committed to git | Use DVC with remote storage |
| Scaler/encoder fitted on full dataset | Always fit on train split only |
| Hard-coded column names in notebooks | Define schema as a config or constant |
| No validation between pipeline stages | Add schema + statistics checks at each stage boundary |
