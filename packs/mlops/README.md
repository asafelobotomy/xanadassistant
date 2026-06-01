# mlops pack

The mlops pack installs machine-learning operations defaults — experiment
tracking, data pipeline discipline, model serving conventions, drift
investigation, and ML-specific code review — so that ML-specific risks are
caught as part of the normal development workflow.

## Purpose

Install this pack when the workspace includes ML model training, data pipelines,
or model serving infrastructure. Agents will proactively flag data leakage,
model bias, reproducibility failures, and serving drift before proposing any
change that touches those surfaces.

## Surfaces

| Surface | Contents |
|---|---|
| **Skills** | `mlopsDataPipelines`, `mlopsExperiments`, `mlopsModelServing`, `mlopsReview` |
| **Prompts** | `/mlops-experiment`, `/mlops-drift` |
| **Tool scripts** | `.github/mcp/scripts/mlopsModelCheck.py` when the mlops pack is installed — validates model versioning metadata and flags missing lineage or reproducibility records. Not part of the default core MCP server roster. |

## Token overrides

| Token | MLOps behavior |
|---|---|
| `{{pack:review-depth}}` | Flag data leakage, model bias, reproducibility failures, and serving drift as blocking issues in any ML code review |
| `{{pack:scope-discipline}}` | Proactively flag model versioning, data pipeline changes, and notebook outputs for leakage, drift, and reproducibility risks before proposing any change |

## Interview customization

During setup you can set the review focus:

- **Comprehensive** (default) — flag data leakage, model bias, reproducibility
  failures, and serving drift as blocking issues; proactively flag model
  versioning and data pipeline changes.
- **Reproducibility first** — flag reproducibility failures and data lineage
  breaks as Critical; flag data leakage and bias as High; report serving drift
  and other ML concerns only when directly raised.

Both options override `{{pack:review-depth}}`.
