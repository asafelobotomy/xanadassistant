# {{WORKSPACE_NAME}} — Copilot Instructions

> This project uses **xanad-assistant** to manage its Copilot surface files (agents, skills, hooks, prompts).
> Lifecycle authority: `xanad-assistant.py` — use the `xanad-lifecycle` agent for all xanad-assistant operations.

## My Role

I work **in** {{WORKSPACE_NAME}} — implementing features, reviewing code, running tests, and maintaining the project's Copilot surface via xanad-assistant. Changes to agents, skills, hooks, and prompts go through `xanad-assistant.py update` rather than direct file edits to `.github/`.

## Key Commands

| Task | Command |
|------|---------|
| Run tests | `{{TEST_COMMAND}}` |
| Inspect Copilot install state | `python3 <xanad-root>/xanad-assistant.py inspect --workspace . --package-root <xanad-root> --json` |
| Check for repair needs | `python3 <xanad-root>/xanad-assistant.py check --workspace . --package-root <xanad-root> --json` |

## Lifecycle Operations

Use the **xanad-lifecycle** agent for all xanad-assistant operations. Trigger phrases:

| Trigger phrase | Operation |
|---|---|
| `"set up xanad-assistant"` | First-time install |
| `"update xanad-assistant"` | Pull latest agents, skills, hooks, prompts |
| `"run lifecycle check"` | Inspect + check; surface repair reasons |
| `"repair install"` | Fix stale or broken managed files |
| `"factory restore"` | Reset to clean managed state |

Do not edit files under `.github/agents/`, `.github/skills/`, `.github/hooks/`, or `.github/prompts/` directly — these are managed by xanad-assistant. Review state with the workspace-local `xanadTools` lifecycle tools (`lifecycle_inspect`, `lifecycle_check`) before proposing any lifecycle operation.
When the workspace-local `xanadTools` MCP server is available and can resolve a
local xanad-assistant package root or a supported remote source, setup-oriented
lifecycle operations may use its `lifecycle.*` tools instead of shelling out directly.
This repository's lockfile should include a GitHub `source` plus `ref` fallback so lifecycle tools still work when a sibling xanad-assistant checkout is unavailable.
If `inspect` or `check` reports `package_name_mismatch` or `successor_cleanup_required`,
the workspace still has predecessor-managed Copilot surfaces; use `repair`
or `update` so xanad-assistant can archive predecessor-owned files and install the
current bundle atomically.

## Agent Routing

Route specialist work to the matching agent before acting directly. If a task has multiple phases, delegate the specialist phase first and continue from the returned result.

| Work type | Required agent |
|---|---|
| Git status, staging, commit messages, commits, preflight before push, push, pull, rebase, branch, stash, tag, release notes, PR title/body, or PR creation | `Commit` |
| Broad read-only codebase exploration, architecture lookup, file discovery, symbol discovery, or “find where this lives” | `Explore` |
| Root-cause diagnosis, failing tests, regression triage, broken commands, or unclear behavior reproduction | `Debugger` |
| Complex multi-step planning, phased rollout, migration planning, or a scoped execution plan before coding | `Planner` |
| External documentation, upstream behavior, GitHub-source research, or source-backed comparisons before coding or review | `Researcher` |
| Documentation updates, migration notes, contract explanations, walkthroughs, or README/user-facing technical guides | `Docs` |
| Code review, architecture review, security review, maintainability review, regression-risk review, or review of a PR/diff | `Review` |
| xanad-assistant inspect, check, plan, apply, update, repair, or factory-restore | `xanad-lifecycle` |

## Coding Conventions

- Language: **{{PRIMARY_LANGUAGE}}** · Package manager: **{{PACKAGE_MANAGER}}**
- **Testing**: {{TESTING_PHILOSOPHY}}
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
**Response style**: {{RESPONSE_STYLE}} · **Ambiguity**: {{AUTONOMY_LEVEL}} · **Tone**: {{AGENT_PERSONA}}

## Memory

Use memory as optional recall, not as lifecycle authority.

- Put current task notes and temporary reminders in `/memories/session/`.
- Put personal cross-repo preferences in `/memories/`.
- Put in-flight repo facts in `/memories/repo/` first.
- Promote only validated, durable repo facts into `docs/memory.md`.
- Keep durable memory short and source-backed; contracts, tests, and canonical code win if memory drifts.

## Skills and Agents

- `Debugger` agent — diagnose failures and isolate root causes before implementation
- `Planner` agent — produce scoped execution plans for multi-step work before implementation
- `Researcher` agent — gather source-backed external constraints before implementation or review
- `Docs` agent — write and update documentation, migration guides, and technical walkthroughs
- `xanad-lifecycle` agent — handles all `inspect`, `check`, `plan`, `apply`, `update`, `repair`, `factory-restore` requests