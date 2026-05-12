---
name: devopsCiCd
description: "CI/CD pipeline patterns — GitHub Actions, stage design, environment gates, and artifact discipline."
---

# devopsCiCd

Use this skill when designing, reviewing, or debugging CI/CD pipelines.

## Pipeline stage model

Structure pipelines in ordered stages. Each stage must pass before the next runs.

| Stage | Purpose | Typical jobs |
|---|---|---|
| **Validate** | Fast, cheap checks | Lint, format check, type check |
| **Test** | Correctness | Unit tests, integration tests |
| **Build** | Produce artifacts | Compile, container image, package |
| **Security** | Risk gate | SAST, dependency scan, image scan |
| **Deploy (staging)** | Verify in production-like env | Smoke tests, E2E tests |
| **Deploy (production)** | Release to users | Canary, blue/green, or rolling |

Never skip a stage to speed up delivery. Add a manual approval gate before production deploys when the risk surface is high.

## GitHub Actions conventions

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read          # principle of least privilege — be explicit

jobs:
  test:
    runs-on: ubuntu-24.04  # pin OS version — avoid ubuntu-latest
    steps:
      - uses: actions/checkout@v4    # pin to major version tag, not SHA
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip                 # cache dependencies
      - run: pip install -r requirements.txt
      - run: pytest
```

**Key rules:**
- Always set top-level `permissions:` to limit blast radius.
- Pin action versions to a major tag (`@v4`) at minimum; pin to a commit SHA for third-party actions.
- Cache dependencies to reduce build times and API rate-limit pressure.
- Never echo secrets to logs — use `${{ secrets.FOO }}` not `$FOO` in shell.

## Environment and deployment gates

```yaml
jobs:
  deploy-production:
    environment: production           # triggers required reviewers
    needs: [test, build, security]    # all upstream stages must pass
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy
        run: ./deploy.sh
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
```

- Use GitHub Environments with protection rules for production.
- Pass secrets via `env:` block, not as positional arguments to scripts.

## Artifact discipline

- Build once, deploy the same artifact to staging and production.
- Tag container images with the git SHA: `image:${GITHUB_SHA}`.
- Never build a fresh image in the deploy stage — use the artifact from the build stage.
- Store test results and coverage reports as job artifacts for debugging.

## Common anti-patterns

| Anti-pattern | Fix |
|---|---|
| `uses: actions/checkout@main` | Pin to `@v4` or a SHA |
| `env: SECRET=${{ secrets.X }}` with `echo $SECRET` | Never echo secrets |
| `if: always()` on deploy | Deploy only on success |
| Build image in deploy job | Build once, promote the artifact |
| `permissions: write-all` | Enumerate only what is needed |
