# xanadAssistant

> Lifecycle management for GitHub Copilot surface files in VS Code workspaces.

xanadAssistant installs, updates, repairs, and factory-restores a curated set of Copilot surface files — agents, skills, MCP scripts, prompts, and instructions — into any VS Code workspace.

- **Managed state** — lockfile tracking with backup before every write
- **Copilot-native** — driven by the `xanadLifecycle` agent and MCP tools; no manual CLI knowledge needed
- **Interview-driven setup** — picks your profile, optional packs, personalisation, and installed-agent follow-up knobs before writing anything
- **Structured output** — full JSON CLI for programmatic use by agents and automations

## What it manages

| Surface | Installed to | Default ownership |
| --- | --- | --- |
| `copilot-instructions.md` | `.github/` | `local` (merge-safe) |
| Instructions | `.github/instructions/` | `local` |
| Prompts | `.github/prompts/` | `local` |
| Agents | `.github/agents/` | `plugin-backed-copilot-format` |
| Skills | `.github/skills/` | `plugin-backed-copilot-format` |
| MCP scripts | `.github/mcp/scripts/` | `local` |
| MCP config | `.vscode/mcp.json` | `local` (merge-safe) |
| VS Code settings | `.vscode/settings.json` | `local` (merge-safe) |

Optional packs (e.g. `lean`, `secure`, `tdd`, `docs`) add further surfaces when selected at setup time.

## MCP servers

When hooks are enabled at setup time, xanadAssistant registers these MCP servers in `.vscode/mcp.json`:

| Server | Script | Purpose |
| --- | --- | --- |
| `xanadTools` | `xanadWorkspaceMcp.py` | Workspace lifecycle inspection and maintenance tools |
| `workspaceTesting` | `workspaceTestingMcp.py` | Generic workspace test execution and coverage parsing |
| `git` | `gitMcp.py` | Local git operations |
| `web` | `webMcp.py` | Web search and fetch |
| `devDocs` | `devDocsMcp.py` | DevDocs-backed library documentation lookup |
| `time` | `timeMcp.py` | Time and elapsed-time tools |
| `memory` | `memoryMcp.py` | Persistent, scoped SQLite-backed agent memory — advisory facts, authoritative rules, and FTS-indexed diary |
| `security` | `securityMcp.py` | Dependency vulnerability queries |
| `github` | `githubMcp.py` | GitHub API operations |
| `sqlite` | `sqliteMcp.py` | Workspace-local SQLite read-only query access |
| `filesystem` | `fsMcp.py` | Workspace-bounded file I/O and search |
| `sequential-thinking` | `sequentialThinkingMcp.py` | Structured step-by-step reasoning |

All servers use the `stdio` transport via `uvx`; server ids match `.vscode/mcp.json`, and servers that need workspace scoping receive the relevant environment variables such as `WORKSPACE_ROOT` or `FS_ALLOWED_ROOT`.

Agents should prefer these structured MCP tools over generic terminal or shell execution when the matching server is connected and the task fits the server's contract. If a required server is unavailable or disabled, agents must fall back to the documented native tool or CLI path for that workflow rather than guessing a new shell command.

Default availability matters:

- `github` and `sqlite` are shipped disabled by default in `.vscode/mcp.json` and should be treated as optional until enabled.
- `xanadTools`, `workspaceTesting`, `git`, `web`, `devDocs`, `time`, `memory`, `security`, `filesystem`, and `sequential-thinking` are the default-on server ids agents should reference in prompts and docs.

## Requirements

- Python 3.10+
- The lifecycle core is stdlib-only; hook-enabled MCP use relies on `mcp[cli]`, and `webMcp.py` also uses uvx-managed `httpx`, `markdownify`, and `beautifulsoup4`

## Quick install

### Recommended: just tell Copilot

Open Copilot chat (agent mode) and say:

> **Setup asafelobotomy/xanadassistant**

Copilot fetches the `xanadLifecycle` agent from GitHub, installs it into your
workspace, and drives the full setup — interview, plan, setup, cleanup.
No manual commands needed.

For a step-by-step walkthrough of what happens, see [INSTALL.md](INSTALL.md).

### Manual alternative

If you prefer to run the agent install step yourself before involving Copilot:

```sh
TAG=v0.5.0  # replace with the target release
mkdir -p .github/agents && curl -fsSL \
  "https://raw.githubusercontent.com/asafelobotomy/xanadassistant/${TAG}/agents/xanadLifecycle.agent.md" \
  -o .github/agents/xanadLifecycle.agent.md
```

