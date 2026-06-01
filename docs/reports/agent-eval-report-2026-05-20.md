# Agent xanadEval Audit — 2026-05-20

Full report from four xanadEval passes run across all 12 agents in `agents/`.

| Pass | Command | Requires API |
| --- | --- | --- |
| Structural metrics | `xanadEval tokens` | No |
| Spec compliance | `xanadEval check` | No |
| Quality scoring | `xanadEval quality` | Yes (gpt-4o-mini) |
| Improvement analysis | `xanadEval dev` | Yes (gpt-4o-mini) |

---

## 1. Structural Metrics (`tokens`)

| Agent | Tokens | Sections | Code blocks | Workflow detected | Max nesting |
| --- | --- | --- | --- | --- | --- |
| cleaner | 919 | 5 | 1 | yes | **4** |
| commit | 2 325 | 15 | 0 | yes | 2 |
| debugger | 608 | 4 | 0 | yes | 2 |
| deps | 2 061 | 22 | 2 | yes | 2 |
| docs | 513 | 4 | 0 | yes | 2 |
| explore | 689 | 4 | 0 | yes | 2 |
| organise | 759 | 4 | 0 | yes | 2 |
| planner | 546 | 4 | 0 | yes | 2 |
| researcher | 825 | 5 | 0 | yes | 2 |
| review | 953 | 7 | 0 | yes | 2 |
| triage | 857 | 5 | 1 | yes | 2 |
| xanadLifecycle | 3 357 | 25 | 14 | yes | 2 |

**Notable:** `cleaner` has max nesting depth 4, which exceeds the advisory threshold of 3 used by `check`.

---

## 2. Spec Compliance (`check`)

The `check` command is designed for `SKILL.md` files. Agents use a different
structural convention, so several checks fire as false positives for all 12
agents (`spec-dir-match`, `spec-verify-checklist`, `spec-when-to-use`,
`spec-when-not-to-use`, `spec-steps-or-modules`, `module-count`,
`eval-presence`). Those are noted but not treated as actionable bugs.

### Compliance ratings

| Agent | Compliance | Genuine failures |
| --- | --- | --- |
| cleaner | Low | `complexity` (depth 4), `negative-delta-risk` (1 pattern) |
| commit | Low | `negative-delta-risk` (1 pattern) |
| debugger | Medium | — |
| deps | Medium | — |
| docs | Medium | — |
| explore | Medium | — |
| organise | Medium | — |
| planner | Medium | `over-specificity` at threshold (10 rules) |
| researcher | Medium | — |
| review | Medium | — |
| triage | Medium | — |
| xanadLifecycle | Low | `negative-delta-risk` (2 patterns — highest count) |

### Spec check raw output (genuine checks only)

#### cleaner

```json
{ "id": "complexity",           "pass": false, "detail": "max nesting depth: 4 (threshold: 3)" }
{ "id": "negative-delta-risk",  "pass": false, "detail": "negative-delta patterns: 1 found" }
```

#### commit

```json
{ "id": "negative-delta-risk",  "pass": false, "detail": "negative-delta patterns: 1 found" }
```

#### planner

```json
{ "id": "over-specificity",     "pass": false, "detail": "max rules per section: 10 (threshold: 10)" }
```

#### xanadLifecycle

```json
{ "id": "negative-delta-risk",  "pass": false, "detail": "negative-delta patterns: 2 found" }
```

All other agents pass every genuine advisory check.

### Universal false positives (all 12 agents)

`spec-dir-match`, `spec-verify-checklist`, `spec-when-to-use`,
`spec-when-not-to-use`, `spec-steps-or-modules`, `module-count` — all fail
because `check` expects SKILL.md file conventions. Not actionable for agents.

`eval-presence` — no eval suite exists for any agent (expected paths:
`evals/{Name}/eval.yaml`). This is a real coverage gap but a separate work
item from the compliance check failures.

---

## 3. Quality Scoring (`quality`, gpt-4o-mini)

Five dimensions: `clarity`, `completeness`, `trigger_precision`, `scope_coverage`, `anti_patterns`.

| Agent | Clarity | Completeness | Trigger precision | Scope | Anti-patterns | **Overall** |
| --- | --- | --- | --- | --- | --- | --- |
| cleaner | 0.90 | 1.00 | 0.90 | 0.90 | 1.00 | **0.94** |
| organise | 0.90 | 1.00 | 0.80 | 0.90 | 0.90 | **0.90** |
| researcher | 0.90 | 1.00 | 0.80 | 0.90 | 0.90 | **0.90** |
| deps | 0.90 | 1.00 | 0.80 | 0.90 | 0.80 | **0.88** |
| explore | 0.90 | 0.90 | 0.80 | 0.90 | 0.90 | **0.88** |
| review | 0.90 | 1.00 | 0.80 | 0.90 | 0.90 | **0.88** |
| triage | 0.90 | 1.00 | 0.80 | 0.90 | 0.90 | **0.88** |
| debugger | 0.90 | 1.00 | 0.80 | 0.90 | 0.90 | **0.86** |
| docs | 0.80 | 1.00 | 0.90 | 0.90 | 0.80 | **0.86** |
| xanadLifecycle | 0.80 | 1.00 | 0.90 | 0.90 | 0.80 | **0.86** |
| commit | 0.80 | 0.90 | 0.70 | 0.90 | 0.90 | **0.84** |
| planner | 0.80 | 0.90 | 0.70 | 0.80 | 0.90 | **0.82** |

