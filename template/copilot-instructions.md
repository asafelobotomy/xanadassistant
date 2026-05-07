# {{PROJECT_NAME}} — Copilot Instructions

> This project uses **xanad-assistant** to manage its Copilot surface files (agents, skills, hooks, prompts).
> Lifecycle authority: `xanad-assistant.py` — use the `lifecycle-planning` agent for all xanad-assistant operations.

## My Role

I work **in** {{PROJECT_NAME}} — implementing features, reviewing code, running tests, and maintaining the project's Copilot surface via xanad-assistant. Changes to agents, skills, hooks, and prompts go through `xanad-assistant.py update` rather than direct file edits to `.github/`.

## Key Commands

| Task | Command |
|------|---------|
| Run tests | `{{TEST_COMMAND}}` |
| Inspect Copilot install state | `python3 <xanad-root>/xanad-assistant.py inspect --workspace . --package-root <xanad-root> --json` |
| Check for repair needs | `python3 <xanad-root>/xanad-assistant.py check --workspace . --package-root <xanad-root> --json` |

## Lifecycle Operations

Use the **lifecycle-planning** agent for all xanad-assistant operations. Trigger phrases:

| Trigger phrase | Operation |
|---|---|
| `"set up xanad-assistant"` | First-time install |
| `"update xanad-assistant"` | Pull latest agents, skills, hooks, prompts |
| `"run lifecycle check"` | Inspect + check; surface repair reasons |
| `"repair install"` | Fix stale or broken managed files |
| `"factory restore"` | Reset to clean managed state |

Do not edit files under `.github/agents/`, `.github/skills/`, `.github/hooks/`, or `.github/prompts/` directly — these are managed by xanad-assistant. Use the `lifecycle-audit` skill to review state before proposing any lifecycle operation.

## Coding Conventions

- Language: **{{PRIMARY_LANGUAGE}}** · Package manager: **{{PACKAGE_MANAGER}}**
- Read before modifying — never edit a file not opened this session
- No silent error swallowing

## PDCA + Test Scope

Plan → Do → Check → Act on every non-trivial change.

- Default: run the narrowest test suite covering changed paths
- Broaden to the full suite at task completion and before merging

## Operating Modes

**Implement** (default): plan → implement → test.
**Review**: read-only; state findings before proposing fixes.
**Refactor**: no behaviour changes; tests pass before and after.

## Skills and Agents

- `lifecycle-audit` skill — loaded on demand; run before any lifecycle operation
- `lifecycle-planning` agent — handles all `inspect`, `check`, `plan`, `apply`, `update`, `repair`, `factory-restore` requests