Then in Copilot chat: **@xanadLifecycle Setup xanadAssistant**

### Without Copilot

> **Note:** Use a Copilot method above when possible. This is a fallback for environments without Copilot agent mode.

```sh
TAG=v0.5.0  # replace with the target release
curl -fsSL "https://raw.githubusercontent.com/asafelobotomy/xanadassistant/${TAG}/xanadBootstrap.py" \
  -o xanadBootstrap.py
python3 xanadBootstrap.py plan setup --workspace . --version "${TAG}" --non-interactive \
  --plan-out .xanadAssistant/tmp/setup-plan.json --json
python3 xanadBootstrap.py setup --workspace . --version "${TAG}" \
  --plan .xanadAssistant/tmp/setup-plan.json --json
```

For a guided setup with interview and options, see [INSTALL.md](INSTALL.md).

Once installed, use Copilot prompts for day-to-day operations: `/setup` (install or refresh), `/update` (pull latest package files), `/bootstrap` (cold-start from a bare workspace).

## CLI reference

> **Note:** Consumer setup and updates run through the `xanadLifecycle` Copilot agent. The CLI is for maintainers and advanced use.

When the `xanadTools` server is connected, lifecycle-oriented agents should prefer the structured `lifecycle_*` MCP tools first and use the CLI as a fallback only when MCP resolution is unavailable.

Point `xanadAssistant.py` at a consumer workspace and at its own repo root:

```sh
python3 xanadAssistant.py <command> --workspace <path> --package-root <path> [--json]
```

### Commands

| Command | Description |
| --- | --- |
| `inspect` | Read-only. Report install state, managed-file findings, and repair needs. |
| `health-check` | Read-only. Classify each managed file as clean, stale, missing, malformed, or retired. |
| `interview` | Read-only. Emit structured questions needed to complete a lifecycle mode. |
| `plan setup` | Compute a first-time install plan without writing anything. |
| `plan update` | Compute an update plan without writing anything. |
| `plan repair` | Compute a repair plan without writing anything. |
| `plan factory-restore` | Compute a full-reset plan without writing anything. |
| `setup` | Apply a previously computed serialized setup plan. Creates a backup before the first write. |
| `update` | Inspect + plan + write in one step. |
| `repair` | Inspect + repair plan + write in one step. |
| `factory-restore` | Backup + purge + reinstall from policy. |
| `health-report` | Collect a maintainer-facing health check report without writing managed files. |

Stale `apply` invocations are retired and return structured migration guidance. Use `setup` for serialized setup plans.

All commands accept `--json` for a single structured JSON response or `--json-lines` for streamed NDJSON events.

### Developer commands

```sh
# Run all tests
python3 -m unittest discover -s tests -p 'test_*.py'

# Run the maintained pre-merge drift gates in repo order
python3 scripts/drift_preflight.py

# LOC gate
python3 scripts/check_loc.py

# Regenerate manifest and catalog after any policy or template change
python3 scripts/generate.py

# Check package-version mirrors against VERSION and update stale references
python3 scripts/check_bump_version.py

# Inspect this workspace
python3 xanadAssistant.py inspect --workspace . --package-root . --json

# Check this workspace
python3 xanadAssistant.py health-check --workspace . --package-root . --json

# Build a shareable maintainer health report for this workspace
python3 xanadAssistant.py health-report --workspace . --package-root . --json

# Plan a setup into another workspace
python3 xanadAssistant.py plan setup --workspace <path> --package-root . --json --non-interactive
```

## Release automation

Pushes to `main` that change [VERSION](VERSION) now publish a GitHub release automatically after the CI checks in [.github/workflows/ci.yml](.github/workflows/ci.yml) pass. The workflow creates the `v<version>` tag if needed and publishes release notes with the full commit changelog since the previous tag.

## Lifecycle processes

### Setup

First-time install of all managed surfaces into a workspace that has no existing xanadAssistant install.

1. Run `inspect` — confirms the workspace is in `not-installed` state.
2. Run `interview` — collects the base choices: profile, optional packs, personalisation tokens (response style, autonomy level, agent persona, testing philosophy), and whether to enable MCP hooks.
3. Run `plan setup` — computes the full write set and emits any installed-agent follow-up questions needed for tokenized agent behavior knobs such as Commit, Docs, Explore, Planner, and Review defaults; no files are written yet; conflicts and backup needs are flagged.
4. Run `setup` — backs up any pre-existing content, writes all managed files with token substitution, and writes the lockfile recording your answers, hashes, profile, packs, MCP state, and agent customization answers for replay.

