"""Memory MCP health checks for lifecycle inspect/check."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_MEMORY_HOOK = ".github/mcp/scripts/memoryMcp.py"
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

    return any((workspace / rel_path).exists() for rel_path in (_MEMORY_HOOK, _MEMORY_DB))


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


def _load_mcp_server_map(path: Path) -> dict | None:
    """Return the parsed servers dict from an mcp.json file, or None on failure."""
    try:
        mcp_config = json.loads(path.read_text(encoding="utf-8"))
        return mcp_config.get("servers", mcp_config.get("mcpServers", {}))
    except (json.JSONDecodeError, OSError):
        return None


def _expected_manifest_mcp_server_ids(package_root: Path, manifest: dict | None) -> dict[str, set[str]]:
    """Return a mapping of relative MCP config path → set of expected server IDs.

    The expected IDs are derived by reading the managed MCP config source files
    (strategy ``merge-json-object``) from the package root.
    """
    if manifest is None:
        return {}
    result: dict[str, set[str]] = {}
    for entry in manifest.get("managedFiles", []):
        target = entry.get("target", "")
        if not (target.endswith("mcp.json") and entry.get("strategy") == "merge-json-object"):
            continue
        source = entry.get("source")
        if source is None:
            continue
        source_path = package_root / source
        server_map = _load_mcp_server_map(source_path)
        if server_map is not None:
            result[target] = set(server_map.keys())
    return result


def check_mcp_structure_health(
    workspace: Path,
    package_root: Path,
    manifest: dict | None,
) -> list[dict]:
    """Return warning dicts for MCP config files with unexpected or retired server IDs.

    Emits ``mcp-extra-server`` for server IDs present in the workspace but not
    expected by the manifest source, and ``mcp-retired-server`` for IDs that
    appear in ``manifest["retiredMcpServers"]``.
    """
    warnings: list[dict] = []
    expected_by_target = _expected_manifest_mcp_server_ids(package_root, manifest)
    if not expected_by_target:
        return warnings

    retired_ids = {entry["serverId"] for entry in (manifest or {}).get("retiredMcpServers", [])}

    for relative_target, expected_ids in sorted(expected_by_target.items()):
        config_path = workspace / relative_target
        if not config_path.exists():
            continue
        actual_map = _load_mcp_server_map(config_path)
        if actual_map is None:
            # malformed — already caught by memory registration checks
            continue
        actual_ids = set(actual_map.keys())
        extra_ids = sorted(actual_ids - expected_ids)
        if not extra_ids:
            continue
        retired_extra = [sid for sid in extra_ids if sid in retired_ids]
        non_retired_extra = [sid for sid in extra_ids if sid not in retired_ids]
        if retired_extra:
            warnings.append({
                "code": "mcp-retired-server",
                "message": (
                    f"'{relative_target}' contains retired server IDs that should be removed. "
                    "Run 'repair' or 'update' to clean up the MCP config."
                ),
                "details": {"path": relative_target, "retiredServerIds": retired_extra},
            })
        if non_retired_extra:
            warnings.append({
                "code": "mcp-extra-server",
                "message": (
                    f"'{relative_target}' contains server IDs not managed by this package. "
                    "Remove unrecognised servers or update the package to include them."
                ),
                "details": {"path": relative_target, "serverIds": non_retired_extra, "expectedServerIds": sorted(expected_ids)},
            })
    return warnings
