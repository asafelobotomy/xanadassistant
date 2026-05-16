# Agent Routing

This file is the canonical routing map for the xanadassistant repository.
Use it to decide which specialist agent should own a task before widening scope.

## Roster

| Agent | User-invocable | Use when |
|---|---|---|
| `Cleaner` | yes | Pruning stale artefacts, caches, archives, and dead files; tightening repository hygiene without changing behaviour |
| `Commit` | yes | Git status, staging, commit messages, commits, pushes, pulls, rebases, branches, tags, releases, and PR work |
| `Deps` | yes | Scanning workspace dependencies, auditing installed packages, checking for vulnerabilities, suggesting updates or alternatives, and installing/updating/repairing/removing packages |
| `Explore` | yes | Broad read-only codebase exploration, file discovery, symbol discovery, and architecture lookup |
| `Review` | yes | Code review, architecture review, security review, maintainability review, and regression-risk review |
| `xanadLifecycle` | yes | `inspect`, `check`, `plan`, `apply`, `update`, `repair`, and `factory-restore` for xanadAssistant-managed surfaces |
| `Triage` | no | First-pass complexity classification — determines whether a task needs a direct answer, targeted edit, single agent, or multi-agent plan |
| `Debugger` | no | Root-cause diagnosis, failing tests, regression triage, broken commands, unclear behavior reproduction, and minimal fix-path isolation |
| `Organise` | no | Subagent-only structural worker — moving files, regrouping folders, fixing caller paths after a file move |
| `Planner` | no | Complex multi-step planning, phased rollout, migration planning, and scoped execution plans before implementation |
| `Researcher` | no | External documentation, upstream behavior, GitHub-source research, and source-backed comparisons before implementation |
| `Docs` | yes | Documentation updates, migration notes, contract explanations, walkthroughs, and user-facing technical guides |

## Routing Table

| Work type | Required agent |
|---|---|
| Pruning stale artefacts, caches, archives, dead files, or tightening repository hygiene | `Cleaner` |
| Git status, staging, commit messages, commits, preflight before push, push, pull, rebase, branch, stash, tag, release notes, PR title/body, or PR creation | `Commit` |
| Scanning workspace dependencies, auditing packages, checking for CVEs or outdated versions, suggesting updates or alternatives, or installing/updating/removing packages | `Deps` |
| Broad read-only codebase exploration, architecture lookup, file discovery, symbol discovery, or "find where this lives" | `Explore` |
| Root-cause diagnosis, failing tests, regression triage, broken commands, or unclear behavior reproduction | `Debugger` |
| Complex multi-step planning, phased rollout, migration planning, or a scoped execution plan before coding | `Planner` |
| External documentation, upstream behavior, GitHub-source research, or source-backed comparisons before coding or review | `Researcher` |
| Documentation updates, migration notes, contract explanations, walkthroughs, or README/user-facing technical guides | `Docs` |
| Code review, architecture review, security review, maintainability review, regression-risk review, or review of a PR/diff | `Review` |
| xanadAssistant inspect, check, plan, apply, update, repair, or factory-restore | `xanadLifecycle` |

## Handoff Rules

- `xanadLifecycle` may delegate to `Explore` for repo inventory, `Debugger` for failing lifecycle behavior, and `Planner` for phased remediation.
- `Cleaner` may delegate to `Review` for security-sensitive or policy-owned files, `Organise` when cleanup turns into file moves or reshaping, `Docs` when cleanup changes maintenance guidance or user-facing references, and `Commit` when the approved scope is ready to stage.
- `Review` may delegate to `Explore` for inventory, `Debugger` for concrete reproduction, `Planner` for remediation planning, and `Researcher` for current external constraints.
- `Debugger` stays read-only and returns diagnosis, evidence, and the minimal next fix step. It may delegate to `Explore` when the failure spans unfamiliar files and a read-only inventory is needed first, and to `Review` when the likely cause involves a contract boundary, security posture, or architecture assumption.
- `Planner` stays read-only and returns an executable plan with file list, risks, and verification.
- `Researcher` stays read-only and returns source-backed findings, constraints, and recommended next steps.
- `Organise` stays structural-only — no semantic implementation unless explicitly widened by the caller.
- `Deps` may delegate to `Researcher` for replacement-candidate research, `Explore` for local import/usage inventory, and `Review` for security findings that require deeper analysis.
- `Commit` may delegate to `Explore` for scope lookup before staging, `Review` for pre-commit diff review, and `Debugger` for unexpected git failures.
- `Docs` may delegate to `Researcher` for external references, `Explore` for local accuracy checks, `Review` for doc quality, and `Planner` when the documentation scope is broad.
- Do not introduce a separate routing manifest. Agent frontmatter plus this file is the routing authority.

## Recommended Handoff Patterns

Use these patterns when a task crosses specialist boundaries but should still stay narrow and deliberate.

| Start | Hand off to | Use when |
|---|---|---|
| `Cleaner` | `Review` | Cleanup touches security-sensitive files, managed surfaces, or policy-owned content |
| `Cleaner` | `Organise` | Cleanup turns into file moves, path repair, or repository reshaping |
| `Cleaner` | `Docs` | Cleanup changes archive conventions, maintenance guidance, or user-facing references |
| `Review` | `Debugger` | A finding depends on reproducing a failure or isolating a concrete regression before the review is credible |
| `Review` | `Planner` | Findings imply a phased remediation path rather than a single local fix |
| `Review` | `Researcher` | The review depends on current upstream docs, release behavior, or external contract constraints |
| `Debugger` | `Explore` | The failure spans unfamiliar files and a read-only inventory is needed before root-cause isolation |
| `Debugger` | `Review` | The likely cause involves a contract boundary, security posture, or architecture assumption requiring structured review |
| `Debugger` | `Planner` | Root cause is known, but the fix spans multiple files or needs staged verification |
| `Debugger` | `Researcher` | The failure appears to depend on current upstream behavior or source-specific constraints |
| `Planner` | `Researcher` | The plan depends on external docs, MCP behavior, GitHub-source semantics, or version-specific rules |
| `Planner` | `Docs` | The plan should be preserved as migration guidance, operational notes, or a maintained project document |
| `Researcher` | `Docs` | Source-backed findings should become maintained repo documentation instead of remaining a one-off summary |
| `Docs` | `Researcher` | Documentation accuracy depends on current external references or upstream behavior |
| `Docs` | `Review` | The document needs a final correctness and coverage pass before it is considered complete |
| `Commit` | `Explore` | Scope of staged changes is unclear before committing |
| `Commit` | `Review` | User requests a diff review before the commit is made |
| `Commit` | `Debugger` | A git command fails unexpectedly and the cause is unclear |
| `xanadLifecycle` | `Debugger` | `inspect`, `check`, `plan`, `apply`, `update`, or `repair` results are surprising or failing and the control path is unclear |
| `xanadLifecycle` | `Planner` | Repair, update, migration, or factory-restore work needs phased remediation before execution |

## Lifecycle Trigger Phrases

| Trigger phrase | Route |
|---|---|
| `inspect workspace` | `xanadLifecycle` |
| `run lifecycle check` | `xanadLifecycle` |
| `repair install` | `xanadLifecycle` |
| `update xanadAssistant` | `xanadLifecycle` |
| `factory restore` | `xanadLifecycle` |

Natural-language requests to add a convention or preference to instructions, such as `Remember this for next time` or `Add this to your instructions`, are not lifecycle operations.

## Follow-up Adoption Work

The ranked review of additional template-repo agents that are still not adopted lives in `docs/template-review-adopt.md`.