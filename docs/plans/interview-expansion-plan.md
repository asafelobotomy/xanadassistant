# Interview Expansion Plan

> Status: Base interview implementation complete; installed-agent follow-up customization now shipped for Commit, Docs, Explore, Planner, and Review. Tier 3-B and Tier 4 remain deferred.
> Sources: `copilot-instructions-template` interview.md + setup.agent.md + template;
> GitHub Copilot customization docs; progressive-disclosure UX research.

---

## Current State (after implementation)

xanadassistant now has a two-stage setup-question flow:

1. A base interview covering setup depth, profile, packs, ownership, personalisation, memory/MCP choices, and other core setup answers.
2. A plan-time follow-up stage that derives `batch: "agent"` questions only for locally installed configurable agents and replays those answers from lockfile `setupAnswers` on later inspect/update/repair flows.

Current shipped configurable agents:

| Agent | Answer keys | Agent tokens | Fallback token(s) |
| --- | --- | --- | --- |
| Commit | `agent.commit.messageStyle`, `agent.commit.secretGuardMode` | `{{agent:commit:message-style}}`, `{{agent:commit:secret-guard}}` | `{{pack:commit-style}}`, `{{pack:secret-guard}}` |
| Docs | `agent.docs.outputStyle` | `{{agent:docs:output-style}}` | `{{pack:output-style}}` |
| Explore | `agent.explore.outputStyle` | `{{agent:explore:output-style}}` | `{{pack:output-style}}` |
| Planner | `agent.planner.planFormat` | `{{agent:planner:plan-format}}` | `{{pack:plan-format}}` |
| Review | `agent.review.reportingThreshold` | `{{agent:review:reporting-threshold}}` | `{{pack:review-depth}}` |

Auto-detected tokens (no questions, scanner runs silently):

| Token | Scanner source |
| --- | --- |
| `{{WORKSPACE_NAME}}` | `workspace.name` (always set) |
| `{{PRIMARY_LANGUAGE}}` | `_workspace_scan.py` — pyproject.toml, Cargo.toml, go.mod, etc. |
| `{{PACKAGE_MANAGER}}` | `_workspace_scan.py` — yarn.lock, pnpm-lock.yaml, etc. |
| `{{TEST_COMMAND}}` | `_workspace_scan.py` — package.json scripts.test, go.mod, Cargo.toml, etc. |

---

## Key Research Findings

1. **CIT setup agent auto-detects workspace stack** — reads project files to infer language/runtime/test command before asking questions. Adopted via `_workspace_scan.py` (Tier 1-B).

2. **CIT installed template has 12+ additional tokens across 8 sections** — xanadassistant adopts a curated subset (Tiers 2–3); the rest are deferred or rejected (see Not Adopting table).

3. **GitHub guidance on instructions files** — files over ~1,000 lines show inconsistent behavior; keep the installed file concise. Language specifics belong in scoped `.instructions.md` stubs.

4. **Progressive disclosure UX** — 3–5 essential questions first; personalisation unlocked after core choices. Completion rates rise ~94% when steps are revealed progressively.

5. **`ui-agent-contract.md` is silent on question kinds** — no contract update needed when adding new `choice` questions.

---

## Implementation Summary

| Tier | Status | Description | New questions | New tokens |
| --- | --- | --- | --- | --- |
| 0 | ✅ done | Token pipeline bug fix (`preserve-marked-markdown-blocks` now renders tokens) | 0 | 0 |
| 1-A | ✅ done | `{{PROJECT_NAME}}` → `{{WORKSPACE_NAME}}` in template | 0 | 0 |
| 1-B | ✅ done | Workspace auto-detection scanner (`_workspace_scan.py`) | 0 | 3 (scanned) |
| 2-A | ✅ done | `response.style` → `{{RESPONSE_STYLE}}` | 1 | 1 |
| 2-B | ✅ done | `autonomy.level` → `{{AUTONOMY_LEVEL}}` | 1 | 1 |
| 2-C | ✅ done | `agent.persona` → `{{AGENT_PERSONA}}` | 1 | 1 |
| 3-A | ✅ done | `testing.philosophy` → `{{TESTING_PHILOSOPHY}}` | 1 | 1 |
| Agent rollout | ✅ done | Installed-agent follow-up registry, replay, and wrapper-token customization for Commit, Docs, Explore, Planner, and Review | 6 | 6 |
| 3-B | 🔧 deferred | `loc.thresholds` → `{{LOC_WARN}}` + `{{LOC_HARD}}` | 1 | 2 |
| 4 | 🔧 future | Additional CIT tokens — see Tier 4 table below | — | — |

### Tier 3-B notes (deferred)

Controls LOC guidance in the installed instructions. Open question: how to omit the LOC row
when `none` is selected (sentinel value vs conditional-omit mechanism not yet decided).

Token values: `strict` → 150/300, `standard` → 250/400, `relaxed` → 400/600, `none` → omit row.

