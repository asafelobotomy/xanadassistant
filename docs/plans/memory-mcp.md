# Memory MCP — Working Document

**Status**: Plan complete, implementation not started.
**Branch**: main
**Repo**: /mnt/SteamLibrary/git/xanadassistant

---

## Goal

Build a FastMCP-based Memory MCP server (`hooks/scripts/memoryMcp.py`) that gives agents persistent, scoped, SQLite-backed memory — both advisory (discovered facts) and rule-based (authoritative user directives).

---

## Design Decisions (confirmed)

| Decision | Value |
|---|---|
| Storage path | `.github/xanadAssistant/memory/memory.db` (relative to workspace root) |
| Branch scoping | `git -C <workspace_root> rev-parse --abbrev-ref HEAD` via subprocess |
| Advisory enforcement | Advisory only — not hard-blocked on contradicting a fact |
| Rules | Authoritative — agents MUST follow returned rules |
| Pattern | FastMCP (`@mcp.tool()`) — same as `sqliteMcp.py` |
| Workspace root | `WORKSPACE_ROOT` env var; raise `ValueError` if unset |

---

## Schema

```sql
CREATE TABLE IF NOT EXISTS advisory_memory (
    agent          TEXT NOT NULL,
    scope          TEXT NOT NULL,
    branch         TEXT NOT NULL DEFAULT '',
    key            TEXT NOT NULL,
    value          TEXT NOT NULL,
    confidence     REAL NOT NULL DEFAULT 1.0,
    source         TEXT NOT NULL DEFAULT 'agent-discovered',
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    expires_at     TEXT,
    valid_from     TEXT,           -- fact not applicable before this date
    valid_until    TEXT,           -- soft validity end (not a hard delete trigger)
    invalidated_at TEXT,           -- set by memory_invalidate; NULL = active
    PRIMARY KEY (agent, scope, branch, key)
);

CREATE TABLE IF NOT EXISTS rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT,
    scope       TEXT NOT NULL DEFAULT 'workspace',
    branch      TEXT,
    rule_type   TEXT NOT NULL,
    description TEXT NOT NULL,
    created_by  TEXT NOT NULL DEFAULT 'user',
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS agent_diary (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT NOT NULL,
    scope       TEXT NOT NULL DEFAULT 'workspace',
    branch      TEXT NOT NULL DEFAULT '',
    entry       TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '',   -- comma-separated
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```

---

## MemPalace Patterns — Extracted

> Source: MemPalace v3.3.5 (52.2k stars, active), prior research session 2026-04-09.
> Methodology: extract patterns that survived community audit; reject those that didn't.

### What we adopt

| MemPalace concept | Our adaptation | Rationale |
|---|---|---|
| Per-agent **wing + diary** | New `agent_diary` table — chronological log of agent decisions/actions, separate from the fact store | Diary entries are append-only and not keyed — distinct semantic from facts |
| **Validity windows** (`valid_from` / `valid_until`) | Add `valid_from TEXT` and `valid_until TEXT` to `advisory_memory` | More expressive than a single `expires_at`; allows "this fact applies to v2.x only" |
| **Soft invalidation** | New `memory_invalidate(agent, key)` tool — sets `invalidated_at`, row kept for audit; `memory_dump` skips invalidated rows | Audit trail preserved; hard delete (`memory_remove`) still available |
| **Structured wake-up ordering** | `memory_dump` returns in fixed order: rules first → recent facts (<24h) → older by confidence → shared facts last | Predictable token cost; most important context loaded first |
| **Cross-agent peek** | `memory_get` gains optional `include_agents: list[str]` param | Explicit, not ambient; agent must opt in to reading another agent's namespace |

### What we reject

| MemPalace feature | Reason |
|---|---|
| ChromaDB / vector search | Overkill for structured key-value agent facts; adds 300 MB dependency |
| AAAK compression | Lossy (−12.4pp on LongMemEval); not lossless as claimed |
| Palace spatial metaphor | Organises human maintenance, not agent retrieval — irrelevant to our use case |
| Per-message transcript sweep | Out of scope; we store structured facts, not raw conversation history |

### Schema additions from MemPalace