```sh
python3 xanadAssistant.py plan setup --workspace <path> --package-root <path> --json
python3 xanadAssistant.py setup --workspace <path> --package-root <path> --plan <plan-file>
```

> For a fresh workspace, see [INSTALL.md](INSTALL.md) and the bootstrap runner.
> Once installed, the `xanadLifecycle` Copilot agent (`.github/agents/xanadLifecycle.agent.md`) handles all future lifecycle operations.

---

### Update

Refresh stale or missing managed files in a workspace that is already installed. Re-reads your existing lockfile so no re-interview is needed.

1. Run `inspect` — confirms install state is `installed` and identifies stale or missing files.
2. Reads all previous answers (profile, packs, personalisation, MCP state, and agent customization answers) from the lockfile.
3. Run `plan update` — hashes each managed file; only stale and missing files appear in the write set.
4. Run the top-level `update` command — it backs up changed files, writes only the stale/missing entries, and updates the lockfile with new hashes.

```sh
# One-step shorthand
python3 xanadAssistant.py update --workspace <path> --package-root <path> --json
```

---

### Repair

Targets a workspace with an existing but damaged, incomplete, or drifted xanadAssistant install — missing managed files, corrupted lockfile, or stale managed state. Also the primary path for migrating from a predecessor package.

1. Run `inspect` — reports repair reasons: `managed-drift`, `missing-managed-files`, `malformed-managed-state`, `package_name_mismatch`, etc.
2. Run `plan repair` — computes the minimal write set covering only damaged or missing entries.
3. Run `repair` — backs up affected files, writes repairs, and updates the lockfile.

```sh
# One-step shorthand
python3 xanadAssistant.py repair --workspace <path> --package-root <path> --json
```

---

### Factory restore

Full reset of a workspace that already has xanadAssistant installed. Use this when you want a clean slate while keeping your existing profile and pack choices.

1. Requires an existing install (use **setup** for first-time installs).
2. Backs up all currently installed managed files.
3. Purges managed and retired xanadAssistant content from the workspace.
4. Preserves user-owned unmanaged lookalike files that happen to live under managed directories.
5. Reinstalls from policy from scratch, reusing your lockfile answers for profile, packs, and personalisation.
6. Rewrites the lockfile with updated hashes.

```sh
# One-step shorthand
python3 xanadAssistant.py factory-restore --workspace <path> --package-root <path> --json
```

---

### Migrate

Migration from a predecessor package (`copilot-instructions-template`) to xanadAssistant. Handled automatically via `repair` or `update` — no separate command needed.

- Run `inspect` — reports `package_name_mismatch` or `successor_cleanup_required` in its findings, signalling a predecessor workspace.
- Run `repair` (or `update`) — re-identifies the workspace as `xanadAssistant`, migrates the lockfile schema, and removes retired predecessor-era files (e.g. old agent files in `.github/agents/`).
- The legacy `.github/copilot-version.md` file is preserved for reference during migration.
- After repair/update completes, `inspect` reports clean with no repair reasons.

```sh
python3 xanadAssistant.py inspect --workspace <path> --package-root <path> --json
python3 xanadAssistant.py repair --workspace <path> --package-root <path> --json
```

## Architecture

```text
xanadAssistant.py            # thin entry point
scripts/lifecycle/
  xanadAssistant.py          # public module and re-export surface
  _xanad/                    # lifecycle engine (small focused submodules)
template/
  copilot-instructions.md     # consumer instructions template ({{}} tokens)
  instructions/               # consumer instruction files
  prompts/                    # consumer prompt files
  setup/
    install-policy.json       # source of truth for what gets installed
    install-manifest.json     # generated — never edit by hand
    catalog.json              # generated — never edit by hand
    pack-registry.json        # available optional packs
    profile-registry.json     # available behavior profiles
    agent-registry.json       # configurable installed-agent follow-up questions
  vscode/mcp.json             # consumer MCP server config
agents/                       # → .github/agents/ in consumer workspaces
skills/                       # → .github/skills/ in consumer workspaces
packs/                        # optional pack surfaces (e.g. lean)
mcp/scripts/                  # → .github/mcp/scripts/ in consumer workspaces
docs/contracts/               # frozen contracts — change requires explicit discussion
docs/contracts/examples/      # machine-facing example payloads for contract surfaces
evals/                        # declarative eval suites for top-level skills
tests/                        # unittest suite
tools/xanadEval/              # static analysis helper for prompt, skill, and eval hygiene
```