---

## Tier 4 (future) — Additional CIT tokens

| Token | CIT section | Notes |
| --- | --- | --- |
| `{{THREE_CHECK_COMMAND}}` | §2 | Could default to `{{TEST_COMMAND}}` if detected |
| `{{TYPE_CHECK_COMMAND}}` | §2 | Auto-detect: `tsc --noEmit`, `mypy`, `cargo check` |
| `{{DEP_BUDGET}}` / `{{DEP_BUDGET_WARN}}` | §2 | Dependency count limits; project-specific |
| `{{INTEGRATION_TEST_ENV_VAR}}` | §2 | Env var name to gate integration tests |
| `{{SUBAGENT_MAX_DEPTH}}` | §3 | Subagent recursion limit; default 3 |
| `{{PREFERRED_SERIALISATION}}` | §4 | JSON / YAML / TOML; project-specific |
| `{{LOC_COMMAND}}` | §7 | LOC counting command; auto-detect from toolchain |
| `{{VALUE_STREAM_DESCRIPTION}}` | §1 | Lean principles; too abstract for setup wizard |

---

## Progressive Disclosure Structure (current)

**Batch 1 — Setup and core choices:**
`setup.depth`, then the base profile/pack/ownership/MCP questions appropriate to that depth.

**Batch 2 — Personalisation:**
`response.style`, `autonomy.level`, `agent.persona`, `testing.philosophy`, and related optional core preferences.

**Batch 3 — Agent follow-ups:**
Plan-time `batch: "agent"` questions emitted only for configurable agents that are actually installed locally after ownership resolution.

In `--non-interactive` mode, base questions use their declared defaults and omitted agent-specific answers fall back to their pack token values. The scanner always runs silently.

---

## What Is Not Being Adopted

| CIT question | Reason |
| --- | --- |
| S2 — Experience level | xanadassistant is a lifecycle tool, not a general tutor |
| S3 — Primary mode (speed/quality/learning) | Covered by `profile.selected` |
| S6 — Unified ownership mode | Already split into `ownership.agents` + `ownership.skills` |
| A6 — Code style (linter/style guide) | Too workspace-specific |
| A7 — Documentation level | Too broad |
| A8 — Error handling | Too broad |
| A9 — Security flagging aggressiveness | Too broad |
| A11 — Dependency philosophy | Context-specific |
| A12 — Instruction editing permission | Governed by managed-surface model |
| A13 — Refactoring stance | Context-specific |
| A14 — Reporting style | Deferred |
| A15 — Skill search | Not applicable to plugin model |
| A16 — Lifecycle hooks | Covered by `mcp.enabled` derivation |
| A17 — Prompt commands | Prompts are always a core surface |
| A18 — Plugin authoring conventions | Maintainer-only |
| CIT §1 Lean Principles (full) | Too prescriptive for generic template |
| CIT §6 Waste Catalogue | Deferred |
| CIT §8 Living Update Protocol | Replaced by managed-surface model |
| E16–E24 (misc.) | Out of scope or VS Code/model-level |

---

## Open Questions

| # | Question | Status |
| --- | --- | --- |
| 1 | `--non-interactive` + blank freetext tokens? | Resolved — auto-detection covers this; blanks leave placeholder text |
| 2 | Exact template placement for Tier 2 tokens? | Resolved — Operating Modes section; Tier 3-A in Coding Conventions |
| 3 | `ui-agent-contract.md` question kinds? | Resolved — not enumerated; no contract update needed |
| 4 | LOC `none` option — sentinel vs conditional-omit? | Open — decision needed before implementing Tier 3-B |
| 5 | Merge `ownership.agents` + `ownership.skills` into one question? | Open — deferred |

---

## Files Affected

| File | Tiers |
| --- | --- |
| `scripts/lifecycle/_xanad/_plan_utils.py` | 0 |
| `scripts/lifecycle/_xanad/_workspace_scan.py` (new) | 1-B |
| `scripts/lifecycle/_xanad/_conditions.py` | 0, 1-B, 2, 3-A |
| `scripts/lifecycle/_xanad/_interview.py` | 2, 3-A, agent rollout |
| `scripts/lifecycle/_xanad/_agent_customization.py` | agent rollout |
| `template/copilot-instructions.md` | 1-A, 1-B, 2, 3-A |
| `template/setup/install-policy.json` | 1-B, 2, 3-A, agent rollout |
| `template/setup/agent-registry.json` | agent rollout |
| `template/setup/install-manifest.json` (generated) | after each tier |
| `template/setup/catalog.json` (generated) | after each tier |
| `tests/lifecycle/test_plan_conditions.py` | agent rollout |
| `tests/lifecycle/test_plan_migration.py` | agent rollout |
| `tests/lifecycle/test_plan_orchestration.py` | agent rollout |
| `tests/lifecycle/test_progress_and_defaults.py` | agent rollout |
