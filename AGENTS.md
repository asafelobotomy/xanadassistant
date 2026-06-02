# Agent Routing

This file is the canonical routing map for the xanadassistant repository.
Use it to decide which specialist agent should own a task before widening scope.

## Roster

| Agent | User-invocable | Use when |
| --- | --- | --- |
| `cleaner` | yes | Pruning stale artefacts, caches, archives, and dead files; tightening repository hygiene without changing behaviour |
| `commit` | yes | Git status, staging, commit messages, commits, pushes, pulls, rebases, branches, tags, releases, and PR work |
| `deps` | yes | Scanning workspace dependencies, auditing installed packages, checking for vulnerabilities, suggesting updates or alternatives, and installing/updating/repairing/removing packages |
| `explore` | yes | Broad read-only codebase exploration, file discovery, symbol discovery, architecture lookup, dependency tracing, example search, and repository structure questions |
| `review` | yes | Code review, PR review, diff review, architecture review, security review, maintainability review, correctness review, regression-risk review, and test coverage review |
| `xanadLifecycle` | yes | `setup`, `inspect`, `interview`, `health-check`, `health-report`, `plan`, `update`, `repair`, `factory-restore`, and health-check workflows for xanadAssistant-managed surfaces |
| `triage` | no | First-pass complexity classification — determines whether a task needs a direct answer, targeted edit, single agent, or multi-agent plan |
| `debugger` | no | Root-cause diagnosis, failing tests, regression triage, broken commands, unclear behavior reproduction, and minimal fix-path isolation |
| `organise` | no | Subagent-only structural worker — moving files, regrouping folders, fixing caller paths after a file move |
| `planner` | no | Complex multi-step planning, phased rollout, migration planning, and scoped execution plans before implementation |
| `researcher` | no | External documentation, upstream behavior, GitHub-source research, and source-backed comparisons before implementation |
| `docs` | yes | Creating or updating documentation files, README files for components or packs, walkthroughs, migration notes, contract explanations, user-facing technical guides, and running documentation tools (markdownlint, spellcheck, link validation) |

## Routing Table

| Work type | Required agent |
| --- | --- |
| Pruning stale artefacts, caches, archives, dead files, or tightening repository hygiene | `cleaner` |
| Git status, staging, commit messages, commits, preflight before push, push, pull, rebase, branch, stash, tag, release notes, PR title/body, or PR creation | `commit` |
| Scanning workspace dependencies, auditing packages, checking for CVEs or outdated versions, suggesting updates or alternatives, or installing/updating/repairing/removing packages | `deps` |
| Broad read-only codebase exploration, architecture lookup, file discovery, symbol discovery, or "find where this lives" | `explore` |
| Root-cause diagnosis, failing tests, regression triage, broken commands, or unclear behavior reproduction | `debugger` |
| Complex multi-step planning, phased rollout, migration planning, or a scoped execution plan before coding | `planner` |
| External documentation, upstream behavior, GitHub-source research, or source-backed comparisons before coding or review | `researcher` |
| Creating or updating documentation files, README files for any component or pack, migration notes, contract explanations, walkthroughs, user-facing technical guides, or running markdownlint, spellcheck, or link validation on docs | `docs` |
| Code review, PR review, diff review, architecture review, security review, maintainability review, correctness review, regression-risk review, test coverage review, or a bare codebase audit | `review` |
| xanadAssistant setup, inspect, interview, health-check, health-report, plan, update, repair, factory-restore, or a health-check workflow | `xanadLifecycle` |
| Moving files, regrouping folders, fixing broken paths, or building logical repository layouts | `organise` |
| First-pass complexity assessment before choosing an execution path — simple prompt vs. agent invocation | `triage` |

## Handoff Rules

