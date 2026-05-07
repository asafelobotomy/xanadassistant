# Xanad Assistant — Developer Instructions

> Role: Developer on this repo — lifecycle engine, schema contracts, test suite, and Copilot surface files.
>
> **Every session:** test narrowly during intermediate phases; run the full suite at task completion. The manifest is generated — never hand-edit it. Read a file before modifying it.

## My Role

I work **on** xanadassistant — building and maintaining the lifecycle engine, schemas, and Copilot surface files (agents, skills, hooks, prompts, instructions). The agents, skills, hooks, and prompts in this repo are delivered verbatim to consumer workspaces. There is no developer-only vs consumer-only split for those surfaces — they are the same files. The instructions file uses token substitution: `template/copilot-instructions.md` carries `{{}}` tokens resolved at consumer install time; this file has them resolved to xanadassistant's own values.

## Architecture

| Path | Role |
|------|------|
| `xanad-assistant.py` | Root entry point (thin wrapper) |
| `scripts/lifecycle/xanad_assistant.py` | Single-file lifecycle engine (~2800 lines) |
| `template/setup/install-policy.json` | Source of truth for what gets installed |
| `template/setup/install-manifest.json` | **Generated** — never edit by hand; run `python3 scripts/generate.py` |
| `template/setup/catalog.json` | **Generated** — never edit by hand |
| `template/copilot-instructions.md` | Consumer instructions template (`{{}}` tokens) |
| `agents/` | Agents → consumer's `.github/agents/` |
| `skills/` | Skills → consumer's `.github/skills/` |
| `hooks/scripts/` | Hook scripts → consumer's `.github/hooks/scripts/` |
| `template/prompts/` | Prompts → consumer's `.github/prompts/` |
| `docs/contracts/` | Frozen contracts: CLI surface, lifecycle protocol, exit codes, schemas |
| `tests/` | 124 tests; 4 network-gated (require `XANAD_NETWORK_TESTS=1`) |

## Key Commands

| Task | Command |
|------|---------|
| Run tests | `python3 -m unittest discover -s tests -p 'test_*.py'` |
| Regenerate manifest + catalog | `python3 scripts/generate.py` |
| Freshness check | `python3 -m scripts.lifecycle.check_manifest_freshness --package-root . --policy template/setup/install-policy.json --manifest template/setup/install-manifest.json --catalog template/setup/catalog.json` |
| Inspect (this workspace) | `python3 xanad-assistant.py inspect --workspace . --package-root . --json` |
| Check (this workspace) | `python3 xanad-assistant.py check --workspace . --package-root . --json` |
| Plan setup | `python3 xanad-assistant.py plan setup --workspace <path> --package-root . --json --non-interactive` |

## Coding Conventions

- Language: **Python 3** · stdlib only · no third-party runtime deps
- Engine: single file `scripts/lifecycle/xanad_assistant.py`
- Hook scripts: `set -euo pipefail`; JSON in on stdin → JSON on stdout
- Tests: `unittest`; fixtures inline in test methods; no external test data files
- No silent error swallowing — raise or emit structured error events
- Read before modifying — never edit a file not opened this session

## PDCA + Test Scope

Plan → Do → Check → Act on every non-trivial change.

| Tier | Use when |
|------|---------|
| `PathTargeted` | Default — run the specific test module for changed code |
| `AffectedSuite` | Shared helpers, schema changes, contract surfaces |
| `FullSuite` | Task completion, multi-module changes, before push |

Targeted example: `python3 -m unittest tests.test_xanad_assistant_inspect`

## Critical Rules

- `template/setup/install-manifest.json` is generated — never edit by hand
- `template/copilot-instructions.md` must contain `{{}}` tokens — do not resolve them in the template
- This file must contain **zero** `{{}}` tokens
- `agents/`, `skills/`, `hooks/scripts/`, `template/prompts/` are consumer-facing — changes here are delivered to consumers
- Contracts in `docs/contracts/` are frozen — require explicit discussion to change

## Operating Modes

**Implement** (default): plan → implement → test.
**Review**: read-only; state findings before proposing fixes.
**Refactor**: no behaviour changes; tests pass before and after.
**Planning**: produce task breakdown before writing code.

## Skills and Agents

- `lifecycle-audit` skill — use before any lifecycle operation on this workspace
- `lifecycle-planning` agent — delegate all `inspect`, `check`, `plan`, `apply`, `update`, `repair`, `factory-restore` requests
- Trigger phrases: `"inspect workspace"`, `"run lifecycle check"`, `"repair install"`, `"update xanad-assistant"`, `"factory restore"`