### Layers

| Layer | Purpose |
| --- | --- |
| `core` | Required for all lifecycle guarantees. Never depends on a pack. |
| `pack` | Optional capability module selected at setup time. |
| `profile` | Behavior preset that changes defaults without adding content. |
| `catalog` | Discovery metadata for Copilot and maintainers. |

### Packs

| Pack | Status | Description |
| --- | --- | --- |
| `lean` | active | Terse workflow helpers and brevity-oriented defaults |
| `secure` | active | Security-first coding defaults with OWASP Top 10:2025 review and dependency vulnerability scanning |
| `tdd` | active | Test-driven development defaults — Red-Green-Refactor discipline, test double guidance, and coverage analysis |
| `oss` | active | Open-source contribution defaults — license compliance, changelog discipline, DCO/semver guidance |
| `docs` | active | Documentation defaults — Diátaxis-structured drafting, API doc conventions, and prose style guidance |
| `devops` | active | DevOps defaults — CI/CD pipeline design, container discipline, IaC conventions, and deployment safety review |
| `mlops` | active | MLOps defaults — experiment tracking, data pipeline discipline, model serving conventions, and drift investigation |
| `shapeup` | active | Shape Up defaults — pitch writing, cycle execution, betting table process, and scope discipline |
| `review` | planned | Code review and audit workflows |
| `research` | planned | Research and synthesis workflows |
| `workspace-ops` | planned | Workspace automation and maintenance helpers |

### Profiles

| Profile | Status | Description |
| --- | --- | --- |
| `balanced` | active | Balanced detail and guidance for normal interactive work |
| `lean` | active | Concise output; includes `lean` pack by default |
| `ultra-lean` | planned | Minimum viable output density for highly structured workflows |

## MCP scripts

When hooks are enabled, the following MCP server scripts are installed into `.github/mcp/scripts/`:

| Server | Enabled by default | Description |
| --- | --- | --- |
| `xanadWorkspaceMcp.py` | yes | xanadAssistant lifecycle tools (`lifecycle_inspect`, `lifecycle_update`, etc.) |
| `memoryMcp.py` | yes | Persistent SQLite-backed agent memory — advisory facts, authoritative rules, and FTS-indexed diary |
| `gitMcp.py` | yes | Full local + remote git workflow (22 tools) |
| `webMcp.py` | yes | DuckDuckGo search and URL fetch |
| `devDocsMcp.py` | yes | DevDocs-backed library documentation lookup |
| `timeMcp.py` | yes | Current time, elapsed duration, timezone conversion |
| `securityMcp.py` | yes | OSV vulnerability lookup and deps.dev health check |
| `fsMcp.py` | yes | Workspace-bounded file I/O and search |
| `sequentialThinkingMcp.py` | yes | Sequential reasoning bridge |
| `githubMcp.py` | no | GitHub REST API (repos, issues, PRs, Actions, code search) |
| `sqliteMcp.py` | no | Query and inspect workspace-local SQLite databases (read-only) |

## Lockfile

Each managed workspace maintains `.github/xanadAssistant-lock.json` recording the installed package name, version, managed file hashes, selected profile, selected packs, and ownership mode per surface. The engine uses this to detect drift and plan safe updates.

## Contributing

1. Read before modifying — never edit a file not opened in the current session.
2. `template/setup/install-manifest.json` and `catalog.json` are generated — run `python3 scripts/generate.py` after any managed source surface change, including agents, skills, prompts, instructions, MCP scripts, packs, setup policy, registries, and template content.
3. `template/copilot-instructions.md` must retain `{{}}` tokens — do not resolve them in the template.
4. Contracts in `docs/contracts/` are frozen — changes require explicit discussion.
5. Engine modules under `scripts/lifecycle/_xanad/` must stay ≤ 250 lines each; MCP scripts use the warning and hard-limit budgets enforced by `scripts/check_loc.py` (default 250 warning / 400 hard, with documented per-file overrides).
6. Keep the lifecycle core stdlib-only; document any hook-runtime MCP dependencies explicitly.
7. Use [docs/maintenance-drift.md](docs/maintenance-drift.md) as the maintainer policy for drift control; CI and local pre-merge checks should go through `python3 scripts/drift_preflight.py`.

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