```sql
-- advisory_memory gains two new nullable columns:
--   valid_from   TEXT  — ISO-8601; fact is not applicable before this date
--   valid_until  TEXT  — ISO-8601; soft validity end (different from hard expires_at)
--   invalidated_at TEXT — set by memory_invalidate; NULL means active

-- New table: agent diary (append-only, no primary-key conflict)
CREATE TABLE IF NOT EXISTS agent_diary (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    agent      TEXT NOT NULL,
    scope      TEXT NOT NULL DEFAULT 'workspace',
    branch     TEXT NOT NULL DEFAULT '',
    entry      TEXT NOT NULL,
    tags       TEXT NOT NULL DEFAULT '',          -- comma-separated
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
```

### Tool count impact

Adds `memory_invalidate`, `diary_add`, `diary_get` → **12 tools total** (up from 9). Still well within the 400-line hard limit.

---

## Time MCP Integration

The `time` MCP (`hooks/scripts/timeMcp.py`) provides `current_time`, `elapsed`,
`convert_timezone`, and `format_duration`. The memory server does **not** call
it internally (server-to-server MCP calls are not possible in the stdio model).
Instead, time awareness is split across two layers:

### Server side — Python stdlib only
- `updated_at` and `created_at` are set by SQLite `DEFAULT (strftime(...,'now'))` — no MCP needed.
- `expires_at` is computed by the server when `ttl_days` is passed: `datetime.now(UTC) + timedelta(days=ttl_days)`. No time MCP round-trip at write time.
- `memory_prune` deletes rows where `expires_at < datetime('now')` (hard expiry via SQLite).

### Agent side — time MCP for reasoning
- `memory_dump` returns `updated_at` in every fact object so agents can reason about age.
- Agent instructions (Phase 3) tell agents: after calling `memory_dump`, call `mcp_time_elapsed(start=fact.updated_at)` for any fact they intend to act on.
- Facts older than **7 days** should be treated as potentially stale and re-verified before use.
- Facts with `expires_at` set should be checked against `current_time()` — if expired but not yet pruned, treat as invalid.

### Why not pass timestamp from agent at write time?
Possible (agent calls `current_time()` then passes it as `updated_at`), but rejected: adds a mandatory round-trip before every write, and the SQLite default is perfectly reliable for this use case. The agent only needs the timestamp at *read* time.

### Staleness summary

| Age (from `elapsed`) | Treatment |
|---|---|
| < 1 day | Fresh — use directly |
| 1–7 days | Usable — note age if acting on it |
| > 7 days | Potentially stale — re-verify before acting |
| Past `expires_at` | Invalid — discard and re-discover |

---

## 12 Tools

### Advisory memory

| Tool | Signature | Notes |
|---|---|---|
| `memory_set` | `(agent, key, value, scope='workspace', confidence=1.0, source='agent-discovered', ttl_days=None, valid_from=None, valid_until=None)` | Upsert into advisory_memory; computes `expires_at` from `ttl_days` via stdlib |
| `memory_get` | `(agent, key, scope='workspace', include_agents=None)` | Single lookup; falls back to `agent='shared'`; `include_agents` for explicit cross-agent peek |
| `memory_list` | `(agent, scope='workspace', include_shared=True)` | All active (non-invalidated) keys for agent+scope |
| `memory_remove` | `(agent, key, scope='workspace')` | Hard delete one entry |
| `memory_invalidate` | `(agent, key, scope='workspace')` | Soft-delete: sets `invalidated_at`; row kept for audit; excluded from dump/list |
| `memory_dump` | `(agent)` | Session wake-up: rules first → recent facts (<24h) → older by confidence → shared facts; each fact includes `updated_at`, `expires_at`, `valid_from`, `valid_until` |
| `memory_prune` | `(agent=None, scope=None, max_age_days=None)` | Hard-delete rows where `expires_at` is past, or `updated_at` older than `max_age_days` |

### Rules

| Tool | Signature | Notes |
|---|---|---|
| `rule_add` | `(description, rule_type, agent=None, scope='workspace', branch=None)` | Insert a rule |
| `rule_list` | `(agent=None, scope='workspace')` | List rules matching agent or global |
| `rule_remove` | `(rule_id)` | Delete rule by id |

### Agent diary (append-only)

| Tool | Signature | Notes |
|---|---|---|
| `diary_add` | `(agent, entry, scope='workspace', tags='')` | Append a chronological decision/action entry |
| `diary_get` | `(agent, scope='workspace', limit=20, tag=None)` | Retrieve recent diary entries, newest first |

