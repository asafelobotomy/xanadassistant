# Template Review Adoption Notes

This file is the concise decision ledger for useful ideas reviewed from
`copilot-instructions-template`.

Keep it short. Canonical implementations and full behavior live in the actual
skill, workflow, instruction, and contract files.

## Adopted

| ID | Decision | Canonical references | Notes |
|---|---|---|---|
| A1 | Attention-budget gate adopted | `scripts/check_attention_budget.py`, `.github/workflows/ci.yml` | Enforced as a repo-local budget check rather than a one-off shell snippet. |
| A6 | Durable memory routing adopted | `docs/memory.md`, `.github/copilot-instructions.md`, `template/copilot-instructions.md` | Durable repo facts promote into `docs/memory.md`; `/memories/repo/` remains the in-flight inbox. |
| A8 | `commit-preflight` adopted as repo-local maintainer skill | `.github/skills/commit-preflight/SKILL.md` | Adapted for repo-specific commands and generated-artifact checks; not consumer-delivered. |
| A9 | `tech-debt-audit` adopted as repo-local maintainer skill | `.github/skills/tech-debt-audit/SKILL.md` | Narrowed to repo-native signals such as LOC, regression, freshness, and debt markers. |

## Deferred

| ID | Decision | Revisit when |
|---|---|---|
| A2 | Defer section numbering in `template/copilot-instructions.md` | Consumer instructions need stable section-level cross-references. |
| A3 | Defer a dedicated self-update protocol section | Consumer instructions need direct self-edit guidance beyond the existing lifecycle routing. |
| A4 | Defer explicit progressive-disclosure rules in more skills | Additional consumer-facing skills are added and need a shared structure contract. |
| A5 | Defer a `SessionStart` hook for lifecycle state | Session-start install-state context becomes frequent enough to justify hook complexity. |

## Remaining Agent Ranking

`Debugger`, `Planner`, `Researcher`, and `Docs` are already adopted. The highest-value remaining template-agent candidates are:

| Rank | Agent | Recommendation | Why |
|---|---|---|---|
| 1 | `Audit` | Conditional next | Strongest remaining specialist if broader repo-health or security review becomes a recurring workflow. |
| 2 | `Fast` | Defer | Useful for tiny tasks, but lower leverage than the default coding flow in this repo. |
| 3 | `Cleaner` | Defer | Hygiene matters, but cleanup is not frequent enough yet to justify a dedicated agent. |
| 4 | `Organise` | Defer | Structural reorg work is still rare and can stay in the default coding path. |
| 5 | `Extensions` | Avoid for now | Too tied to extension/profile workflows that are peripheral to xanadassistant. |
| 6 | `Code` | Reject as duplicate | Duplicates the default coding agent without adding distinct value. |
| 7 | `Setup` | Reject for this architecture | Assumes plugin-style delivery rather than xanadassistant's CLI- and manifest-driven model. |

Current recommendation: adopt `Audit` only if the existing `lifecycle-audit` skill needs to expand into a broader repository health review surface.

## Standing Rule

Do not copy template features verbatim when repo-local constraints differ.

Prefer adaptation when a feature depends on:

- repo-specific commands or generated artifacts
- maintainer-only workflows that must not ship to consumers
- assumptions about plugin delivery that do not match xanadassistant

## Non-goals

| Feature | Reason |
|---|---|
| Pulse / heartbeat session tracking | Too heavy for current single-repo needs. |
| `routing-manifest.json` | Agent frontmatter plus `AGENTS.md` already define routing. |
| Multi-plugin-format manifests | Not needed for the current CLI- and manifest-driven architecture. |
| Separate `SOUL.md` / `USER.md` durable memory files | One git-tracked `docs/memory.md` is sufficient for now. |
| Starter kits | Only relevant if xanadassistant later ships broader stack-specific content. |
