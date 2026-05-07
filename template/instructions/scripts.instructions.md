---
name: Lifecycle Engine
applyTo: "scripts/lifecycle/**,xanad-assistant.py"
description: "Conventions for the lifecycle engine — single-file constraint, event emission, CLI surface rules, and manifest/lockfile discipline"
---

# Lifecycle Engine Instructions

- The engine lives in a **single file**: `scripts/lifecycle/xanad_assistant.py`. Do not split it into modules.
- `xanad-assistant.py` at the repo root is a thin wrapper — keep it thin.
- All four modes (`setup`, `update`, `repair`, `factory-restore`) go through the same `build_execution_result → build_plan_result → execute_apply_plan` pipeline.
- **Never write** to `template/setup/install-manifest.json` or `template/setup/catalog.json` by hand — always regenerate via `python3 scripts/generate.py`.
- Emit structured lifecycle events (`event`, `type`, `payload`) on stdout; all prose goes to stderr.
- `--json` outputs a single JSON object on stdout; `--json-lines` streams NDJSON events; `--ui agent` is the Copilot-friendly mode.
- Exit codes are frozen — see `docs/contracts/exit-codes.md`. Do not add new exit codes without updating the contract.
- No third-party runtime dependencies — stdlib only.
- No silent error swallowing: raise or emit a structured `error` event.
- Lockfile reads and writes go through `parse_lockfile_state()` and `write_lockfile()` — never open `.github/xanad-assistant-lock.json` directly in new code paths.
- Schema validation happens at system boundaries (lockfile load, manifest load). Do not re-validate mid-pipeline.