- `xanadLifecycle` may delegate to `explore` for repo inventory, `debugger` for failing lifecycle behavior, and `planner` for phased remediation.
- `cleaner` may delegate to `review` for security-sensitive or policy-owned files, `organise` when cleanup turns into file moves or reshaping, `docs` when cleanup changes maintenance guidance or user-facing references, and `commit` when the approved scope is ready to stage.
- `review` may delegate to `explore` for inventory, `debugger` for concrete reproduction, `planner` for remediation planning, and `researcher` for current external constraints.
- `debugger` stays read-only and returns diagnosis, evidence, and the minimal next fix step. It may delegate to `explore` when the failure spans unfamiliar files and a read-only inventory is needed first, `review` when the likely cause involves a contract boundary, security posture, or architecture assumption, `planner` when root cause is known but the fix spans multiple files or needs staged verification, and `researcher` when the failure appears to depend on current upstream behavior or source-specific constraints.
- `planner` stays read-only and returns an executable plan with file list, risks, and verification. It may delegate to `explore` for a broader inventory before the plan is credible, `debugger` when broken state must be diagnosed first, `review` for contract or architecture analysis the plan depends on, `researcher` for external doc constraints, and `docs` to persist the plan as a project document.
- `researcher` stays read-only and returns source-backed findings, constraints, and recommended next steps. It may delegate to `explore` for a broader local inventory, `planner` when findings imply a multi-step remediation path, `docs` to convert findings into maintained documentation, and `review` when findings need to become correctness or regression-risk findings.
- `organise` stays structural-only — no semantic implementation unless explicitly widened by the caller. It may delegate to `explore` for a read-only inventory of callers before moving files, and `docs` when moves require updating user-facing references or migration guides.
- `deps` may delegate to `researcher` for replacement-candidate research, `explore` for local import/usage inventory, and `review` for security findings that require deeper analysis.
- `commit` may delegate to `explore` for scope lookup before staging, `review` for pre-commit diff review, and `debugger` for unexpected git failures.
- `docs` may delegate to `researcher` for external references, `explore` for local accuracy checks, `review` for doc quality, and `planner` when the documentation scope is broad.
- `triage` classifies task complexity and recommends the minimal execution path. It may delegate to `planner` for Compound or Complex tasks that need a scoped plan before implementation.
- Do not introduce a separate routing manifest. Agent frontmatter plus this file is the routing authority.
- Multi-level delegation chains (A invokes subagent B, which invokes subagent C) require `chat.subagents.allowInvocationsFromSubagents: true` in VS Code workspace settings. This workspace has that setting enabled; consumer workspaces have it installed automatically via the settings surface.
- `researcher` and `planner` each list the other in their `agents:` arrays. Circular delegation at one level is intentional, but recursion is not. When a `researcher → planner → researcher` or `planner → researcher → planner` chain reaches the second iteration, the inner agent must return its output rather than delegating again.

## Recommended Handoff Patterns

Use these patterns when a task crosses specialist boundaries but should still stay narrow and deliberate.

