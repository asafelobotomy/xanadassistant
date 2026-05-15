"""Unit tests for scripts/lifecycle/_xanad/_memory_check.py.

Covers all four warning codes in isolation, plus FTS table probe and
malformed mcp.json handling.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._memory_check import check_memory_health

_HOOK_PATH = ".github/hooks/scripts/memoryMcp.py"
_MCP_JSON_PATH = ".vscode/mcp.json"
_DB_PATH = ".github/xanadAssistant/memory/memory.db"


def _make_workspace(tmp: str) -> Path:
    return Path(tmp)


def _install_hook(ws: Path) -> None:
    p = ws / _HOOK_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# stub\n", encoding="utf-8")


def _write_mcp_json(ws: Path, servers: dict) -> None:
    p = ws / _MCP_JSON_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"servers": servers}), encoding="utf-8")


def _create_db(ws: Path, tables: list[str], include_fts: bool = True) -> None:
    db = ws / _DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    try:
        for t in tables:
            conn.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY)")
        if include_fts:
            conn.execute(
                "CREATE VIRTUAL TABLE agent_diary_fts "
                "USING fts5(id UNINDEXED, agent UNINDEXED, scope UNINDEXED, "
                "branch UNINDEXED, entry, tags)"
            )
        conn.commit()
    finally:
        conn.close()


class MemoryCheckHookMissingTests(unittest.TestCase):
    def test_hook_absent_emits_memory_mcp_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            warnings = check_memory_health(ws)
            codes = [w["code"] for w in warnings]
            self.assertIn("memory_mcp_missing", codes)

    def test_hook_present_no_memory_mcp_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            warnings = check_memory_health(ws)
            codes = [w["code"] for w in warnings]
            self.assertNotIn("memory_mcp_missing", codes)


class MemoryCheckMcpRegistrationTests(unittest.TestCase):
    def test_mcp_json_missing_memory_key_emits_unregistered(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            _write_mcp_json(ws, {"other-server": {}})
            warnings = check_memory_health(ws)
            codes = [w["code"] for w in warnings]
            self.assertIn("memory_mcp_unregistered", codes)

    def test_mcp_json_with_memory_key_no_unregistered(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            _write_mcp_json(ws, {"memory": {"command": "uvx"}})
            warnings = check_memory_health(ws)
            codes = [w["code"] for w in warnings]
            self.assertNotIn("memory_mcp_unregistered", codes)

    def test_mcp_json_absent_no_unregistered_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            # No mcp.json at all — memory_mcp_unregistered should not fire
            warnings = check_memory_health(ws)
            codes = [w["code"] for w in warnings]
            self.assertNotIn("memory_mcp_unregistered", codes)

    def test_malformed_mcp_json_emits_unregistered(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            p = ws / _MCP_JSON_PATH
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{not valid json}", encoding="utf-8")
            warnings = check_memory_health(ws)
            codes = [w["code"] for w in warnings]
            self.assertIn("memory_mcp_unregistered", codes)


class MemoryCheckDbTests(unittest.TestCase):
    def test_db_absent_emits_memory_db_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            _write_mcp_json(ws, {"memory": {}})
            warnings = check_memory_health(ws)
            codes = [w["code"] for w in warnings]
            self.assertIn("memory_db_missing", codes)

    def test_db_absent_early_return_no_schema_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            _write_mcp_json(ws, {"memory": {}})
            warnings = check_memory_health(ws)
            codes = [w["code"] for w in warnings]
            self.assertNotIn("memory_db_schema_corrupt", codes)

    def test_db_with_all_tables_no_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            _write_mcp_json(ws, {"memory": {}})
            _create_db(ws, ["advisory_memory", "rules", "agent_diary"], include_fts=True)
            warnings = check_memory_health(ws)
            codes = [w["code"] for w in warnings]
            self.assertNotIn("memory_db_schema_corrupt", codes)
            self.assertNotIn("memory_db_missing", codes)

    def test_db_missing_table_emits_schema_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            _write_mcp_json(ws, {"memory": {}})
            # Only create advisory_memory; missing rules and agent_diary
            _create_db(ws, ["advisory_memory"], include_fts=False)
            warnings = check_memory_health(ws)
            corrupt = [w for w in warnings if w["code"] == "memory_db_schema_corrupt"]
            self.assertTrue(corrupt)
            missing = corrupt[0]["details"]["missingTables"]
            self.assertIn("rules", missing)
            self.assertIn("agent_diary", missing)

    def test_db_missing_fts_table_emits_schema_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            _write_mcp_json(ws, {"memory": {}})
            # Create all required tables but NOT the FTS virtual table
            _create_db(ws, ["advisory_memory", "rules", "agent_diary"], include_fts=False)
            warnings = check_memory_health(ws)
            corrupt = [w for w in warnings if w["code"] == "memory_db_schema_corrupt"]
            self.assertTrue(corrupt)
            missing = corrupt[0]["details"]["missingTables"]
            self.assertIn("agent_diary_fts", missing)

    def test_db_corrupt_file_emits_schema_corrupt_with_error_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            _install_hook(ws)
            _write_mcp_json(ws, {"memory": {}})
            db = ws / _DB_PATH
            db.parent.mkdir(parents=True, exist_ok=True)
            db.write_bytes(b"this is not a sqlite database")
            warnings = check_memory_health(ws)
            corrupt = [w for w in warnings if w["code"] == "memory_db_schema_corrupt"]
            self.assertTrue(corrupt)
            self.assertIn("error", corrupt[0]["details"])


if __name__ == "__main__":
    unittest.main()
