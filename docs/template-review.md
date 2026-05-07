# Template Review — copilot-instructions-template vs xanadassistant

> Reviewed: 2026-05-07  
> Source repo: `/mnt/SteamLibrary/git/copilot-instructions-template` @ v0.7.0  
> Scope: architectural patterns, instruction file design, lifecycle model, memory, hooks, CI.

---

## Summary

| Category | Finding count |
|----------|--------------|
| What they did right — adopt or adapt | 8 |
| What they did wrong — avoid | 7 |
| What xanadassistant does better | 5 |
| What xanadassistant should adopt | 5 |

---

## What they did right

### R1 — Developer / consumer instruction separation

The hard invariant between `.github/copilot-instructions.md` (zero `{{}}` tokens,
developer layer) and `template/copilot-instructions.md` (placeholder version, consumer
layer) is the single best architectural decision in the repo. It makes the authoring
boundary unambiguous and CI-enforceable.

**CI implementation** (from `ci.yml`):

```yaml
# Developer instructions have no placeholder tokens
- name: Developer instructions have no placeholder tokens
  run: |
    unquoted=$(perl -pe 's/`[^`]*`//g' .github/copilot-instructions.md)
    count=$(echo "$unquoted" | grep -c '{{' 2>/dev/null || echo 0)
    if [[ "$count" -gt 0 ]]; then
      echo "Found $count unresolved tokens"; exit 1
    fi

# Template has placeholder tokens (not yet resolved)
- name: Template placeholders present
  run: |
    count=$(grep -c '{{' template/copilot-instructions.md 2>/dev/null || echo 0)
    [[ "$count" -ge 3 ]] || { echo "Only $count tokens — template may have been resolved"; exit 1; }
```

The backtick-stripping step (`perl -pe 's/\`[^\`]*\`//g'`) is important — it allows the
developer instructions to *document* `{{PLACEHOLDER}}` syntax without triggering the
check. The template's CI also enforces parity between `.github/instructions/` and
`template/instructions/` using a cross-reference validation script.

**Xanadassistant status**: `template/copilot-instructions.md` exists (6 lines) but there
is no equivalent CI gate on token presence or absence. The consumer layer and developer
layer are not formally separated. Because the file is so small now, the risk is low, but
the gate should be added before the file grows.

---

### R2 — CI-enforced LOC budgets on instruction sections

Hard line limits on `template/copilot-instructions.md` enforced by
`scripts/ci/validate-attention-budget.sh`, called from `ci.yml`:

| Budget | Limit | Sections |
|--------|-------|---------|
| Total file | 800 lines | All of §1–§14 |
| Per section (standard) | 120 lines | §1–§4, §6–§9 |
| §5 Operating Modes | 210 lines | Largest section; contains all workflow modes |
| §11–§14 (protocols) | 150 lines | Tool, skill, MCP, workspace knowledge |
| §10 Project-Specific Overrides | Unlimited | Grows with project |

The per-section check works by scanning for `## §N —` headings, computing the line span
between consecutive sections, and comparing against the tier limit. The last section's
span is computed as `TOTAL - last_section_start + 1`.

**Overflow rule** (§8): when a section approaches its budget, extract detailed procedures
into a skill file (`.github/skills/`), a path-specific instruction file
(`.github/instructions/`), or a prompt file (`.github/prompts/`). Leave a one-line
reference in the main section. This is the same progressive disclosure pattern as R5.

**Why this matters at scale**: once a consumer fills in §10 with project-specific overrides
(LOC command, test command, coding patterns, etc.) the file can reach 400–600 lines in a
real project. Without a hard gate, the file drifts beyond the model's reliable recall
horizon silently — no error, just degraded instruction-following for the sections loaded
earliest.

**Xanadassistant status**: no LOC gate exists on the instructions template. The current
`template/copilot-instructions.md` is 6 lines and the risk is low, but the gate should
be added alongside section numbering (A1+A2) before the file grows.

---

### R3 — Section numbering with CI-checkable cross-references

§1–§14 anchors on instruction sections enable precise cross-referencing from agents,
skills, and hooks. "See §12" survives restructuring, can be grepped, and can be
CI-checked for dangling references. Prose section names can't.

**Xanadassistant status**: the instructions template has no internal section numbering.
The `lifecycle-planning.agent.md` uses prose headings only.

---

### R4 — Living update protocol (§8)

A formal rule defining when and how the instructions file may be self-edited. Self-update
is triggered only by canonical phrases (`"Update your instructions"`,
`"Check for instruction updates"`, `"Sync instructions with the template"`, etc.) that
invoke the Setup agent — not by arbitrary agent judgment.

Key rules from §8:
- **Never delete** existing rules without explicit user instruction.
- **Additive by default** — append to sections; don't restructure.
- **Flag before writing** — describe the change and wait for confirmation before editing §1–§7.
- **Self-update trigger phrases**: `"Add this to your instructions"`,
  `"Remember this for next time"` — these add a convention to this file.
- **Template updates**: when the user says `"Update your instructions"`, this specifically
  invokes the Setup agent's update mode, not arbitrary editing.

The canonical trigger table is in `AGENTS.md`:

| Action | Trigger phrase |
|--------|---------------|
| Update instructions | `"Update your instructions"` / `"Check for instruction updates"` / `"Sync instructions with the template"` |
| Force update check | `"Force check instruction updates"` |
| Restore backup | `"Restore instructions from backup"` |

The distinction between "add this convention" (direct §8 append) and "update from
template" (Setup agent invocation) is important — they are different operations with
different safety profiles.

**Xanadassistant status**: no equivalent protocol exists. The `lifecycle-planning.agent.md`
has a "Trigger phrases" section but it covers lifecycle operations (install, update,
repair), not instruction file self-editing. There is no canonical phrase that triggers
the xanad-assistant update flow from within a consumer workspace session.

---

### R5 — Progressive disclosure in skills

Skills explicitly follow a three-tier loading model:

| Tier | Token budget | Content |
|------|-------------|---------|
| Startup metadata | ~100 tokens | YAML frontmatter + one-line description |
| On-activation body | < 5000 tokens (≤ 400 lines) | Steps, rules, tables, examples |
| On-demand resources | Unbounded | `scripts/`, `references/`, `assets/` subdirs |

The YAML frontmatter carries the discovery-critical fields:

```yaml
---
name: agentic-workflows
description: Set up and manage GitHub Actions workflows that use Copilot coding agents for automated PR handling and issue resolution
compatibility: ">=3.2"
---
```

After the frontmatter the body follows the **When to use / When NOT to use / Prerequisites
/ Concepts / Steps** structure. "When NOT to use" is as important as "When to use" — it
prevents the skill from over-triggering when adjacent task descriptions are similar (e.g.,
"fix a failing workflow" should route to `fix-ci-failure`, not `agentic-workflows`).

CI checks from `ci.yml`:
```yaml
- name: Skills have valid SKILL.md
  # enforces: name, description fields present in frontmatter
- name: Skills document metadata note (advisory)
  # advisory: body-level metadata note present (non-blocking)
```

**Xanadassistant status**: `skills/lifecycle-audit/SKILL.md` (7 lines) has no YAML
frontmatter, no `name:` field, no structured body sections. It will not be discoverable
by the VS Code skill protocol. The CI `Skills have valid SKILL.md` check from the
template would fail for it.

---

### R6 — Living update protocol — plugin delivery model

All template assets are delivered at plugin install time via `${CLAUDE_PLUGIN_ROOT}/`.
The Setup agent reads from the local plugin path; no network fetch is needed at setup
time. This means setup is reproducible, fast, and works offline after install.

In contrast, xanadassistant's `--source github:owner/repo` does a network clone at
run time — slower, fallible under network conditions, and cache-dependent (though the
cache mitigates the repeated-fetch cost). The plugin model eliminates the runtime network
dependency entirely.

**Xanadassistant status**: network clone is mitigated by caching but not eliminated.
The plugin delivery model is not yet applicable to xanadassistant since it is not
packaged as a VS Code plugin.

---

### R7 — PDCA + test scope tiers baked into instructions

The instructions template defines four explicit test scope tiers:

| Tier | When to use |
|------|-------------|
| `PathTargeted` | Default during intermediate work |
| `AffectedSuite` | Shared helpers or broad contract surfaces |
| `FullSuite` | Only when selector emits `run_full_suite_at_completion: true` |
| `MergeGate` | Before merge, release, or final handoff |

This prevents the common failure mode of running the full test suite between every
intermediate step (slow, noisy) or never running it at a gate (risky).

**Xanadassistant status**: the `lifecycle-planning.agent.md` does not specify test scope
policy. The agent knows the test commands from repo memory but has no tier policy.

---

### R8 — Hook scripts as deterministic outcome guarantees

The key distinction: **hooks guarantee outcomes; instructions suggest behaviour**. A
`guard-destructive.sh` PreToolUse hook that actually blocks `rm -rf` and `git push --force`
is architecturally different from an instruction that says "be careful with destructive
commands." The instruction can be ignored under context pressure; the hook cannot.

**`guard-destructive.sh` implementation details:**
- Runs on `PreToolUse` for any `terminal`, `command`, `bash`, or `shell` tool (plus `create_and_run_task`)
- Parses `tool_input.command` (or `tool_input.task.command`) via Python to extract the actual shell command
- Checks against a JSON policy file (`guard-policy.json`) with deny-list patterns and caution-list patterns
- Returns `permissionDecision: "deny"` for hard-blocked patterns; `"ask"` for caution patterns; `"allow"` otherwise
- Falls back to `"ask"` if Python is unavailable rather than silently allowing

**`session-start.sh` implementation details:**
- Runs on `SessionStart`; drains stdin (required by hook protocol but unused)
- Gathers: OS/distro/arch, git branch+commit, project name+version from `package.json`/`pyproject.toml`/`Cargo.toml`
- Reads `HEARTBEAT.md` pulse state
- Builds specialist roster from `agents/routing-manifest.json` (or fallback defaults)
- Returns all context as `additionalContext` JSON field

**Hook config** — two locations kept in sync:
- `.github/hooks/copilot-hooks.json` — developer workspace (all-local mode)
- `hooks/hooks.json` — plugin component (delivered to consumers via plugin install)

The template wires all eight VS Code lifecycle events. The `xanad-workspace-mcp.py` stub
in xanadassistant's `hooks/scripts/` is a single Python file that exists but is not
wired to any lifecycle event and has no corresponding `copilot-hooks.json`.

**Xanadassistant status**: `.github/workflows/ci.yml` exists as a passive CI gate.
No active VS Code lifecycle hooks are wired. The `hooks/scripts/xanad-workspace-mcp.py`
stub exists but is unused.

---

## What they did wrong

### W1 — Over-engineered heartbeat / pulse system

The pulse system comprises six Python modules invoked on every PostToolUse hook call:

| Module | Responsibility |
|--------|---------------|
| `pulse_runtime.py` | Entry point; routes by trigger type; calls all others |
| `pulse_state.py` | JSONL event journal + state.json; session size heuristics; lock files |
| `pulse_routing.py` | Routing manifest loading; prompt pattern matching; confidence scoring |
| `pulse_intent.py` | Intent engine update; detects explicit heartbeat/retrospective prompts |
| `pulse_paths.py` | Extracts tool paths from PostToolUse events |
| `pulse_artifacts.py` | Pulse state artifact generation |

This is a mini-application executing on every tool call. `pulse.sh` alone requires:
Python detection with fallback (`python3` → `python`), file existence checks on
`pulse_runtime.py`, stdin capture, and a Python subprocess. Any import error, JSON
parse failure, or state file lock contention silently degrades or breaks the hook.

**The core concept is sound**: knowing whether a session is "small" (< 5 files, < 15 min)
or "large" (8+ files or 30+ min) and gating retrospective prompts accordingly is
genuinely useful for long-session quality. The failure is the implementation weight.

**A viable minimal version** for xanadassistant would be a single ~30-line shell script
that reads `git diff --name-only HEAD` line count and session start time from a temp
file, and emits a single line of `additionalContext` when the session is large. No
Python, no JSONL, no locks.

---

### W2 — routing-manifest.json is speculative infrastructure

`agents/routing-manifest.json` defines per-agent routing with confidence thresholds,
suppress patterns, behavioral patterns, cooldowns, and prompt pattern regexes. This
re-implements something the VS Code agent framework should handle natively.

Problems:
- Must be kept in sync with agent frontmatter (two sources of truth for the same routing intent).
- Confidence thresholds are not documented as having any runtime effect in the VS Code agent protocol.
- The JSON file adds maintenance cost without a clear runtime guarantee.

The agent frontmatter `description` and `argument-hint` fields are the canonical
routing mechanism. Extra machinery on top creates false confidence that routing is
controlled precisely when it may not be.

---

### W3 — Multi-plugin-format fragmentation

Three plugin manifest formats are maintained in parallel:
- `plugin.json` — VS Code Copilot native (agents + skills only; no hooks/MCP)
- `.plugin/` — OpenPlugin format (`${PLUGIN_ROOT}` paths)
- `.claude-plugin/` — Claude format (`${CLAUDE_PLUGIN_ROOT}` paths)

The instructions explicitly note that `plugin.json` must NOT contain hooks or MCP
entries because VS Code has no plugin-root token to resolve executable paths. This
is a known footgun documented in the architecture notes.

Each format must stay in sync. When a new agent or skill is added, three manifests
must be updated. The `${CLAUDE_PLUGIN_ROOT}` path variable used in agent prose only
resolves in the Claude plugin context — not in VS Code native mode.

---

### W4 — Runtime state mixed with git-tracked knowledge

`.copilot/workspace/` mixes:
- **Git-tracked knowledge**: `knowledge/MEMORY.md`, `knowledge/SOUL.md`,
  `knowledge/USER.md`, `knowledge/RESEARCH.md`
- **Runtime state**: `runtime/.heartbeat-events.jsonl`, `runtime/state.json`,
  lockfiles (`.heartbeat-session.lock`, `state.json.lock`)

Runtime files should not live in the same directory tree as version-controlled
knowledge files. The lockfiles showing up in `git status` are constant noise.
The `.gitignore` partially handles this but requires careful maintenance.

---

### W5 — Always-on instruction file is still heavy

The consumer-facing `template/copilot-instructions.md` is 429 lines with §1–§14 all
loaded into every interaction. Sections include: Lean principles, PDCA cycle, test
scope policy, coding conventions, operating modes, waste catalogue, metrics, living
update protocol, subagent protocol, tool protocol, skill protocol, MCP protocol, and
workspace knowledge.

The §8 overflow rule says to extract to skills when sections approach their budget.
But the existing sections are already at scale — the file is nearly at half the
800-line CI hard limit with the template still in placeholder state. Consumer projects
that fill in all the project-specific sections will approach the limit quickly.

---

### W6 — Setup agent prose paths only resolve in one delivery mode

The Setup agent uses `${CLAUDE_PLUGIN_ROOT}/template/...` throughout. This path token
only resolves in the Claude plugin context. When the template is used in VS Code native
mode (without the Claude plugin), or when the agent is invoked directly without the
plugin resolver, these paths are unresolvable. The developer instructions acknowledge
this limitation but it remains an architectural constraint.

---

### W7 — MEMORY.md / SOUL.md / USER.md separation adds cognitive overhead

Three separate git-tracked knowledge files with distinct routing rules (MEMORY.md for
project conventions, SOUL.md for reasoning heuristics, USER.md for observed user
behaviour) require the agent to evaluate the routing decision tree before every memory
write. The tree has 6 rows. This is correct and principled but adds friction on every
memory operation. A simpler single-file approach with topic sections would have lower
cognitive overhead at the cost of less precise scoping.

---

## What xanadassistant does better

### X1 — Machine-readable lifecycle protocol

`plan`, `inspect`, `check` all emit structured JSON. State is deterministic and
testable. The copilot-instructions-template's setup is entirely agent-prose-driven;
there is no equivalent of `plan repair --json` that can be asserted against in a test.

This means xanadassistant's lifecycle logic is **verifiable** — 124 tests cover the
engine, schema contracts, convergence, migration, and freshness. The template's
lifecycle logic lives in agent prose that cannot be unit-tested.

---

### X2 — Lockfile as authoritative installed state

`xanad-assistant-lock.json` is schema-validated, hash-verified, with migration coverage
for pre-0.1.0 shapes. The template determines installed state by reading and parsing the
prose instructions file (checking for `{{}}` tokens, version markers in comments).
That is content heuristics, not structured state — fragile under any edit that changes
those markers.

---

### X3 — Single lifecycle engine for all four modes

`setup`, `update`, `repair`, `factory-restore` all go through the same
`build_execution_result → build_plan_result → execute_apply_plan` pipeline. The template
has separate agent procedure sections for each mode that can diverge independently.

---

### X4 — CI-enforced manifest and catalog freshness

`check_manifest_freshness.py` in CI fails if `install-manifest.json` or `catalog.json`
are stale relative to their source inputs. The template's CI enforces LOC budgets and
token presence but not semantic artifact freshness.

---

### X5 — Schema contracts with test coverage

`xanad-assistant-lock.schema.json`, `install-manifest.schema.json`,
`install-policy.schema.json` are JSON Schema documents with dedicated validation tests
(`test_manifest_schema_contract.py`, `test_metadata_contracts.py`). The template has no
equivalent schema contracts for its JSON artifacts (`workspace-index.json`,
`routing-manifest.json`).

---

## What xanadassistant should adopt

### A1 — CI-enforced LOC budget on the instructions template

Add a CI check to `ci.yml` that fails if `template/copilot-instructions.md` exceeds a
line limit. Current size: 6 lines. Proposed hard limit: 150 lines (lean — xanadassistant
has fewer concerns than a full project template; 150 lines is about 3 sections at the
same size density as the template's standard sections).

**Proposed CI step** (drop into `.github/workflows/ci.yml`):

```yaml
- name: Instructions template within attention budget
  run: |
    FILE="template/copilot-instructions.md"
    if [[ -f "$FILE" ]]; then
      lines=$(wc -l < "$FILE")
      if [[ $lines -gt 150 ]]; then
        echo "❌ $FILE is $lines lines (budget: 150)"
        echo "   Extract detail into skills/ or agents/ and reference from here."
        exit 1
      fi
      echo "✅ $FILE is $lines lines (within 150-line budget)"
    fi
```

A per-section check (like the template's `validate-attention-budget.sh`) is premature
until section numbering (A2) is added. The simple total-lines gate is sufficient for
now; add per-section limits when sections are defined.

---

### A2 — Section numbering for precise cross-referencing

Add §-style anchors to `template/copilot-instructions.md` sections. The `lifecycle-planning.agent.md`
and future skills can then cross-reference with "see §3" rather than prose section names
that break under edits.

**Proposed minimal sections** for xanadassistant's consumer instructions file:

| § | Section |
|---|---------|
| §1 | Identity and Role |
| §2 | Lifecycle Operations (`setup`, `update`, `repair`, `factory-restore`) |
| §3 | Installed State (lockfile path, `inspect` output format) |
| §4 | Operating Constraints (what the agent may/must not do) |
| §5 | Project-Specific Overrides (consumer-filled) |

CI enforcement: once section numbering is in place, add the template's §-prefix check
to confirm all sections are present:
```bash
for section in 1 2 3 4 5; do
  grep -q "^## §$section —" template/copilot-instructions.md \
    || { echo "❌ Missing §$section"; exit 1; }
done
```

---

### A3 — Explicit living update protocol

Add a short §4 rule to `template/copilot-instructions.md` defining when the file may
be self-edited and what the canonical trigger phrases are.

**Proposed §4 text**:

```markdown
## §4 — Operating Constraints

- **Never delete** existing rules without explicit user instruction.
- **Additive by default** — append to sections; do not restructure.
- **Flag before writing** — describe the change, wait for confirmation before editing §1–§3.

### Self-update triggers

| Trigger phrase | Action |
|---------------|--------|
| `"Add this to your instructions"` / `"Remember this for next time"` | Append a convention to §5 |
| `"Update your instructions"` / `"Check for instruction updates"` | Run `xanad-assistant.py update` to pull latest template |
| `"Restore instructions from backup"` | Run `xanad-assistant.py repair` |
```

The key invariant: "add a project convention" (direct §5 append, low safety overhead)
is distinct from "pull a new version of the template" (lifecycle engine invocation,
potentially rewrites multiple files). Conflating them is a safety hazard.

---

### A4 — Progressive disclosure discipline in skills

Document the "metadata cheap, body on-demand" contract explicitly in
`skills/lifecycle-audit/SKILL.md` and any future pack skills.

**Proposed rework of `skills/lifecycle-audit/SKILL.md`**:

```markdown
---
name: lifecycle-audit
description: Review xanad-assistant workspace lifecycle state before proposing install, update, repair, or restore operations
---

# Lifecycle Audit

> Skill metadata: version "1.0"; license MIT; tags [xanad-assistant, lifecycle, inspect, repair]; recommended tools [codebase, runCommands].

## When to use

- Before proposing any install, update, repair, or factory-restore operation
- When a workspace's installed-state lockfile is stale or suspect

## When NOT to use

- During an already-in-progress lifecycle operation
- When the user explicitly says to skip inspection

## Steps

1. Run `python3 xanad-assistant.py inspect --json` and verify `installState` is valid.
2. Run `python3 xanad-assistant.py check --json` and inspect `repairReasons`.
3. If `repairReasons` is non-empty or `needsMigration` is true, surface findings before planning.
4. Prefer `plan` output over ad-hoc file edits.
5. Keep `ownership` distinctions explicit — managed files vs skipped surfaces.
```

The `name` + `description` frontmatter fields make this discoverable by the VS Code
skill protocol. The body structure (When to use, When NOT to use, Steps) matches the
template's validated pattern and will pass the CI `Skills have valid SKILL.md` check.

---

### A5 — A minimal SessionStart hook

Wire a `session-start.sh` as a VS Code `SessionStart` hook. The template's
`session-start.sh` collects ~120 lines of OS, runtime, project, and heartbeat context
on each session start and injects it as `additionalContext`. For xanadassistant the
equivalent is much simpler:

```bash
#!/usr/bin/env bash
# session-start.sh — inject xanad-assistant install state into each session
set -euo pipefail
cat > /dev/null  # drain stdin (hook protocol requirement)

WORKSPACE="$(pwd)"
LOCKFILE="$WORKSPACE/.github/xanad-assistant-lock.json"

if [[ -f "$LOCKFILE" ]]; then
  INSTALL_STATE=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print('installed — version:', d.get('package', {}).get('version', 'unknown'))
print('profile:', d.get('profile', 'none'))
print('packs:', d.get('selectedPacks', []))
needs_migration = not all(k in d for k in ('schemaVersion','package','manifest','timestamps','selectedPacks','files'))
if needs_migration: print('WARNING: lockfile needs migration — run: xanad-assistant.py repair')
" "$LOCKFILE" 2>/dev/null || echo "lockfile present but unreadable")
else
  INSTALL_STATE="not installed"
fi

python3 -c "
import json, sys
print(json.dumps({'hookSpecificOutput': {'additionalContext':
  'xanad-assistant state: ' + sys.argv[1]}}))
" "$INSTALL_STATE"
```

The required `copilot-hooks.json` wiring:

```json
{
  "hooks": [
    {
      "event": "SessionStart",
      "script": ".github/hooks/scripts/session-start.sh"
    }
  ]
}
```

This eliminates the "what's installed in this workspace?" overhead from the first
message of every session. It also surfaces `needsMigration` warnings immediately
rather than waiting for the user to run `inspect`.

---

### A6 — Git-tracked MEMORY.md alongside /memories/repo/

`/memories/repo/` is machine-local (lives in VS Code's `workspaceStorage/`), has a
28-day auto-expiry when GitHub-hosted Copilot Memory is enabled, and is not git-tracked.
It works well as an in-flight inbox for facts discovered during a session but is lost
on machine change, environment reset, or expiry.

**What the template does**: `knowledge/MEMORY.md` (in `.copilot/workspace/knowledge/`)
is git-tracked, uses a structured table schema with Date and Source columns, and is
explicitly scoped to "architectural decisions, error patterns, team conventions, gotchas
not yet in the instructions file." The `MEMORY-GUIDE.md` routing decision tree determines
which store each fact goes to.

**Proposed routing for xanadassistant** (simplified, single-file):

| Fact type | Target |
|-----------|--------|
| Current session context, in-progress notes | `/memories/session/` |
| Personal cross-repo preferences | `/memories/` user files |
| In-flight repo facts, not yet validated | `/memories/repo/` (inbox) |
| Validated project conventions, architecture decisions | `docs/memory.md` (git-tracked) |

**Proposed `docs/memory.md` schema**:

```markdown
## Architecture Decisions

| Date | Decision | Rationale | Source |
|------|----------|-----------|--------|
| 2026-05-07 | Lockfile as installed-state authority | Content heuristics ({{}} tokens) are fragile | contracts/package-state-model.md |

## Known Gotchas

| Date | Pattern | Context | Source |
|------|---------|---------|--------|

## Conventions

| Date | Convention | Applies to | Source |
|------|-----------|-----------|--------|
```

The promotion rule from the template is worth adopting: use `/memories/repo/` as the
inbox while a task is in flight. Promote validated, durable facts to `docs/memory.md`
at task completion. This keeps the inbox clean without losing knowledge.

---

## Deferred / out of scope

The following template features are deliberate non-goals for xanadassistant:

| Feature | Reason |
|---------|--------|
| Pulse / heartbeat session tracking | Over-engineered for single-developer use; the concept (session-size retrospectives) can be revisited simply |
| `routing-manifest.json` | VS Code agent routing is handled by agent frontmatter; extra JSON adds sync cost |
| Multi-plugin-format manifests | Xanadassistant is not a VS Code plugin; no plugin manifest needed until packaging |
| SOUL.md / USER.md separation | Premature; fold into a single `docs/memory.md` until complexity justifies splitting |
| Starter kits | Relevant only after xanadassistant ships as a plugin with stack-specific content |
