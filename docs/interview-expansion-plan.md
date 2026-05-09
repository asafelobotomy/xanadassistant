# Interview Expansion Plan

> Status: Draft v2 — expanded after cross-repo comparison and external research.
> Sources: `copilot-instructions-template` interview.md + setup.agent.md + template;
> GitHub Copilot customization docs; progressive-disclosure UX research.
> This plan is read-only until approved.

---

## Current State

xanadassistant delivers 5 interview questions and 2 resolved tokens:

| Answer key | Kind | Resolves |
| --- | --- | --- |
| `profile.selected` | choice | `{{XANAD_PROFILE}}` — written to installed instructions |
| `packs.selected` | multi-choice | gates `lean-skills` surface install |
| `ownership.agents` | choice | plugin-backed vs local file delivery |
| `ownership.skills` | choice | plugin-backed vs local file delivery |
| `mcp.enabled` | confirm | gates 3-file MCP install |

The installed `template/copilot-instructions.md` has 4 additional tokens that are
**never resolved**, so every consumer receives literal placeholder text:

| Token | Location |
| --- | --- |
| `{{PROJECT_NAME}}` | Title (line 1) and role description (line 8) |
| `{{TEST_COMMAND}}` | Key Commands table (line 14) |
| `{{PRIMARY_LANGUAGE}}` | Coding Conventions (line 56) |
| `{{PACKAGE_MANAGER}}` | Coding Conventions (line 56) |

---

## Research Findings

### 1. The CIT setup agent auto-detects workspace stack (§1)

The predecessor setup agent reads `package.json`, `pyproject.toml`, `Cargo.toml`,
`go.mod`, `Makefile` to infer language, runtime, package manager, test framework,
and project name **before asking any questions**. Only when detection fails does it
fall back to `{{PLACEHOLDER}}`. This is a fundamentally better UX than freetext
questions — and the xanadassistant lifecycle engine already has access to the
workspace path during `plan setup`.

**Implication for T1-B**: rather than adding freetext interview questions for
`{{TEST_COMMAND}}`, `{{PRIMARY_LANGUAGE}}`, and `{{PACKAGE_MANAGER}}`, implement a
workspace scanner (`_workspace_scan.py`) that auto-detects these values. The plan
then shows detected values in its summary. No new question kind is needed.

### 2. The CIT installed template is far richer

Comparing CIT's `template/copilot-instructions.md` against xanadassistant's shows
roughly 12 additional tokens and 5 additional content sections that xanadassistant
doesn't install:

| CIT section | CIT tokens | xanadassistant equivalent |
| --- | --- | --- |
| §1 Lean Principles | `{{VALUE_STREAM_DESCRIPTION}}`, `{{FLOW_DESCRIPTION}}` | None |
| §2 Standardised Work Baselines | `{{LOC_WARN_THRESHOLD}}`, `{{LOC_HIGH_THRESHOLD}}`, `{{DEP_BUDGET}}`, `{{DEP_BUDGET_WARN}}`, `{{TEST_COMMAND}}`, `{{TYPE_CHECK_COMMAND}}`, `{{THREE_CHECK_COMMAND}}`, `{{INTEGRATION_TEST_ENV_VAR}}`, `{{SUBAGENT_MAX_DEPTH}}` | None |
| §3 PDCA + Structured Thinking | (prose only) | Partial — PDCA present |
| §4 Coding Conventions | `{{LANGUAGE}}`, `{{RUNTIME}}`, `{{PACKAGE_MANAGER}}`, `{{TEST_FRAMEWORK}}`, `{{PREFERRED_SERIALISATION}}`, `{{CODING_PATTERNS}}` | `{{PRIMARY_LANGUAGE}}`, `{{PACKAGE_MANAGER}}` (broken) |
| §6 Waste Catalogue (W1–W16) | (prose only) | None |
| §7 Metrics table | `{{LOC_COMMAND}}` | None |
| §8 Living Update Protocol | (prose only) | None |

