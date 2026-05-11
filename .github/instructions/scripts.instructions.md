---
name: Lifecycle Engine
applyTo: "scripts/lifecycle/**,xanadAssistant.py"
description: "Conventions for the lifecycle engine — public entrypoints, internal module boundaries, event emission, and manifest/lockfile discipline"
---

# Lifecycle Engine Instructions

- `scripts/lifecycle/xanadAssistant.py` is the public lifecycle module and re-export surface. Keep it as the stable import boundary.
- Engine implementation lives under `scripts/lifecycle/_xanad/`. Prefer small focused modules there rather than growing the dispatcher.
- `xanadAssistant.py` at the repo root is a thin wrapper — keep it thin.
- All four modes (`setup`, `update`, `repair`, `factory-restore`) go through the same `build_execution_result → build_plan_result → execute_apply_plan` pipeline.
- **Never write** to `template/setup/install-manifest.json` or `template/setup/catalog.json` by hand — always regenerate via `python3 scripts/generate.py`.
- Emit structured lifecycle events (`event`, `type`, `payload`) on stdout; all prose goes to stderr.
- `--json` requests a single JSON object on stdout; `--json-lines` streams NDJSON events; do not combine them.
- Exit codes are frozen — see `docs/contracts/exit-codes.md`. Do not add new exit codes without updating the contract.
- No third-party runtime dependencies — stdlib only.
- No silent error swallowing: raise or emit a structured `error` event.
- Naming convention: **hyphens** for consumer-facing names (MCP server scripts like `git-mcp.py`, agent/skill directory names like `lifecycle-audit/`); **underscores** for Python-importable modules (lifecycle engine submodules like `_plan_a.py`, MCP helpers like `_xanad_mcp_source.py`).
- Lockfile reads go through `parse_lockfile_state()` and planned lockfile contents go through `build_planned_lockfile()` — never open `.github/xanadAssistant-lock.json` directly in new code paths.
- Schema validation happens at system boundaries (lockfile load, manifest load). Do not re-validate mid-pipeline.
