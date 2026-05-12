---
name: devopsReview
description: "DevOps review checklist — pipeline safety, secret hygiene, permissions, rollback, and deployment risk."
---

# devopsReview

Use this skill when reviewing CI/CD pipelines, Dockerfiles, IaC definitions, deployment scripts, or infrastructure PRs.

## Review tiers

### Tier 1 — Safety blockers (block merge)

- [ ] No secrets, tokens, or credentials hardcoded in any file (including base64-encoded).
- [ ] No `.env` files or `*.tfvars` with real values committed to git.
- [ ] Container images do not run as root (unless explicitly required and justified).
- [ ] IAM roles / permissions follow least privilege — no `*` actions on `*` resources without justification.
- [ ] Pipelines do not echo or log secret variable values.
- [ ] Third-party actions/modules are pinned to a version tag or digest, not a mutable branch.

### Tier 2 — Operational risk (block merge for production-facing changes)

- [ ] A rollback procedure exists and is documented (feature flag, blue/green swap, prior artifact re-deploy).
- [ ] Production deploys are gated on successful staging and an explicit approval step.
- [ ] State files (Terraform, Pulumi) are remote, locked, and encrypted.
- [ ] Breaking changes to infrastructure (database schema, network topology) have a migration plan.
- [ ] Resource limits (CPU, memory) are set for containerised services.

### Tier 3 — Hygiene (suggest)

- [ ] `.dockerignore` excludes `.git`, `*.env`, dev artifacts.
- [ ] Base image is pinned to a minor version or digest (not `:latest`).
- [ ] Dependency installs use a lock file (`requirements.txt`, `package-lock.json`).
- [ ] Pipeline caches dependencies to reduce build time.
- [ ] IaC variables have `description` and `type` annotations.
- [ ] All CI jobs explicitly set `permissions:`.

## Secret detection patterns

Flag any value that matches these patterns — even in comments:

| Pattern | Example |
|---|---|
| AWS access key | `AKIA[0-9A-Z]{16}` |
| Private key header | `-----BEGIN RSA PRIVATE KEY-----` |
| Generic API key assignment | `api_key = "sk-..."`, `token = "ghp_..."` |
| Base64-encoded long string in config | May indicate encoded credential |

## Rollback checklist

A deployment is reviewable only if it has a rollback path:

1. **Stateless services**: re-deploy the previous image tag.
2. **Database migrations**: migration must be backward-compatible with the previous app version, or the rollback plan must include a down-migration.
3. **Infrastructure changes**: `terraform plan` of the previous state must be available and tested.
4. **Feature flags**: confirm the flag can be disabled without a deploy.

## Review comment format

| Prefix | Meaning |
|---|---|
| `secret:` | Credential or token exposure — must fix |
| `privilege:` | Overly broad permission — must fix |
| `rollback:` | No recovery path — must fix for production |
| `risk:` | Operational risk requiring documented mitigation |
| `hygiene:` | Non-blocking improvement |
| `nit:` | Minor style preference |
