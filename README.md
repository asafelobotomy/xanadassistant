# xanad-assistant

A lifecycle manager for GitHub Copilot surface files in VS Code workspaces.

xanad-assistant installs, updates, repairs, and restores a curated set of Copilot surface files — agents, skills, hooks, prompts, and instructions — into any VS Code workspace. It tracks managed state in a lockfile, backs up user content before overwriting it, and exposes a structured JSON CLI for use by Copilot agents and MCP tools.

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

## Usage

Point `xanad-assistant.py` at a consumer workspace and at its own repo root:

```sh
python3 xanad-assistant.py <command> --workspace <path> --package-root <path> [--json]
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
python3 xanad-assistant.py inspect --workspace . --package-root . --json

# Check this workspace
python3 xanad-assistant.py check --workspace . --package-root . --json

# Plan a setup into another workspace
python3 xanad-assistant.py plan setup --workspace <path> --package-root . --json --non-interactive
```

## Architecture

```
xanad-assistant.py            # thin entry point
scripts/lifecycle/
  xanad_assistant.py          # public module and re-export surface
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
| `xanad-workspace-mcp.py` | yes | xanad-assistant lifecycle tools (`lifecycle.*`) |
| `git-mcp.py` | yes | Full local + remote git workflow (22 tools) |
| `web-mcp.py` | yes | DuckDuckGo search and URL fetch |
| `time-mcp.py` | yes | Current time, elapsed duration, timezone conversion |
| `security-mcp.py` | yes | OSV vulnerability lookup and deps.dev health check |
| `mcp-sequential-thinking-server.py` | yes | Sequential reasoning bridge |
| `github-mcp.py` | no | GitHub REST API (repos, issues, PRs, Actions, code search) |
| `sqlite-mcp.py` | no | Query and inspect local SQLite databases |

## Lockfile

Each managed workspace maintains `.github/xanad-assistant-lock.json` recording the installed package name, version, managed file hashes, selected profile, selected packs, and ownership mode per surface. The engine uses this to detect drift and plan safe updates.

## Contributing

1. Read before modifying — never edit a file not opened in the current session.
2. `template/setup/install-manifest.json` and `catalog.json` are generated — run `python3 scripts/generate.py` after any policy or template content change.
3. `template/copilot-instructions.md` must retain `{{}}` tokens — do not resolve them in the template.
4. Contracts in `docs/contracts/` are frozen — changes require explicit discussion.
5. Engine modules under `scripts/lifecycle/_xanad/` must stay ≤ 250 lines each; hook scripts ≤ 380 lines (warning), 400 lines (hard limit).
6. No third-party runtime dependencies — stdlib only.

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
