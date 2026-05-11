# xanadAssistant — Developer Instructions

> Role: Developer on this repo — lifecycle engine, schema contracts, test suite, and Copilot surface files.
>
> **Every session:** test narrowly during intermediate phases; run the full suite at task completion. The manifest is generated — never hand-edit it. Read a file before modifying it.

## My Role

I work **on** xanadAssistant — building and maintaining the lifecycle engine, schemas, and Copilot surface files (agents, skills, hooks, prompts, instructions). The agents, skills, hooks, and prompts in this repo are delivered verbatim to consumer workspaces. There is no developer-only vs consumer-only split for those surfaces — they are the same files. The instructions file uses token substitution: `template/copilot-instructions.md` carries `{{}}` tokens resolved at consumer install time; this file has them resolved to xanadAssistant's own values.

## Architecture

| Path | Role |
|------|------|
| `xanadAssistant.py` | Root entry point (thin wrapper) |
| `scripts/lifecycle/xanadAssistant.py` | Thin dispatcher; re-exports all public symbols |
| `scripts/lifecycle/_xanad/` | Lifecycle engine package (small focused submodules, each ≤250 lines) |
| `template/setup/install-policy.json` | Source of truth for what gets installed |
| `template/setup/install-manifest.json` | **Generated** — never edit by hand; run `python3 scripts/generate.py` |
| `template/setup/catalog.json` | **Generated** — never edit by hand |
| `template/copilot-instructions.md` | Consumer instructions template (`{{}}` tokens) |
| `agents/` | Agents → consumer's `.github/agents/` |
| `skills/` | Skills → consumer's `.github/skills/` |
| `hooks/scripts/` | Hook scripts → consumer's `.github/hooks/scripts/` |
| `template/prompts/` | Prompts → consumer's `.github/prompts/` |
| `docs/contracts/` | Frozen contracts: CLI surface, lifecycle protocol, exit codes, schemas |
| `tests/` | Unittest suite; network-gated coverage requires `XANAD_NETWORK_TESTS=1` |

## Key Commands

| Task | Command |
|------|---------|
| Run tests | `python3 -m unittest discover -s tests -p 'test_*.py'` |
| LOC gate | `python3 scripts/check_loc.py` |
| Regenerate manifest + catalog | `python3 scripts/generate.py` |
| Freshness check | `python3 -m scripts.lifecycle.check_manifest_freshness --package-root . --policy template/setup/install-policy.json --manifest template/setup/install-manifest.json --catalog template/setup/catalog.json` |
| Inspect (this workspace) | `python3 xanadAssistant.py inspect --workspace . --package-root . --json` |
| Check (this workspace) | `python3 xanadAssistant.py check --workspace . --package-root . --json` |
| Plan setup | `python3 xanadAssistant.py plan setup --workspace <path> --package-root . --json --non-interactive` |

## Coding Conventions

- Language: **Python 3** · stdlib only · no third-party runtime deps
- Engine: single file `scripts/lifecycle/xanadAssistant.py`
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

Targeted example: `python3 -m unittest tests.lifecycle.test_inspect_check`

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

## Memory

Use memory as optional recall, not as lifecycle authority.

- Put current task notes and temporary reminders in `/memories/session/`.
- Put personal cross-repo preferences in `/memories/`.
- Put in-flight repo facts in `/memories/repo/` first.
- Promote only validated, durable repo facts into `docs/memory.md`.
- Keep durable memory short and source-backed; contracts, tests, and canonical code win if memory drifts.

## Skills and Agents

- `lifecycle-audit` skill — use before any lifecycle operation on this workspace
- `commit-preflight` skill — repo-local git preflight for this workspace
- `tech-debt-audit` skill — repo-local maintainability audit for this workspace
- `Debugger` agent — diagnose failures and isolate root causes before implementation
- `Planner` agent — produce scoped execution plans for multi-step work before implementation
- `Researcher` agent — gather source-backed external constraints before implementation or review
- `Docs` agent — write and update documentation, migration guides, and technical walkthroughs
- `xanad-lifecycle` agent — delegate all `inspect`, `check`, `plan`, `apply`, `update`, `repair`, `factory-restore` requests
- `AGENTS.md` — canonical repo-local routing table for agent selection, handoffs, and lifecycle trigger phrases
- Trigger phrases: `"inspect workspace"`, `"run lifecycle check"`, `"repair install"`, `"update xanadAssistant"`, `"factory restore"`
- If `inspect` or `check` reports `package_name_mismatch` or `successor_cleanup_required`, treat the workspace as a predecessor `copilot-instructions-template` migration and route it through `repair` or `update` rather than ad hoc cleanup.

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
| xanadAssistant inspect, check, plan, apply, update, repair, or factory-restore | `xanad-lifecycle` |