### Summaries from model

- **cleaner (0.94)** — "Clear, complete, and precise with very few potential anti-patterns."
- **commit (0.84)** — "Mostly clear and thorough but could improve on specific trigger phrase precision."
- **debugger (0.86)** — "Well-structured and clear, but slight improvements can enhance precision and clarity."
- **deps (0.88)** — "Clear and complete, but could improve precision in triggers and address minor anti-patterns."
- **docs (0.86)** — "Clear and complete but could improve trigger precision and clarity in certain guidelines."
- **explore (0.88)** — "Clear and comprehensive, with minor areas for improvement in trigger specificity."
- **organise (0.90)** — "Well-defined with minor improvements needed in trigger precision."
- **planner (0.82)** — "Well-defined with strong guidelines, but some areas in trigger precision and clarity could be improved."
- **researcher (0.90)** — "Clear and comprehensive guidelines, with minor improvements needed for trigger precision."
- **review (0.88)** — "Well-structured and clear but could improve trigger specificity."
- **triage (0.88)** — "Clear classification framework and detailed guidance, with minor improvements needed for trigger precision."
- **xanadLifecycle (0.86)** — "Mostly clear and complete, but could benefit from clearer trigger phrases and more precise language."

---

## 4. Improvement Analysis (`dev`, gpt-4o-mini)

Same five dimensions as `quality`, scored independently. Surfaces the top 3
improvement suggestions per agent.

| Agent | Clarity | Completeness | Trigger | Scope | Anti-patterns | **Overall** |
| --- | --- | --- | --- | --- | --- | --- |
| deps | 0.80 | 0.90 | 0.85 | 0.90 | 0.95 | **0.82** |
| commit | 0.80 | 0.90 | 0.85 | 0.80 | 0.70 | **0.82** |
| researcher | 0.90 | 0.80 | 0.85 | 0.75 | 0.90 | **0.82** |
| xanadLifecycle | 0.80 | 0.90 | 0.85 | 0.90 | 0.70 | **0.82** |
| explore | 0.90 | 0.80 | 0.90 | 0.70 | 0.60 | **0.80** |
| organise | 0.85 | 0.80 | 0.75 | 0.90 | 0.60 | **0.78** |
| cleaner | 0.80 | 0.90 | 0.70 | 0.80 | 0.60 | **0.76** |
| debugger | 0.90 | 0.80 | 0.70 | 0.85 | **0.40** | **0.74** |
| triage | 0.90 | 0.80 | 0.70 | 0.85 | 0.50 | **0.74** |
| docs | 0.80 | 0.70 | 0.90 | **0.60** | 0.50 | **0.72** |
| review | 0.80 | 0.70 | **0.60** | 0.90 | 0.50 | **0.70** |
| planner | 0.80 | 0.70 | **0.60** | 0.75 | 0.50 | **0.66** |

### Top improvements per agent

#### cleaner (0.76)

1. Clarify examples for user prompts to avoid ambiguity.
2. Provide more explicit guidelines on what constitutes "stale" or "dead" files.
3. Incorporate more detailed case studies or scenarios to illustrate proper usage.

#### commit (0.82)

1. Provide examples for each git task in the description to enhance clarity.
2. Add more explicit warnings or checks for high-risk operations to prevent user errors.
3. Ensure that all sections are complete and properly formatted — current message conventions section is absent.

#### debugger (0.74)

1. Clarify the output style section with specific examples of structured diagnosis.
2. Provide more detailed instructions on what to do if `memory_dump` fails beyond just emitting a note.
3. Expand on the criteria for "minimal next fix step" to ensure agents can determine what qualifies as minimal.

#### deps (0.82)

1. Include specific examples in the documentation of each operation for better understanding.
2. Ensure that the process for citing sources is emphasized and clarified within the auditing section.
3. Add a troubleshooting guide or FAQ section for common issues users might encounter.

#### docs (0.72)

1. Expand the guidelines section to include examples of acceptable and unacceptable documentation formats.
2. Clarify the roles of each agent with specific use cases to enhance understanding for users.
3. Include a checklist for verifying commands, paths, and code examples to ensure thorough validation.

#### explore (0.80)

1. Add examples of common queries to improve user understanding.
2. Clarify the expected output format for different thoroughness tiers.
3. Include more specific guidelines for handling errors or unexpected inputs.

#### organise (0.78)

1. Include examples of common file organization issues that might arise.
2. Provide clearer definitions of terms like "logical directories" and "caller paths".
3. Outline specific scenarios that warrant stopping for ambiguity instead of proceeding.

#### planner (0.66)

1. Provide more specific examples of scoped execution plans to enhance clarity.
2. Include details on potential risks and how to handle them in the planning process.
3. Clarify the definitions of terms like "blast radius" and "stop conditions" for better understanding.