| Start | Hand off to | Use when |
| --- | --- | --- |
| `cleaner` | `review` | Cleanup touches security-sensitive files, managed surfaces, or policy-owned content |
| `cleaner` | `organise` | Cleanup turns into file moves, path repair, or repository reshaping |
| `cleaner` | `docs` | Cleanup changes archive conventions, maintenance guidance, or user-facing references |
| `review` | `explore` | Inventory of unfamiliar files or symbols is needed before the review can proceed |
| `review` | `debugger` | A finding depends on reproducing a failure or isolating a concrete regression before the review is credible |
| `review` | `planner` | Findings imply a phased remediation path rather than a single local fix |
| `review` | `researcher` | The review depends on current upstream docs, release behavior, or external contract constraints |
| `debugger` | `explore` | The failure spans unfamiliar files and a read-only inventory is needed before root-cause isolation |
| `debugger` | `review` | The likely cause involves a contract boundary, security posture, or architecture assumption requiring structured review |
| `debugger` | `planner` | Root cause is known, but the fix spans multiple files or needs staged verification |
| `debugger` | `researcher` | The failure appears to depend on current upstream behavior or source-specific constraints |
| `planner` | `researcher` | The plan depends on external docs, MCP behavior, GitHub-source semantics, or version-specific rules |
| `planner` | `docs` | The plan should be preserved as migration guidance, operational notes, or a maintained project document |
| `researcher` | `docs` | Source-backed findings should become maintained repo documentation instead of remaining a one-off summary |
| `docs` | `researcher` | Documentation accuracy depends on current external references or upstream behavior |
| `docs` | `review` | The document needs a final correctness and coverage pass before it is considered complete |
| `commit` | `explore` | Scope of staged changes is unclear before committing |
| `commit` | `review` | User requests a diff review before the commit is made |
| `commit` | `debugger` | A git command fails unexpectedly and the cause is unclear |
| `xanadLifecycle` | `debugger` | `inspect`, `health-check`, `health-report`, `plan`, `setup`, `update`, or `repair` results are surprising or failing and the control path is unclear |
| `xanadLifecycle` | `planner` | Repair, update, migration, or factory-restore work needs phased remediation before execution |
| `xanadLifecycle` | `explore` | Workspace inventory is needed before a lifecycle operation can be scoped or validated |
| `cleaner` | `commit` | Cleanup scope is approved and changes are ready to stage |
| `deps` | `researcher` | A package is abandoned or a replacement candidate needs source-backed research |
| `deps` | `explore` | Local usage of a package must be confirmed before removing or replacing it |
| `deps` | `review` | Security findings or dependency changes need deeper architectural review |
| `docs` | `explore` | Documentation accuracy requires confirming local implementation details before writing |
| `docs` | `planner` | The documentation scope is broad enough to warrant a scoped plan before drafting |
| `planner` | `explore` | A broader read-only inventory is needed before the plan is credible |
| `planner` | `debugger` | Existing failures or unclear broken state must be diagnosed before the plan is reliable |
| `planner` | `review` | The plan depends on contract, architecture, or regression-risk analysis |
| `researcher` | `explore` | A broader local inventory is needed before spending time on upstream sources |
| `researcher` | `planner` | Research findings imply a multi-step implementation or remediation path |
| `researcher` | `review` | Research output needs to be translated into correctness, contract, or regression-risk findings |
| `organise` | `explore` | A read-only inventory of callers or affected file clusters is needed before moving files |
| `organise` | `docs` | File moves require updating documentation, migration guides, or user-facing references |
| `triage` | `planner` | Task is Compound or Complex and needs a scoped execution plan before implementation |

## Lifecycle Trigger Phrases

| Trigger phrase | Route |
| --- | --- |
| `inspect workspace` | `xanadLifecycle` |
| `run lifecycle check` | `xanadLifecycle` |
| `repair install` | `xanadLifecycle` |
| `update xanadAssistant` | `xanadLifecycle` |
| `factory restore` | `xanadLifecycle` |
| `health check` | `xanadLifecycle` |
| `run health check` | `xanadLifecycle` |

Natural-language requests to add a convention or preference to instructions, such as `Remember this for next time` or `Add this to your instructions`, are not lifecycle operations.

## Model Selection

Each agent's frontmatter lists models in preference order. The first entry is the default; subsequent entries are fallbacks. Fallback ordering follows **closer task-fit before lighter-but-less-capable models** — prefer the next model that still matches the work profile over the cheapest available option.

| Default model | Agents | Rationale |
| --- | --- | --- |
| `Claude Sonnet 4.6` |cleaner, commit, deps, docs, organise, researcher, xanadLifecycle | General-purpose procedural work — instruction-following, structured output, multi-step execution. GitHub Copilot guidance recommends Sonnet-class models as the baseline for agentic tasks. |
| `GPT-5.4` |debugger, planner, review | Deep-reasoning tasks — root-cause isolation, multi-file planning, architectural and security review. GPT-5.4's reasoning depth pays off where correctness matters more than speed. |
| `GPT-5.4 mini` |explore | Codebase exploration and grep-style tooling. GitHub explicitly recommends a mini-class model here: fast symbol and file traversal does not require deep reasoning, and the lighter model keeps exploration loops responsive. |
| `Claude Haiku 4.5` |triage | Classification-only first-pass routing. Haiku 4.5 is fast and lightweight — appropriate when the task is a binary complexity judgment rather than implementation. |

Update this table whenever an agent's default model changes.

## Follow-up Adoption Work

The ranked review of additional template-repo agents that are still not adopted lives in `docs/template-review-adopt.md`.
