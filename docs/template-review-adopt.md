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
