# xanadEval & agenticReview — Gap Review vs microsoft/waza

> Status: Research complete. Implementation not started.
> Sources: `tools/xanadEval/` (current), `skills/agenticReview/SKILL.md` (current), `microsoft/waza` v0.34.0 README + GRADERS.md (fetched 2026-06-02).

---

## Background

xanadEval is xanadassistant's Python static-analysis and eval-runner for Copilot surface files. It was inspired by the early Python releases of microsoft/waza (≤v0.3.2). Waza has since rewritten to Go (v0.4.0+, now at v0.34.0) and added a large surface of new commands and eval-spec features. xanadEval retains its Python foundation and its own integration story (xanadAssistant layout, agent-specific checks, agenticReview skill), but several waza features represent genuine gaps worth adopting.

---

## Section 1 — xanadEval: Current Capabilities

| Command | Description |
| --- | --- |
| `tokens <path>` | Token count, section count, code blocks, workflow steps, nesting depth |
| `check <path>` | Spec + advisory checks for agents and skills |
| `suggest <path>` | Scaffold eval task suite from frontmatter (heuristic, template-based) |
| `coverage [root]` | Skill-to-eval coverage report |
| `compare <ref>` | Git-ref token-diff |
| `report [paths]` | Self-contained HTML check report |
| `run <eval.yaml>` | Execute eval tasks against GitHub Models |
| `grade <eval.yaml>` | Re-run graders on existing results |
| `quality <path>` | LLM-as-judge scoring on 5 dimensions |
| `dev <path>` | Surface top improvement suggestions |
| `results list/compare/view` | Manage saved result files |

**Grader types supported:** `text`, `behavior`, `trigger`, `file`, `diff`, `code`, `action_sequence`, `tool_constraint`, `script`, `human`, `skill_invocation`, `llm`, `llm_comparison`, `prompt_judge`, `json_schema`.

---

## Section 2 — Waza v0.34 Features Not in xanadEval

### Priority 1 — Spec alignment (low effort, high value)

These are additive checks to `_static.py` that align with waza's `check` output and the evolving agentskills.io spec.

| Gap | Details |
| --- | --- |
| `spec-allowed-fields` check | Validate frontmatter contains only allowed keys. Waza rejects unknown fields; xanadEval ignores them silently. |
| `spec-version` check (skills) | Check for `metadata.version` field in SKILL.md frontmatter. |
| `spec-license` check (skills) | Check for `license` field in SKILL.md frontmatter. |
| `procedural-content` advisory | Detect that description contains procedural language ("when:", "use when:", etc.). xanadEval checks description presence and length but not language register. |
| Two positive-trigger tasks in `suggest` | Waza's `new eval` scaffolds `positive-trigger-1.yaml` **and** `positive-trigger-2.yaml`. xanadEval's `suggest` only creates one. The second positive task is the evals.instructions coverage requirement. |

### Priority 2 — Eval spec features (medium effort)

New keys supported in waza's eval YAML spec that would improve xanadEval's `run` command and task authoring:

| Feature | Waza key | Value for xanadEval |
| --- | --- | --- |
| Instruction file injection | `config.instruction_files: [...]` | Apply `.instructions.md` guidance during task execution; useful for testing agents in a realistic context. |
| Skip skill body for trigger evals | `config.inject_skill_body: false` | Enables trigger-precision evals that measure invocation without body injection. Critical for `trigger` grader tasks. |
| Tag-based task filtering | `waza run --tags smoke` | Run only tagged subsets; enables CI smoke vs. full regression split. |
| Task retries | `config.max_attempts: N` | Retry failed grader validations before marking a task failed — reduces flaky failures in CI. |
| Result grouping | `config.group_by: model` | Aggregate and display results by model or other dimension. Useful for multi-model comparison runs. |

### Priority 3 — New commands (larger effort)

| Waza command | Description | Adoptability |
| --- | --- | --- |
| `waza tokens suggest [paths]` | Heuristic + LLM-powered token-reduction suggestions per file | High — Python port is straightforward; heuristic-only is sufficient without `--copilot` flag |
| `waza new task from-prompt` | Record a live prompt run and auto-generate a task YAML with inferred validators | Medium — requires a live Copilot session; the non-recording form (heuristic inference) is already in `suggest` |
| `waza run --baseline` | A/B testing mode — runs each task twice without/with skill and computes improvement delta | Medium — provides the "does this skill actually help?" signal |
| `waza run --discover` | Auto-discover all SKILL.md + eval.yaml pairs and run them | High — trivial scan; already partially covered by `coverage` |
| `waza run --cache` | Cache results to skip re-execution on unchanged tasks | Low — useful for CI speedup; moderate implementation complexity |
| `waza tokens profile [path]` | Structural one-line summary with warnings — more human-readable than current `tokens` output | High — cosmetic improvement to existing `tokens` command |

### Priority 4 — Infrastructure (deferred)

These features depend on infrastructure not in scope for xanadEval's current Python architecture:

| Feature | Notes |
| --- | --- |
| `--parallel` concurrent workers | Requires thread-safe eval state; non-trivial in the current serial runner |
| Session logging (NDJSON) | Useful for debugging; not a correctness gap |
| `waza serve` web dashboard | We have HTML `report`; a full HTTP server is out of scope |
| Azure Blob Storage for results | Infrastructure dependency; not relevant to the Python-only install story |
| Git worktree task resources | Workspace materialization; relevant only for integration-style evals |
| CSV dataset support (`tasks_from`) | Useful for data-driven evals; medium-complexity addition |

---

## Section 3 — agenticReview Skill: Gaps