#### researcher (0.82)

1. Add specific examples of research targets to enhance understanding.
2. Clarify the output format to include more detailed sections.
3. Include potential pitfalls or common mistakes in the research process.

#### review (0.70)

1. Enhance the argument-hint with specific examples for various review types to improve clarity.
2. Specify consequences for ignoring the scoping question to guide users more effectively.
3. Add examples of findings to illustrate expected output structure and increase completeness.

#### triage (0.74)

1. Provide examples for each tier to enhance understanding of the classification process.
2. Clarify the circumstances under which to consider a task as Blocked to avoid confusion.
3. Suggest defining clear user confirmation steps for Blocked tasks to ensure safety before proceeding.

#### xanadLifecycle (0.82)

1. Provide more detailed examples of natural-language requests that should not trigger the agent.
2. Clarify the consequences of ignoring the authority section regarding file management.
3. Include a troubleshooting section for common issues users might encounter during lifecycle operations.

---

## 5. Bug Summary

### Bug Class A — Unresolved template variables (7 occurrences, 6 agents)

Found by: manual inspection triggered by `dev` anti_patterns scores and reading
agent source.

```text
agents/debugger.agent.md:37        {{pack:output-style}}
agents/docs.agent.md:36            {{agent:docs:output-style}}
agents/explore.agent.md:39         {{agent:explore:output-style}}
agents/planner.agent.md:38         {{agent:planner:plan-format}}
agents/review.agent.md:50          {{agent:review:reporting-threshold}}
agents/commit.agent.md:41          {{agent:commit:message-style}}
agents/commit.agent.md:45          {{agent:commit:secret-guard}}
```

**Critical — section body completely empty (placeholder is all there is):**

| Agent | Line | Section | Impact |
| --- | --- | --- | --- |
| `commit.agent.md` | 41 | `## Message conventions` | No commit format defined; all commits are free-form |
| `planner.agent.md` | 38 | `## Plan format` | No plan schema returned to callers |
| `docs.agent.md` | 36 | `## Output style` | No output format guidance |

**Non-critical — orphaned placeholder, real content present below:**

| Agent | Line | Section | Status |
| --- | --- | --- | --- |
| `debugger.agent.md` | 37 | `## Output style` | Bullet-point format defined directly below |
| `explore.agent.md` | 39 | `## Output style` | Output guidance present below |
| `review.agent.md` | 50 | `## Reporting threshold` | Default rule present below |
| `commit.agent.md` | 45 | `## Secret guard` | Stop directive present below |

### Bug Class B — Static compliance (genuine findings)

| Agent | Check | Detail |
| --- | --- | --- |
| `cleaner.agent.md` | `complexity` | Nesting depth 4, threshold 3; approval-gate YAML block is over-nested |
| `cleaner.agent.md` | `negative-delta-risk` | 1 negative-delta pattern |
| `commit.agent.md` | `negative-delta-risk` | 1 negative-delta pattern |
| `xanadLifecycle.agent.md` | `negative-delta-risk` | 2 negative-delta patterns |
| `planner.agent.md` | `over-specificity` | 10 rules/section — exactly at threshold |

### Bug Class C — Content gaps (from `dev` analysis)

| Agent | Dev overall | Primary gap |
| --- | --- | --- |
| `planner` | 0.66 | Empty plan format; undefined jargon ("blast radius", "stop conditions") |
| `review` | 0.70 | Empty reporting threshold; no example findings |
| `docs` | 0.72 | Empty output style; scope coverage gaps |
| `debugger` | 0.74 | Orphaned placeholder pollutes output style; criteria for "minimal fix step" unclear |
| `triage` | 0.74 | "Blocked" tier criteria underspecified |

### Coverage gap

No eval suite exists for any of the 12 agents.

---

## 6. Prioritized Fix List

| # | Severity | Agent | Action |
| --- | --- | --- | --- |
| 1 | Critical | `commit.agent.md` | Define `## Message conventions` — remove placeholder, add commit message format |
| 2 | Critical | `planner.agent.md` | Define `## Plan format` — remove placeholder, add plan schema |
| 3 | Critical | `docs.agent.md` | Define `## Output style` — remove placeholder, add output guidance |
| 4 | High | `debugger.agent.md` | Remove orphaned `{{pack:output-style}}` line |
| 5 | High | `explore.agent.md` | Remove orphaned `{{agent:explore:output-style}}` line |
| 6 | High | `review.agent.md` | Remove orphaned `{{agent:review:reporting-threshold}}` line |
| 7 | High | `commit.agent.md` | Remove orphaned `{{agent:commit:secret-guard}}` line |
| 8 | Medium | `cleaner.agent.md` | Reduce approval-gate nesting from depth 4 to ≤3 |
| 9 | Medium | `planner.agent.md` | Define "blast radius" and "stop conditions" inline |
| 10 | Medium | `triage.agent.md` | Clarify "Blocked" tier and user confirmation steps |
| 11 | Low | All 12 agents | Add eval suites under `evals/{Name}/eval.yaml` |
