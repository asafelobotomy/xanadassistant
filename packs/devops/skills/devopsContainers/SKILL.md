---
name: devopsContainers
description: "Container and image discipline — Dockerfile best practices, multi-stage builds, layer caching, and image security."
---

# devopsContainers

Use this skill when writing or reviewing Dockerfiles, container compose files, or image-build pipelines.

## Dockerfile best practices

```dockerfile
# Stage 1: build
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: runtime — minimal image
FROM python:3.12-slim AS runtime
WORKDIR /app

# Run as non-root user
RUN addgroup --system app && adduser --system --ingroup app app
USER app

COPY --from=builder /install /usr/local
COPY --chown=app:app src/ ./src/

EXPOSE 8080
ENTRYPOINT ["python", "-m", "src.main"]
```

**Rules:**
- Use multi-stage builds to keep the runtime image minimal.
- Never install dev tools or test dependencies in the runtime stage.
- Always run as a non-root user.
- Use `COPY` not `ADD` (unless you need tar extraction or URL fetching).
- Prefer `ENTRYPOINT` + `CMD` over `CMD` alone for the main process.

## Layer caching discipline

Order Dockerfile instructions from least-frequently-changing to most-frequently-changing:

1. Base image
2. System packages (`apt-get install`)
3. Dependency manifests (`requirements.txt`, `package.json`)
4. Install dependencies
5. Application source code

Copying source code before installing dependencies defeats caching — every code change triggers a full dependency reinstall.

## Image security

| Rule | Why |
|---|---|
| Pin base image to a digest: `python:3.12-slim@sha256:abc123` | Prevents silent upstream changes |
| Scan images with `docker scout` or `trivy` in CI | Catch known CVEs before deploy |
| Do not include `.git/`, secrets, or IDE config in the image | Use `.dockerignore` |
| Set `HEALTHCHECK` | Enables orchestrator to detect unhealthy containers |
| Do not `chmod 777` any directory | Use specific `chown` for the app user |

## .dockerignore

Always include a `.dockerignore`:

```
.git
.github
*.env
*.env.*
__pycache__
*.pyc
.pytest_cache
node_modules
dist
build
.vscode
```

## Image tagging strategy

| Tag | Use |
|---|---|
| `:latest` | Never in production — it is mutable and unpredictable |
| `:${GIT_SHA}` | Immutable; trace from image to commit |
| `:v1.2.3` | Semver release tag |
| `:main` | Mutable branch tag; useful for staging |

Build once with the SHA tag, then add the version tag at release time. Never rebuild the image to tag it.

## Compose conventions

- Use named volumes, not bind mounts, for persistent data in production.
- Set `restart: unless-stopped` for long-running services.
- Never store secrets in `docker-compose.yml` — use `.env` files excluded from git, or a secrets manager.
- Set resource limits (`mem_limit`, `cpus`) to prevent runaway containers.