The agenticReview skill is well-structured across six modules. These gaps were found in comparison with waza's `check` output and the evolving spec:

| Gap | Module | Severity | Suggested addition |
| --- | --- | --- | --- |
| No `spec-version` / `spec-license` guidance | Module 5 (Coverage) | Medium | Add to the SKILL.md file-type coverage checklist: "Check for `metadata.version` and `license` fields per agentskills.io spec; absence is a Low-severity gap." |
| No `inject_skill_body` guidance for trigger evals | Module 5 (Coverage) | Low | Under "Skill files" coverage: "If `## When to use` relies heavily on trigger precision, flag that eval tasks should test with `inject_skill_body: false` to measure trigger isolation." |
| `positive-trigger-2` coverage requirement | Module 5 (Coverage) | Low | The evals.instructions.md convention requires only `positive-trigger-1`. Waza creates two. Consider noting that a second positive-trigger task improves coverage confidence. |
| No multi-trial flakiness guidance | Module 4 (Cognitive Load) | Low | Add: "When xanadEval `run` results are available, check `trials_per_task` ≥ 2; single-trial results mask flaky grader behavior." |
| No baseline/uplift measurement step | Module 5 (Coverage) | Low | Add: "If `--baseline` results are available, verify the skill shows positive uplift (skill score > baseline score); near-zero or negative uplift is a coverage-gap finding." |
| `scope-coverage` rating criteria not linked to waza | Module 5 (Coverage) | Low | The LLM-as-judge completeness rating could explicitly note: "Cross-reference with `waza check` advisory `procedural-content` — a skill with no procedural language in its description typically scores Incomplete." |

---

## Section 4 — Waza Upstream Trajectory

Waza's Python-to-Go rewrite (v0.4.0, released ~4 months ago) is now stable at v0.34.0. The Python releases (≤v0.3.2) are frozen. Key trajectory observations:

1. **The spec is evolving** — `spec-allowed-fields`, `spec-version`, and `spec-license` are new checks that reflect the agentskills.io submission requirements, not just internal quality gates. These matter if xanadEval-validated skills are intended for the wider Copilot skill ecosystem.

2. **Trigger grader architecture has matured** — waza's `trigger_tests` grader type (separate from the heuristic `_grade_trigger`) runs tasks against actual Copilot sessions with skill body injection controlled via `inject_skill_body`. xanadEval's keyword-overlap heuristic is a reasonable offline proxy but cannot detect semantic invocation mismatches.

3. **`from-prompt` task recording is the biggest UX gap** — waza's ability to record a live prompt run and auto-generate a validated task YAML is the single most impactful capability xanadEval lacks. It eliminates the "write tasks by hand" burden for non-trivial skills.

4. **The Go rewrite is not directly portable** — waza is now a compiled Go binary with embedded Copilot CLI artifacts. The Python xanadEval architecture is deliberate (pip-installable, no binary dependencies) and should be retained. Port features selectively.

---

## Section 5 — Recommended Implementation Order

### Phase 1 — Spec alignment (Priority 1 items)

All additive, low-risk changes to `tools/xanadEval/_static.py` and `evals.instructions.md`:

1. Add `spec-allowed-fields` advisory check to `_check_items_skill` — warn on unknown frontmatter keys.
2. Add `spec-version` and `spec-license` advisory checks to `_check_items_skill`.
3. Add `procedural-content` advisory check to `_check_items_skill` — detect "when:", "use when:", or "how to" in description.
4. Add `positive-trigger-2.yaml` to `cmd_suggest` scaffold output.
5. Update `evals.instructions.md` to require two positive-trigger tasks (not one) per coverage requirements.

Tests: add cases to `tests/tools/` for each new check.

### Phase 2 — Eval spec features (Priority 2 items)

Changes to `_common.py` / `_dynamic.py` to support new eval YAML keys:

1. `instruction_files` — parse and pass to executor context.
2. `inject_skill_body` — plumb through to the `run` command's skill injection logic.
3. `--tags` filter — simple glob match on task `tags` list.
4. `max_attempts` — retry loop around grader execution.
5. `group_by` — aggregate results by a config dimension.

### Phase 3 — New commands (Priority 3 items, individual spikes)

1. `tokens suggest` — heuristic token-reduction analysis (redundant sentences, long tables, over-specified steps).
2. `run --discover` — walk `skills/` + `evals/` and enqueue all found eval.yaml files.
3. `tokens profile` — reformat `tokens` output as a one-line summary with threshold warnings.
4. `run --baseline` — run each task twice, compute delta; deferred until Phase 2 executor changes land.

### Phase 4 — agenticReview skill updates

After Phase 1 spec checks are implemented, update `skills/agenticReview/SKILL.md` to:
- Add `spec-version`, `spec-license`, `procedural-content`, and two-positive-trigger coverage checklist items.
- Add multi-trial flakiness note in Module 4.
- Add baseline uplift check in Module 5.

---

## Section 6 — What Does NOT Need Porting

| Waza feature | Reason to skip |
| --- | --- |
| Go binary + LFS embedded Copilot CLI | Architecture mismatch; pip-installable Python is the right path for xanadEval |
| Azure Blob Storage | Infrastructure dependency not in scope |
| `waza serve` HTTP dashboard | `report` HTML command covers the local visualization need |
| CSV `tasks_from` | Niche use case; low priority until skill count grows |
| Session logging NDJSON | Useful for debugging but not a correctness or coverage gap |
| `waza models` | GitHub Models API enumeration already handled by caller configuration |
| `git worktree` task resources | Integration-test use case; out of scope for skill quality evals |