### 3. GitHub's own guidance on instructions files

From the GitHub Blog (Nov 2025, updated Apr 2026) on effective instructions:

- Files over ~1,000 lines show **inconsistent behavior** — keep the installed file concise.
- Short, imperative rules work better than paragraphs.
- Separate language-specific rules into path-specific `.instructions.md` files
  (already done via xanadassistant's `instructions/` surface).
- The `copilot-instructions.md` file should contain team standards and routing;
  language/tool specifics belong in scoped stubs.

**Implication**: the installed `copilot-instructions.md` should stay short.
Not everything from CIT §1–§8 needs to be replicated — but the token pipeline
fix and a curated subset of the richer sections would add real value.

### 4. `ui-agent-contract.md` is silent on question kinds

The contract covers phase labels and stdout/stderr split only. No contract update
is needed if a new `freetext` question kind is added. However, with workspace
auto-detection (finding 1), `freetext` questions may not be needed at all.

### 5. Progressive disclosure UX research

Best practice for setup wizards:

- Show only **essential** questions first (3–5 max).
- Unlock deeper options after core choices. CIT uses tiers: Q (always) → S
  (optional) → F (full) → Skip.
- Group questions into batches of 3–4.
- Show detected/default values prominently so users can accept quickly.
- Completion rates rise ~94% when steps are revealed progressively.

---

## Revised Plan

### Tier 0 — Token pipeline bug (prerequisite, no new questions)

**Bug**: `preserve-marked-markdown-blocks` strategy in `_plan_utils.py →
expected_entry_bytes()` never calls `render_tokenized_text()`, so all tokens in
`copilot-instructions.md` pass through as literal placeholders. Only the
`token-replace` strategy (used for `prompts/`) calls the renderer.

**Fix**: inside the `preserve-marked-markdown-blocks` branch of
`expected_entry_bytes()`, apply `render_tokenized_text()` to the source text
before the markdown merge step. One-line change; the token_values dict is already
threaded through at the call site.

Files: `scripts/lifecycle/_xanad/_plan_utils.py`
Tests: add assertion to an existing phase5 test that `{{WORKSPACE_NAME}}` is
resolved (not literal) in the installed instructions content.

---

### Tier 1-A — `{{PROJECT_NAME}}` → `{{WORKSPACE_NAME}}` (no new question)

`{{WORKSPACE_NAME}}` is already resolved and registered. `{{PROJECT_NAME}}` is
redundant. Replace all occurrences in `template/copilot-instructions.md` with
`{{WORKSPACE_NAME}}`. Template-only change; manifest regen required.

Files: `template/copilot-instructions.md`, manifest regen.

---

### Tier 1-B — Workspace auto-detection (new scanner module, no new questions)

Instead of freetext interview questions, add a workspace scanner that auto-detects
`{{TEST_COMMAND}}`, `{{PRIMARY_LANGUAGE}}`, `{{PACKAGE_MANAGER}}`, and optionally
`{{TEST_FRAMEWORK}}` and `{{TYPE_CHECK_COMMAND}}` from workspace project files:

| Detected from | Tokens inferred |
| --- | --- |
| `package.json` → `scripts.test` | `{{TEST_COMMAND}}` |
| `package.json` → `devDependencies` keys | `{{PACKAGE_MANAGER}}` (npm), `{{TEST_FRAMEWORK}}` |
| `pyproject.toml`, `setup.py` | `{{PRIMARY_LANGUAGE}}` (Python), `{{TEST_FRAMEWORK}}` (pytest) |
| `Cargo.toml` | `{{PRIMARY_LANGUAGE}}` (Rust), `{{TEST_COMMAND}}` (`cargo test`) |
| `go.mod` | `{{PRIMARY_LANGUAGE}}` (Go), `{{TEST_COMMAND}}` (`go test ./...`) |
| `pom.xml`, `build.gradle` | `{{PRIMARY_LANGUAGE}}` (Java) |
| `yarn.lock` | `{{PACKAGE_MANAGER}}` (yarn) |
| `pnpm-lock.yaml` | `{{PACKAGE_MANAGER}}` (pnpm) |
| `Makefile` containing `test:` | `{{TEST_COMMAND}}` (`make test`) |
| `Gemfile` | `{{PRIMARY_LANGUAGE}}` (Ruby) |

When detection is confident, the token value is set silently. When detection
finds multiple candidates or nothing, the token is left blank or set to a
human-readable placeholder (`<your test command>`). The plan output shows a
`stackDiscovery` section listing what was detected and what remains unresolved.

**Engine changes:**

- New `scripts/lifecycle/_xanad/_workspace_scan.py` (new file, ≤150 lines).
- `_conditions.py → resolve_token_values()` — call scanner for new tokens.
- `install-policy.json → tokenRules` — add entries for new tokens.
- `template/copilot-instructions.md` — ensure tokens present in context.
- `_plan_b.py` — surface scan results in plan output `stackDiscovery` field.
- Tests — unit tests for the scanner against inline fixture workspace layouts.

**Non-interactive mode**: tokens that aren't detected remain empty; token
substitution is skipped for empty values (template line left with placeholder
text so the consumer can fill it in manually).

---

### Tier 2-A — `response.style` (from CIT S1)

**Why**: The single highest-impact personalisation from CIT. Sets the
verbosity of all agent responses. Matches what developers consistently ask about
in community threads ("how to make Copilot less chatty").

**Question:**

```text
How much explanation do you want alongside generated code?
  concise     — code + one-liner rationale
  balanced    — code + brief explanation  [recommended]
  verbose     — code + full reasoning chain
```

**Answer key**: `response.style`
**Token**: `{{RESPONSE_STYLE}}`
**Token values**:

- `concise` → `Concise — code with one-liner rationale only.`
- `balanced` → `Balanced — code with brief explanation.`
- `verbose` → `Verbose — code with full reasoning chain.`

**Template placement** (new line in Operating Modes section):

```markdown
**Response style**: {{RESPONSE_STYLE}}
```

**Engine changes**: `_interview.py` (1 question, existing `choice` kind),
`_conditions.py` (1 elif branch), `install-policy.json` (1 tokenRule entry),
`template/copilot-instructions.md` (1 line added).

---

### Tier 2-B — `autonomy.level` (from CIT S5)

**Why**: "Ambiguity handling" is one of the most common pain points with AI
coding agents — either too much asking or too much doing. Making this explicit
at setup time aligns the agent to the developer's workflow style.

**Question:**

```text
How should I act when something is ambiguous?
  ask-first      — always confirm before acting  [recommended]
  act-then-tell  — proceed and report what was done
  best-judgement — act on the most reasonable interpretation
```

**Answer key**: `autonomy.level`
**Token**: `{{AUTONOMY_LEVEL}}`
**Token values**:

- `ask-first` → `Ask first — always confirm before acting on ambiguity.`
- `act-then-tell` → `Act then tell — proceed and report what was done.`
- `best-judgement` → `Best judgement — act on the most reasonable interpretation.`

**Template placement** (new line in Operating Modes section):

```markdown
**Ambiguity handling**: {{AUTONOMY_LEVEL}}
```

**Engine changes**: same pattern as T2-A.

---

### Tier 2-C — `agent.persona` (from CIT E17)

**Why**: Tone dramatically affects how productive sessions feel. Developers
working alone often prefer `direct`; onboarding developers prefer `mentor`.
This has no code impact — it's purely about session feel.

**Question:**

```text
What tone and personality do you prefer?
  professional    — concise, neutral, precise  [recommended]
  mentor          — explain as you go, teach patterns
  pair-programmer — collaborative, think out loud
  direct          — minimal preamble, maximum signal
```

**Answer key**: `agent.persona`
**Token**: `{{AGENT_PERSONA}}`

**Token values** (each expands to a short behavioral note):

- `professional` → `Professional — concise, neutral, precise.`
- `mentor` → `Mentor — explain patterns and decisions as you go.`
- `pair-programmer` → `Pair programmer — think out loud, invite feedback.`
- `direct` → `Direct — minimal preamble, maximum signal.`

**Template placement** (new line in Operating Modes section):

```markdown
**Tone**: {{AGENT_PERSONA}}
```

**Engine changes**: same pattern as T2-A.

---

### Tier 3-A — `testing.philosophy` (from CIT S4)

**Why**: Controls a key behavioral rule in the Coding Conventions section —
whether tests are always written, suggested, or skipped unless requested. The
current template has no guidance on this.

**Question:**

```text
How should I handle tests?
  always   — write tests alongside every code change  [recommended]
  suggest  — propose tests but don't write without asking
  skip     — skip tests unless explicitly requested
```

**Answer key**: `testing.philosophy`
**Token**: `{{TESTING_PHILOSOPHY}}`

**Token values**:

- `always` → `Always — write tests alongside every code change.`
- `suggest` → `Suggest — propose but don't write tests without explicit request.`
- `skip` → `Skip unless asked.`

**Template placement** (new line in Coding Conventions):

```markdown
**Testing**: {{TESTING_PHILOSOPHY}}
```

---

### Tier 3-B — `loc.thresholds` (from CIT A10)

**Why**: The installed instructions should document the LOC standards for the
consumer project, just as xanadassistant's own `check_loc.py` documents them
for this repo. This question controls the **instructions content** — it is
independent of the repo-side LOC gate (`check_loc.py`) which always uses its
own hardcoded limits.

**Question:**

```text
What LOC thresholds should I enforce in instructions?
  strict    — warn 150 lines, hard limit 300
  standard  — warn 250 lines, hard limit 400  [recommended]
  relaxed   — warn 400 lines, hard limit 600
  none      — no LOC guidance in instructions
```

**Answer key**: `loc.thresholds`
**Tokens**: `{{LOC_WARN}}`, `{{LOC_HARD}}`

**Token values by option**:

| Option | `{{LOC_WARN}}` | `{{LOC_HARD}}` |
| --- | --- | --- |
| `strict` | 150 | 300 |
| `standard` | 250 | 400 |
| `relaxed` | 400 | 600 |
| `none` | — | — |

When `none` is selected, the LOC row is omitted from the template via a
conditional token-strip mechanism. This requires a new `"kind": "omit-if-blank"`
token behavior, or alternatively a sentinel value (e.g., `0`) that the template
renders as a note to ignore.

**Template placement** (new Standardised Work Baselines mini-table):

```markdown
| Baseline | Warn | Hard limit |
| --- | --- | --- |
| File LOC | {{LOC_WARN}} lines | {{LOC_HARD}} lines |
```

**Note on separation**: the note "This controls instructions guidance only;
the repo-side `check_loc.py` gate uses its own limits" should appear in the
template so consumers understand the two are independent.

---

### Tier 4 (future, not planned for this sprint) — Additional CIT tokens

These are identified for future consideration but are deferred because they
require either significant template expansion or are too project-specific to
have useful defaults:

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

## Progressive Disclosure Structure

After this work, the interview would look like:

**Batch 1 — Always asked (essential, 5 questions):**

1. `profile.selected` — behavior profile
2. `packs.selected` — optional packs
3. `ownership.agents` / `ownership.skills` — delivery mode (shown as one question with sub-options, or two)
4. `mcp.enabled` — MCP configuration

**Batch 2 — Personalisation (Tiers 2–3, 4 questions):**

- `response.style`
- `autonomy.level`
- `agent.persona`
- `testing.philosophy`

**Batch 3 — Advanced (Tier 3-B, 1 question):**

- `loc.thresholds`

In `--non-interactive` mode, all questions use their `default` values. The
scanner always runs silently.

Total with all tiers: 9 questions (up from 5). Well within progressive
disclosure limits.

---

## What Is Not Being Adopted

| CIT question | Reason |
| --- | --- |
| S2 — Experience level | xanadassistant is a lifecycle tool, not a general tutor |
| S3 — Primary mode (speed/quality/learning) | Covered by `profile.selected` |
| S6 — Unified ownership mode | Already split more precisely into `ownership.agents` + `ownership.skills` |
| A6 — Code style (linter/style guide) | Too workspace-specific to bake in at install time |
| A7 — Documentation level | Too broad |
| A8 — Error handling | Too broad |
| A9 — Security flagging aggressiveness | Too broad |
| A11 — Dependency philosophy | Context-specific |
| A12 — Instruction editing permission | Governed by xanadassistant's managed-surface model |
| A13 — Refactoring stance | Context-specific |
| A14 — Reporting style | Deferred (nice to have) |
| A15 — Skill search | Not applicable to xanadassistant's plugin model |
| A16 — Lifecycle hooks | Already covered by `mcp.enabled` derivation |
| A17 — Prompt commands | Prompts are always a core surface |
| A18 — Plugin authoring conventions | Maintainer-only, not consumer-facing |
| CIT §1 Lean Principles (full) | Too prescriptive for a generic template |
| CIT §6 Waste Catalogue | Installed in CIT template; deferred for xanadassistant |
| CIT §8 Living Update Protocol | The xanadassistant managed-surface model replaces this |
| E16–E24 (misc.) | Out of scope or VS Code/model-level concerns |

---

## Implementation Order

```text
Tier 0  →  Tier 1-A  →  Tier 1-B  →  Tier 2 (A, B, C)  →  Tier 3 (A, B)
```

- Tier 0 and Tier 1-A are independent; can be done in parallel.
- Tier 1-B depends on Tier 0 (token pipeline must work before new auto-detected tokens are meaningful).
- Tier 2 depends on Tier 0 for the same reason.
- Tier 3 depends on Tier 2 being done first (pattern established).

Each tier: manifest regen → targeted tests → full suite at task completion.

---

## Open Questions (resolved and unresolved)

| # | Question | Status |
| --- | --- | --- |
| 1 | Does `--non-interactive` handle blank freetext tokens? | Resolved — auto-detection replaces freetext; blanks leave placeholder text in installed file |
| 2 | Where exactly in the template do Tier 2 tokens appear? | Open — exact line placement needs agreement before editing template |
| 3 | Does `ui-agent-contract.md` enumerate allowed question kinds? | Resolved — it does not; no contract update needed |
| 4 | LOC `none` option — how to omit rows from the template? | Open — sentinel vs conditional-omit mechanism needs decision |
| 5 | Should `ownership.agents` + `ownership.skills` be merged into one question with a sub-option? | Open — currently two questions; CIT uses one; could simplify |

---

## Files Affected Summary

| File | Tiers |
| --- | --- |
| `scripts/lifecycle/_xanad/_plan_utils.py` | Tier 0 |
| `scripts/lifecycle/_xanad/_workspace_scan.py` (new) | Tier 1-B |
| `scripts/lifecycle/_xanad/_conditions.py` | Tier 0, 1-B, 2, 3 |
| `scripts/lifecycle/_xanad/_interview.py` | Tier 2, 3 |
| `scripts/lifecycle/_xanad/_plan_b.py` | Tier 1-B (stackDiscovery output field) |
| `template/copilot-instructions.md` | Tier 1-A, 1-B, 2, 3 |
| `template/setup/install-policy.json` | Tier 1-B, 2, 3 |
| `template/setup/install-manifest.json` (generated) | After each tier |
| `template/setup/catalog.json` (generated) | After each tier |
| `tests/test_phase5a.py` or `test_phase5b.py` | Tier 0 |
| New test file or extensions to existing phase tests | Tier 1-B, 2, 3 |
