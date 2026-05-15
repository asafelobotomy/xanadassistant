---
name: ciPreflight
description: "Use when: running pre-commit or pre-push CI-equivalent checks in any workspace — discovers the project's CI workflow commands using workspace tools, filters for local executability, scopes to staged changes, and runs checks cheapest-first before delegating failures."
---

# CI Preflight

> Skill metadata: version "1.0"; tags [commit, preflight, ci, workflow, generic]; recommended tools [codebase, runCommands, editFiles, askQuestions].

Discover and execute a workspace's CI checks locally before commit or push,
using workspace tools to read actual workflow definitions rather than assuming
knowledge of the project's specific tooling or conventions.

## When to use

- Before any commit or push when CI check coverage is needed
- When the project's CI checks are unknown, vary by workspace, or may have changed
- When the workspace may use any language, framework, or build system

## When not to use

- When the workspace has a project-specific preflight skill — prefer that skill
  over this generic one (it will know the project's exact commands and repair
  steps)
- When the user has explicitly asked to skip verification
- When there is nothing staged and no proposed file list to verify against

## Steps

### 0. Check memory cache

Call `memory_get(agent="shared", key="ci.commands")`.
- If it returns a cached command list (not a "No active fact" message), skip Steps 1–4 and proceed directly to Step 5 with those commands.
- If it returns unavailable or "No active fact", continue to Step 1.

### 1. Discover CI workflow files

Use the `codebase` tool (or run `ls .github/workflows/` with `runCommands`) to
list all files under `.github/workflows/`.

For each file found, read its full contents with the `codebase` tool.

**Keep** a file if its `on:` key includes `push` or `pull_request`.
**Skip** a file that only triggers on `schedule`, `workflow_dispatch`,
`release`, or deployment events — those require infrastructure or secrets that
cannot be reproduced locally.

### 2. Extract locally-executable run steps

For each kept workflow file, collect every `jobs.<id>.steps[]` entry that has
a `run:` key.

**Exclude** a step if its `run:` block:
- References `${{ secrets.* }}` — requires external credentials
- References environment variables that are only available on GitHub Actions
  runners (e.g. `GITHUB_RUN_ID`, `RUNNER_TOOL_CACHE`)
- Invokes `actions/deploy`, upload-artifact, download-artifact, or any step
  that publishes or transfers artefacts
- Calls a deployment or release tool (`gh release`, `npm publish`,
  `docker push`, etc.)

**Include** a step if its `run:` is a self-contained interpreter or tool
invocation that operates on local files (e.g. `python3 ...`, `npm test`,
`make check`, `go test ./...`, `cargo test`, `./gradlew test`).

### 3. Scope to staged changes

Run `git diff --cached --name-only` with `runCommands` to get the staged file
list.

Narrow the extracted check list by that scope:
- Skip Python-specific checks if no `.py` files or test-config files are staged
- Skip Node checks if no `.js`, `.ts`, or `package.json` are staged
- Keep any check whose scope cannot be narrowed (e.g. a global lint or a
  manifest freshness gate that affects the whole repo)

### 4. Fall back to project-structure detection

If Step 2 found no usable run steps (no workflow files, or all steps were
excluded), detect the test runner from workspace files using the `codebase`
tool:

| Signal file or folder | Inferred command |
|---|---|
| `tests/` with `test_*.py` files | `python3 -m unittest discover -s tests -p 'test_*.py'` |
| `pytest.ini`, `pyproject.toml` with `[tool.pytest]` | `python3 -m pytest` |
| `package.json` with a `test` script | `npm test` |
| `Makefile` with a `test` target | `make test` |
| `go.mod` | `go test ./...` |
| `Cargo.toml` | `cargo test` |
| `Gemfile` with rspec | `bundle exec rspec` |

Once you have a command list (from Step 1–2 or fallback detection), call
`memory_set(agent="shared", key="ci.commands", value=<command list as JSON string>)`
so future preflight runs skip discovery.

### 5. Order checks cheapest-first

Group extracted commands into tiers and run in this order, stopping at the
first blocker before running later tiers:

1. **Static / format / lint** — fastest, no side effects
   (e.g. `ruff check`, `eslint`, `golangci-lint`, budget/LOC scripts)
2. **Type checks** — moderate cost (e.g. `mypy`, `tsc --noEmit`)
3. **Unit tests** — moderate to expensive
4. **Integration / e2e tests** — most expensive; skip if not in scope of
   staged changes

When tier assignment is ambiguous, prefer the order commands appear in the
workflow file — the project author likely ordered them by cost already.

### 6. Execute and handle each result

Run each command with `runCommands`. For each result:

| Outcome | Action |
|---|---|
| Exit 0 | Continue to the next check |
| Stale generated artifact (exit nonzero + recognisable regen command in output) | Re-run the generator with `runCommands`, re-stage outputs with `editFiles`, re-run the check |
| Unit or lint test failure | Delegate to `Debugger` with the exact failure output and staged file list; apply the minimal fix returned; re-run the failing check |
| Budget / LOC / format violation | Surface the exact violation output to the user; ask: fix now, or accept residual risk before proceeding |
| Template-safety violation (unresolved `{{}}` tokens in a template file) | Block — do not commit until resolved |
| Step requires secrets or infra (detected mid-run) | Skip; note in summary — not a blocker |
| Any other nonzero exit | Surface exact stdout + stderr; use `askQuestions` to ask the user how to proceed |

### 7. Return a summary to the caller

Return:
- The workflow files read and the commands extracted from them (or "detected
  from project structure" if Step 4 was used)
- Which checks were skipped, and why
- Whether any artifacts were regenerated and staged
- A clear **pass**, **block**, or **residual-risk** outcome for the caller to
  act on

## Verify

- [ ] Workflow files listed and read with a tool — not assumed from memory
- [ ] Only push/PR-triggered workflows included; others explicitly skipped
- [ ] Steps requiring secrets or external infra excluded and noted
- [ ] `git diff --cached --name-only` used to scope checks to staged files
- [ ] Commands executed in cheapest-first order; stopped at first blocker
- [ ] Stale artifacts repaired and restaged before re-running the failing check
- [ ] `Debugger` delegated to for test/lint failures, not ad-hoc guesses
- [ ] Summary returned with pass / block / residual-risk outcome
- [ ] `memory_get(agent="shared", key="ci.commands")` checked before re-scanning workflow files
- [ ] `memory_set(agent="shared", key="ci.commands", ...)` called after discovering commands
