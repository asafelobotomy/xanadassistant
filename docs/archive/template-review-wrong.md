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

`xanadAssistant-lock.json` is schema-validated, hash-verified, with migration coverage
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

`xanadAssistant-lock.schema.json`, `install-manifest.schema.json`,
`install-policy.schema.json` are JSON Schema documents with dedicated validation tests
(`test_manifest_schema_contract.py`, `test_metadata_contracts.py`). The template has no
equivalent schema contracts for its JSON artifacts (`workspace-index.json`,
`routing-manifest.json`).

---

