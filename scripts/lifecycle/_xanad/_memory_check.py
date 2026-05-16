"""Memory MCP health checks for lifecycle inspect/check."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_MEMORY_HOOK = ".github/hooks/scripts/memoryMcp.py"
_MEMORY_MCP_JSON = ".vscode/mcp.json"
_MEMORY_DB = ".github/xanadAssistant/memory/memory.db"
_REQUIRED_TABLES = frozenset({"advisory_memory", "rules", "agent_diary"})


def _memory_checks_enabled(
    workspace: Path,
    *,
    setup_answers: dict | None = None,
    mcp_enabled: bool | None = None,
) -> bool:
    if isinstance(setup_answers, dict):
        if setup_answers.get("hooks.enabled") is False or setup_answers.get("mcp.enabled") is False:
            return False
        if setup_answers.get("hooks.enabled") is True or setup_answers.get("mcp.enabled") is True:
            return True

    if mcp_enabled is False:
        return False
    if mcp_enabled is True:
        return True

    return any((workspace / rel_path).exists() for rel_path in (_MEMORY_HOOK, _MEMORY_MCP_JSON, _MEMORY_DB))


def check_memory_health(
    workspace: Path,
    *,
    setup_answers: dict | None = None,
    mcp_enabled: bool | None = None,
) -> list[dict]:
    """Return warning dicts for any memory MCP health issues found in *workspace*.

    Callers extend the ``collect_context`` warnings list with the returned value.
    """
    warnings: list[dict] = []

    if not _memory_checks_enabled(workspace, setup_answers=setup_answers, mcp_enabled=mcp_enabled):
        return warnings

    # 1. memoryMcp.py installed
    if not (workspace / _MEMORY_HOOK).exists():
        warnings.append({
            "code": "memory_mcp_missing",
            "message": (
                "memoryMcp.py is not installed. "
                "Run 'repair' or 'update' to install it."
            ),
            "details": {"path": _MEMORY_HOOK, "severity": "warning"},
        })

    # 2. "memory" server registered in .vscode/mcp.json
    mcp_path = workspace / _MEMORY_MCP_JSON
    if not mcp_path.exists():
        warnings.append({
            "code": "memory_mcp_unregistered",
            "message": (
                "'.vscode/mcp.json' is missing, so the 'memory' server cannot be registered. "
                "Run 'repair' or 'update' to restore it."
            ),
            "details": {"path": _MEMORY_MCP_JSON, "severity": "warning"},
        })
    else:
        try:
            mcp_config = json.loads(mcp_path.read_text(encoding="utf-8"))
            servers = mcp_config.get("servers", mcp_config.get("mcpServers", {}))
            if "memory" not in servers:
                warnings.append({
                    "code": "memory_mcp_unregistered",
                    "message": (
                        "'memory' server not registered in .vscode/mcp.json. "
                        "Run 'repair' or 'update' to register it."
                    ),
                    "details": {"path": _MEMORY_MCP_JSON, "severity": "warning"},
                })
        except (json.JSONDecodeError, OSError):
            # mcp.json unreadable/malformed — memory server cannot be registered
            warnings.append({
                "code": "memory_mcp_unregistered",
                "message": (
                    "'memory' server cannot be verified in .vscode/mcp.json "
                    "(file is malformed or unreadable). "
                    "Run 'repair' or 'update' to restore it."
                ),
                "details": {"path": _MEMORY_MCP_JSON, "severity": "warning"},
            })

    # 3. DB schema (missing DB = first-run warning; corrupt schema = error)
    db_path = workspace / _MEMORY_DB
    if not db_path.exists():
        warnings.append({
            "code": "memory_db_missing",
            "message": "Memory DB not yet initialised (first-run state is valid).",
            "details": {"path": _MEMORY_DB, "severity": "info"},
        })
        return warnings

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            fts_missing = False
            try:
                conn.execute("SELECT count(*) FROM agent_diary_fts LIMIT 0").fetchone()
            except sqlite3.OperationalError:
                fts_missing = True
        finally:
            conn.close()
        missing = _REQUIRED_TABLES - tables
        if missing or fts_missing:
            all_missing = sorted(missing) + (["agent_diary_fts"] if fts_missing else [])
            warnings.append({
                "code": "memory_db_schema_corrupt",
                "message": (
                    "Memory DB is missing required tables. "
                    "Run 'repair' to re-initialise the memory database."
                ),
                "details": {"missingTables": all_missing, "severity": "error"},
            })
    except sqlite3.DatabaseError as exc:
        warnings.append({
            "code": "memory_db_schema_corrupt",
            "message": (
                "Memory DB cannot be read. "
                "Run 'repair' to re-initialise the memory database."
            ),
            "details": {"error": str(exc), "severity": "error"},
        })

    return warnings
