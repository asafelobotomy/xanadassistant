# {{WORKSPACE_NAME}} — Copilot Instructions

> This project uses **xanadAssistant** to manage its Copilot surface files (agents, skills, hooks, prompts).
> Lifecycle authority: `xanadAssistant.py` — use the `xanadLifecycle` agent for all xanadAssistant operations.

## My Role

I work **in** {{WORKSPACE_NAME}} — implementing features, reviewing code, running tests, and maintaining the project's Copilot surface via xanadAssistant. Changes to agents, skills, mcp, and prompts go through `xanadAssistant.py update` rather than direct file edits to `.github/`.

## Key Commands

| Task | Command |
| ------ | --------- |
| Run tests | `{{TEST_COMMAND}}` |
| Drift preflight | `python3 scripts/drift_preflight.py` |
| LOC gate | `python3 scripts/check_loc.py` |
| Inspect Copilot install state | `python3 <xanad-root>/xanadAssistant.py inspect --workspace . --package-root <xanad-root> --json` |
| Check for repair needs | `python3 <xanad-root>/xanadAssistant.py health-check --workspace . --package-root <xanad-root> --json` |

## Lifecycle Operations

Use the **xanadLifecycle** agent for all xanadAssistant operations. Trigger phrases:

| Trigger phrase | Operation |
| --- | --- |
| `"set up xanadAssistant"` | First-time install |
| `"inspect workspace"` | Inspect current install state |
| `"update xanadAssistant"` | Pull latest agents, skills, hooks, prompts |
| `"run lifecycle check"` | Inspect + check; surface repair reasons |
| `"repair install"` | Fix stale or broken managed files |
| `"factory restore"` | Reset to clean managed state |
| `"health check"` | Run xanadAssistant install-state health check |
| `"run health check"` | Run xanadAssistant install-state health check |

Available prompts: `/setup` (install or refresh), `/bootstrap` (cold-start from bare workspace), `/update` (pull latest package files).

Do not edit files under `.github/agents/`, `.github/skills/`, `.github/mcp/`, or `.github/prompts/` directly — these are managed by xanadAssistant. Use the `lifecycleAudit` skill to review state before proposing any lifecycle operation.

**Conditional behaviors:**
- **If `xanadTools` MCP is available** and can resolve a local xanadAssistant package root or a supported remote source, setup-oriented lifecycle operations may use its `lifecycle_inspect`, `lifecycle_check`, `lifecycle_interview`, `lifecycle_plan_setup`, `lifecycle_setup`, `lifecycle_update`, `lifecycle_repair`, and `lifecycle_factory_restore` tools instead of shelling out directly. If `xanadTools` MCP is unavailable, fall back to `xanadAssistant.py` directly.
- **If `inspect` or `health-check` reports `package_name_mismatch` or `successor_cleanup_required`**, the workspace is being migrated from `copilot-instructions-template`; use `repair` or `update` so xanadAssistant can archive predecessor-owned files and install the current bundle atomically.

## Agent Routing

Route specialist work to the matching agent before acting directly. If a task involves work that maps to a specialist agent's domain, delegate that work to the specialist agent first and continue from the returned result. If a delegated agent cannot complete its task, handle the failure inline or surface it to the user before continuing.

See [AGENTS.md](../AGENTS.md) for the full routing table, roster, handoff rules, and trigger phrases. That file is loaded automatically as an instruction source, so routing guidance is always in context.

## Coding Conventions

- Language: **{{PRIMARY_LANGUAGE}}** · Package manager: **{{PACKAGE_MANAGER}}**
- **Testing**: {{TESTING_PHILOSOPHY}}
- Read before modifying — never edit a file whose current content you have not read in this task
- No silent error swallowing

## PDCA + Test Scope

Plan → Do → Check → Act on every non-trivial change.

- Before commit, merge, or push in this repository, run `python3 scripts/drift_preflight.py`.
- Default: run the single test module or test class that directly covers the changed code (see `tests.instructions.md` for the full test-scope policy)
- Broaden to the full suite at task completion and before merging

## Operating Modes

**Implement** (default): plan → implement → test.
**Review**: read-only; state findings before proposing fixes.
**Refactor**: no behaviour changes; tests pass before and after.
**Response style**: {{RESPONSE_STYLE}} · **Ambiguity**: {{AUTONOMY_LEVEL}} · **Tone**: {{AGENT_PERSONA}}

## Memory

Memory provides workspace-specific rules and cached facts; use it when available, not as lifecycle authority.

### Memory MCP server

When hooks are enabled, a `memory` MCP server is available. Each specialist agent's instruction file defines when and how to use it. The pattern used by every agent is:

1. Call `memory_dump(agent="<agent-name>")` at the start of each task to load rules and cached facts.
2. Follow all returned **rules** unconditionally for the rest of the task.
3. For any **fact** you intend to act on, call `elapsed(start=fact.updated_at)` to verify its age.
4. When you discover something specific to this workspace's commands, tool versions, paths, or established conventions, call `memory_set(agent="<agent-name>", key=..., value=...)` before finishing.
5. If the `memory` server is unavailable, emit one visible note ("⚠️ Memory MCP unavailable: [reason]") then continue without it.

## Skills and Agents

See `## Agent Routing` for the authoritative routing table; this section is a quick-reference index.

### Skills

- `lifecycleAudit` — loaded on demand; run before any lifecycle operation
- `agenticReview` — loaded on demand; evaluate or improve Copilot surface files
- `ciPreflight` — loaded on demand; run CI-equivalent checks before push

### Agents

- `Cleaner` — prune stale artefacts, caches, archives, and dead files
- `Commit` — git operations, commit messages, staging, push, pull, PR work
- `Debugger` — diagnose failures and isolate root causes before implementation
- `Deps` — scan dependencies, audit packages, check for vulnerabilities, install/update/repair/remove
- `Docs` — write and update documentation, migration guides, and technical walkthroughs
- `Explore` — broad read-only codebase exploration and architecture lookup
- `Organise` — move files, regroup folders, fix broken paths (subagent-only)
- `Planner` — produce scoped execution plans for multi-step work before implementation
- `Researcher` — gather source-backed external constraints before implementation or review
- `Review` — code, architecture, security, correctness, and regression-risk review; handles codebase audits
- `Triage` — first-pass complexity assessment; classify and route before acting (subagent-only)
- `xanadLifecycle` — handles all `setup`, `inspect`, `interview`, `health-check`, `health-report`, `plan`, `update`, `repair`, `factory-restore`, and **health check** requests
