# devops pack

The devops pack installs infrastructure and pipeline defaults — CI/CD design,
container discipline, IaC conventions, deployment safety review, and
secret-hygiene scanning — so that infrastructure changes are treated with the
same rigor as application code.

## Purpose

Install this pack when the workspace includes CI/CD pipelines, Dockerfiles,
infrastructure-as-code, or deployment scripts. Agents will proactively flag
secret-exposure surfaces, privilege-escalation paths, unpinned container images,
missing rollback procedures, and overly broad IAM permissions.

## Surfaces

| Surface | Contents |
|---|---|
| **Skills** | `devopsCiCd`, `devopsContainers`, `devopsInfraAsCode`, `devopsReview` |
| **Prompts** | `/devops-pipeline`, `/devops-incident` |
| **Tool scripts** | `.github/mcp/scripts/devopsEnvCheck.py` when the devops pack is installed — checks environment variable usage for exposed secrets and misconfigured references. Not part of the default core MCP server roster. |

## Token overrides

| Token | DevOps behavior |
|---|---|
| `{{pack:review-depth}}` | Always report Critical and High; also flag hardcoded secrets, overly broad IAM permissions, missing rollback procedures, unencrypted secrets in pipelines, unpinned container images, and changes that could cause a production outage with no safe recovery path |
| `{{pack:scope-discipline}}` | Proactively flag secret-exposure surfaces, privilege-escalation paths, and unrecoverable deployment states even when not asked |

## Interview customization

During setup you can focus the pack on a specific infrastructure area:

- **Pipeline and containers** (default) — prioritize CI/CD pipelines,
  Dockerfiles, and container orchestration safety.
- **IaC and cloud** — prioritize infrastructure-as-code, cloud resource
  definitions, and deployment safety; proactively flag IaC drift, missing
  rollback procedures, and overly broad IAM permissions.

Both options override `{{pack:scope-discipline}}`.