**Allowlists** (validate on entry, raise `ValueError` if invalid):
- `scope`: `{'workspace', 'project', 'branch', 'session'}`
- `rule_type`: `{'never', 'always', 'prefer', 'avoid'}`
- `agent`: any non-empty alphanumeric+hyphen string OR `None`

---

## Phases

### Phase 0 — Interview Question (optional, lower priority)
- File: `scripts/lifecycle/_xanad/_interview_questions.py`
- Add `memory_gitignore` question to `personalisation_questions()`
- `batch='advanced'`, `default='yes'`, `required=False`
- Apply step: if yes, add `.github/xanadAssistant/memory/` to `.gitignore`

### Phase 1 — MCP Server (START HERE)
- File: `hooks/scripts/memoryMcp.py`
- ~300 lines, FastMCP, two tables, 9 tools
- Header docstring listing tools + security notes
- `_init_db(conn)` called on first `_get_conn()` call
- `_current_branch(workspace_root)` — subprocess, returns `''` on error
- `_get_workspace_root()` — reads `WORKSPACE_ROOT` env var
- `_get_conn()` — opens/creates DB, runs `_init_db`, returns connection

### Phase 2 — MCP Registration
- File: `template/vscode/mcp.json`
- Add `"memory"` server entry (not disabled) using uvx pattern
- After: regenerate manifest (`python3 scripts/generate.py`)

### Phase 3 — Agent Instructions
- Files: all consumer agents in `agents/`
- Each agent: add session-start `memory_dump` call + rule-following note + `memory_set` for discovered facts
- Agents: commit, debugger, deps, docs, explore, planner, researcher, review, cleaner

### Phase 4 — ciPreflight Skill Update
- File: `skills/ciPreflight/SKILL.md`
- After discovering CI commands, cache them: `memory_set(agent='shared', key='ci.commands', ...)`
- At start: check `memory_get(agent='shared', key='ci.commands')` before re-scanning

### Phase 5 — Tests
- File: `tests/hooks/test_memory_mcp.py` (new dir `tests/hooks/`)
- Classes: `MemorySetGetTests`, `MemoryBranchScopeTests` (mock `_current_branch`), `MemoryRulesTests`, `MemoryDumpTests`, `MemoryPruneTests`, `SecurityTests`
- Use `tempfile.mkdtemp()` for DB; patch `WORKSPACE_ROOT`

### Phase 6 — Manifest Regeneration + Full Suite
- `python3 scripts/generate.py`
- `python3 -m unittest discover -s tests -p 'test_*.py'`

---

## MCP Registration Entry (template)

```json
"memory": {
  "type": "stdio",
  "command": "uvx",
  "env": {
    "CLAUDE_TMPDIR": "${userHome}/.cache/uv",
    "TMPDIR": "${userHome}/.cache/uv",
    "WORKSPACE_ROOT": "${workspaceFolder}"
  },
  "args": [
    "--from", "mcp[cli]",
    "mcp", "run",
    "${workspaceFolder}/.github/hooks/scripts/memoryMcp.py"
  ]
}
```

---

## Open Questions / Refinements Needed

- [ ] Phase 3 wording: how prescriptive should agent instructions be?
  - Option A: always call `memory_dump` at start unconditionally
  - Option B: call only if memory MCP is connected (softer)
- [ ] Phase 0 priority: implement now or defer until Phase 1-6 are done?
- [x] `memory_dump` return format: JSON object `{facts: [...], rules: [...]}` — each fact includes `updated_at`, `expires_at`, `valid_from`, `valid_until`; ordered by wake-up priority (rules → recent → older → shared)
- [x] `memory_prune`: on-demand only; hard expiry (`expires_at`) handled by SQL predicate, not auto-called on connect
- [x] Time MCP integration: agent-side only — agents call `elapsed()` at read time; server uses Python stdlib for TTL computation
- [ ] Which agents get rule-following language vs just fact-recording? (all vs subset)
- [ ] `tests/hooks/` — new directory; check if `__init__.py` needed

---

## Key File References

- Pattern to follow: `hooks/scripts/sqliteMcp.py`
- Registration: `template/vscode/mcp.json`
- Consumer agents: `agents/` (8 files)
- Interview questions: `scripts/lifecycle/_xanad/_interview_questions.py`
- Full suite command: `python3 -m unittest discover -s tests -p 'test_*.py'`
- Manifest regen: `python3 scripts/generate.py`
