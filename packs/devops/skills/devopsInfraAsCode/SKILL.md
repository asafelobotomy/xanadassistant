---
name: devopsInfraAsCode
description: "Infrastructure as Code conventions — naming, state management, modularity, and drift detection."
---

# devopsInfraAsCode

Use this skill when writing or reviewing Terraform, Pulumi, or similar IaC definitions.

## Core IaC principles

1. **All infrastructure is code** — no console-click changes. Manual changes create drift.
2. **State is the source of truth** — protect state files; lock before apply.
3. **Plan before apply** — always review `terraform plan` output before `terraform apply`.
4. **Least privilege** — IaC runners need only the permissions required for their resources.
5. **Immutable infrastructure** — replace rather than mutate when possible.

## Terraform conventions

### File organisation

```
infra/
  main.tf          # root module entry point
  variables.tf     # input variable declarations
  outputs.tf       # output value declarations
  versions.tf      # required_providers + terraform version constraint
  modules/
    networking/    # reusable module
    database/
```

### Naming convention

`<project>-<environment>-<resource-type>-<purpose>`

Example: `myapp-prod-sg-api`, `myapp-staging-rds-main`

### Variable discipline

```hcl
variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}
```

- Always include `description` and `type`.
- Use `validation` blocks for values with a bounded set.
- Never use `default = ""` as a placeholder — omit `default` to make the variable required.

### State management

```hcl
terraform {
  backend "s3" {
    bucket         = "myapp-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "myapp-tfstate-lock"   # required for locking
    encrypt        = true
  }
}
```

- Remote state is mandatory for team use.
- Enable encryption at rest.
- Enable state locking (DynamoDB for S3 backend).
- Never commit `terraform.tfstate` or `terraform.tfstate.backup` to git.

### Module design

- Modules should encapsulate a single logical resource group (e.g., a VPC, a database cluster).
- Accept inputs via variables; expose outputs for cross-module references.
- Pin module versions when sourcing from a registry: `version = "~> 3.0"`.
- Avoid deeply nested module calls — prefer flat module trees.

## Drift detection

Run `terraform plan` in CI on a schedule (not just on PR) to detect out-of-band changes:

```yaml
- name: Drift check
  run: terraform plan -detailed-exitcode
  # Exit code 2 = changes present — fail the check
```

## Common anti-patterns

| Anti-pattern | Fix |
|---|---|
| Hardcoded AWS account IDs or region strings | Use `data.aws_caller_identity` and variables |
| `count = 0` to disable a resource | Use `for_each` with an empty map |
| Secrets in `.tfvars` committed to git | Use a secrets manager or CI secret injection |
| `terraform apply` without `plan` in CI | Always plan first; require approval for prod |
| No version constraints on providers | Pin: `version = "~> 5.0"` |
