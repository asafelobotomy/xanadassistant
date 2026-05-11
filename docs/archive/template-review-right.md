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
the xanadAssistant update flow from within a consumer workspace session.

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

**Xanadassistant status**: `skills/lifecycleAudit/SKILL.md` (7 lines) has no YAML
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

The template wires all eight VS Code lifecycle events. The `xanadWorkspaceMcp.py` stub
in xanadassistant's `hooks/scripts/` is a single Python file that exists but is not
wired to any lifecycle event and has no corresponding `copilot-hooks.json`.

**Xanadassistant status**: `.github/workflows/ci.yml` exists as a passive CI gate.
No active VS Code lifecycle hooks are wired. The `hooks/scripts/xanadWorkspaceMcp.py`
stub exists but is unused.

---

