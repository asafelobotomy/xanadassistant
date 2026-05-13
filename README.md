# xanadAssistant

A lifecycle manager for GitHub Copilot surface files in VS Code workspaces.

xanadAssistant installs, updates, repairs, and restores a curated set of Copilot surface files — agents, skills, hooks, prompts, and instructions — into any VS Code workspace. It tracks managed state in a lockfile, backs up user content before overwriting it, and exposes a structured JSON CLI for use by Copilot agents and MCP tools.

## What it manages

| Surface | Installed to | Default ownership |
|---|---|---|
| `copilot-instructions.md` | `.github/` | `local` (merge-safe) |
| Instructions | `.github/instructions/` | `local` |
| Prompts | `.github/prompts/` | `local` |
| Agents | `.github/agents/` | `plugin-backed-copilot-format` |
| Skills | `.github/skills/` | `plugin-backed-copilot-format` |
| Hook scripts | `.github/hooks/scripts/` | `local` |
| MCP config | `.vscode/mcp.json` | `local` (merge-safe) |

Optional packs (e.g. `lean`) add further surfaces when selected at setup time.

## Requirements

- Python 3.10+
- stdlib only — no third-party runtime dependencies

## Quick install

For a fresh workspace with no prior install, fetch the bootstrap runner and
follow the step-by-step guide in [INSTALL.md](INSTALL.md).

```sh
curl -fsSL https://raw.githubusercontent.com/asafelobotomy/xanadassistant/main/xanadBootstrap.py | python3 - apply --workspace . --non-interactive --json
```

If you have a local checkout of this repo, you can also run the lifecycle CLI
directly — see [Usage](#usage) below.

## Usage

Point `xanadAssistant.py` at a consumer workspace and at its own repo root:

```sh
python3 xanadAssistant.py <command> --workspace <path> --package-root <path> [--json]
```

### Commands

| Command | Description |
|---|---|
| `inspect` | Read-only. Report install state, managed-file findings, and repair needs. |
| `check` | Read-only. Classify each managed file as clean, stale, missing, malformed, or retired. |
| `interview` | Read-only. Emit structured questions needed to complete a lifecycle mode. |
| `plan setup` | Compute a first-time install plan without writing anything. |
| `plan update` | Compute an update plan without writing anything. |
| `plan repair` | Compute a repair plan without writing anything. |
| `plan factory-restore` | Compute a full-reset plan without writing anything. |
| `apply` | Apply a previously computed plan. Creates a backup before the first write. |
| `update` | Inspect + plan + apply in one step. |
| `repair` | Inspect + repair plan + apply in one step. |
| `factory-restore` | Backup + purge + reinstall from policy. |

All commands accept `--json` for a single structured JSON response or `--json-lines` for streamed NDJSON events.

### This workspace (development)

```sh
# Run all tests
python3 -m unittest discover -s tests -p 'test_*.py'

# LOC gate
python3 scripts/check_loc.py

# Regenerate manifest and catalog after any policy or template change
python3 scripts/generate.py

# Inspect this workspace
python3 xanadAssistant.py inspect --workspace . --package-root . --json

# Check this workspace
python3 xanadAssistant.py check --workspace . --package-root . --json

# Plan a setup into another workspace
python3 xanadAssistant.py plan setup --workspace <path> --package-root . --json --non-interactive
```

## Lifecycle processes

### Setup

First-time install of all managed surfaces into a workspace that has no existing xanadAssistant install.

1. Run `inspect` — confirms the workspace is in `not-installed` state.
2. Run `interview` — collects your choices: profile, optional packs, personalisation tokens (response style, autonomy level, agent persona, testing philosophy), and whether to enable MCP hooks.
3. Run `plan setup` — computes the full write set; no files are written yet; conflicts and backup needs are flagged.
4. Run `apply` — backs up any pre-existing content, writes all managed files with token substitution, and writes the lockfile recording your answers, hashes, profile, packs, and MCP state.

```sh
python3 xanadAssistant.py plan setup --workspace <path> --package-root <path> --json
python3 xanadAssistant.py apply --workspace <path> --package-root <path> --plan <plan-file>
```

> For a fresh workspace, see [INSTALL.md](INSTALL.md) and the bootstrap runner.
> Once installed, the `xanadLifecycle` Copilot agent (`.github/agents/xanadLifecycle.agent.md`) handles all future lifecycle operations.

---

### Update

Refresh stale or missing managed files in a workspace that is already installed. Re-reads your existing lockfile so no re-interview is needed.

1. Run `inspect` — confirms install state is `installed` and identifies stale or missing files.
2. Reads all previous answers (profile, packs, personalisation, MCP state) from the lockfile.
3. Run `plan update` — hashes each managed file; only stale and missing files appear in the write set.
4. Run `apply` — backs up changed files, writes only the stale/missing entries, and updates the lockfile with new hashes.

```sh
# One-step shorthand
python3 xanadAssistant.py update --workspace <path> --package-root <path> --json
```

---

### Factory restore

Full reset of a workspace that already has xanadAssistant installed. Use this when you want a clean slate while keeping your existing profile and pack choices.

1. Requires an existing install (use **setup** for first-time installs).
2. Backs up all currently installed managed files.
3. Purges all managed content from the workspace.
4. Reinstalls from policy from scratch, reusing your lockfile answers for profile, packs, and personalisation.
5. Rewrites the lockfile with updated hashes.

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

```
xanadAssistant.py            # thin entry point
scripts/lifecycle/
  xanadAssistant.py          # public module and re-export surface
  _xanad/                     # lifecycle engine (small focused submodules)
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
  vscode/mcp.json             # consumer MCP server config
agents/                       # → .github/agents/ in consumer workspaces
skills/                       # → .github/skills/ in consumer workspaces
packs/                        # optional pack surfaces (e.g. lean)
hooks/scripts/                # → .github/hooks/scripts/ in consumer workspaces
docs/contracts/               # frozen contracts — change requires explicit discussion
tests/                        # unittest suite
```

### Layers

| Layer | Purpose |
|---|---|
| `core` | Required for all lifecycle guarantees. Never depends on a pack. |
| `pack` | Optional capability module selected at setup time. |
| `profile` | Behavior preset that changes defaults without adding content. |
| `catalog` | Discovery metadata for Copilot and maintainers. |

### Packs

| Pack | Status | Description |
|---|---|---|
| `lean` | active | Terse workflow helpers and brevity-oriented defaults |
| `memory` | planned | Durable memory and recall features |
| `review` | planned | Code review and audit workflows |
| `research` | planned | Research and synthesis workflows |
| `workspace-ops` | planned | Workspace automation and maintenance helpers |

### Profiles

| Profile | Status | Description |
|---|---|---|
| `balanced` | active | Standard detail and guidance |
| `lean` | active | Concise output; includes `lean` pack by default |
| `ultra-lean` | planned | Minimum viable output density |

## MCP servers

When hooks are enabled, the following MCP servers are installed into `.github/hooks/scripts/`:

| Server | Enabled by default | Description |
|---|---|---|
| `xanadWorkspaceMcp.py` | yes | xanadAssistant lifecycle tools (`lifecycle.*`) |
| `gitMcp.py` | yes | Full local + remote git workflow (22 tools) |
| `webMcp.py` | yes | DuckDuckGo search and URL fetch |
| `timeMcp.py` | yes | Current time, elapsed duration, timezone conversion |
| `securityMcp.py` | yes | OSV vulnerability lookup and deps.dev health check |
| `mcpSequentialThinkingServer.py` | yes | Sequential reasoning bridge |
| `githubMcp.py` | no | GitHub REST API (repos, issues, PRs, Actions, code search) |
| `sqliteMcp.py` | no | Query and inspect local SQLite databases |

## Lockfile

Each managed workspace maintains `.github/xanadAssistant-lock.json` recording the installed package name, version, managed file hashes, selected profile, selected packs, and ownership mode per surface. The engine uses this to detect drift and plan safe updates.

## Contributing

1. Read before modifying — never edit a file not opened in the current session.
2. `template/setup/install-manifest.json` and `catalog.json` are generated — run `python3 scripts/generate.py` after any policy or template content change.
3. `template/copilot-instructions.md` must retain `{{}}` tokens — do not resolve them in the template.
4. Contracts in `docs/contracts/` are frozen — changes require explicit discussion.
5. Engine modules under `scripts/lifecycle/_xanad/` must stay ≤ 250 lines each; hook scripts ≤ 380 lines (warning), 400 lines (hard limit).
6. No third-party runtime dependencies — stdlib only.

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
