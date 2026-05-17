from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad import _memory_check


class MemoryCheckTests(unittest.TestCase):
    def test_memory_checks_enabled_respects_answers_flag_and_workspace_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            self.assertFalse(_memory_check._memory_checks_enabled(workspace, setup_answers={"mcp.enabled": False}))
            self.assertTrue(_memory_check._memory_checks_enabled(workspace, setup_answers={"hooks.enabled": True}))
            self.assertFalse(_memory_check._memory_checks_enabled(workspace, mcp_enabled=False))
            hook = workspace / ".github" / "mcp" / "scripts" / "memoryMcp.py"
            hook.parent.mkdir(parents=True)
            hook.write_text("# hook\n", encoding="utf-8")
            self.assertTrue(_memory_check._memory_checks_enabled(workspace))

    def test_check_memory_health_reports_missing_install_and_unregistered_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            warnings = _memory_check.check_memory_health(workspace, mcp_enabled=True)

        codes = {warning["code"] for warning in warnings}
        self.assertEqual(codes, {"memory_mcp_missing", "memory_mcp_unregistered", "memory_db_missing"})

    def test_check_memory_health_handles_malformed_mcp_json_and_corrupt_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            hook = workspace / ".github" / "mcp" / "scripts" / "memoryMcp.py"
            hook.parent.mkdir(parents=True)
            hook.write_text("# hook\n", encoding="utf-8")
            mcp_json = workspace / ".vscode" / "mcp.json"
            mcp_json.parent.mkdir(parents=True)
            mcp_json.write_text("{bad", encoding="utf-8")
            db_path = workspace / ".github" / "xanadAssistant" / "memory" / "memory.db"
            db_path.parent.mkdir(parents=True)
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE advisory_memory(id INTEGER)")
            conn.commit()
            conn.close()

            warnings = _memory_check.check_memory_health(workspace)

        codes = {warning["code"] for warning in warnings}
        self.assertIn("memory_mcp_unregistered", codes)
        self.assertIn("memory_db_schema_corrupt", codes)

    def test_check_memory_health_accepts_registered_server_and_complete_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            hook = workspace / ".github" / "mcp" / "scripts" / "memoryMcp.py"
            hook.parent.mkdir(parents=True)
            hook.write_text("# hook\n", encoding="utf-8")
            mcp_json = workspace / ".vscode" / "mcp.json"
            mcp_json.parent.mkdir(parents=True)
            mcp_json.write_text(json.dumps({"servers": {"memory": {}}}), encoding="utf-8")
            db_path = workspace / ".github" / "xanadAssistant" / "memory" / "memory.db"
            db_path.parent.mkdir(parents=True)
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE advisory_memory(id INTEGER)")
            conn.execute("CREATE TABLE rules(id INTEGER)")
            conn.execute("CREATE TABLE agent_diary(id INTEGER)")
            conn.execute("CREATE VIRTUAL TABLE agent_diary_fts USING fts5(content)")
            conn.commit()
            conn.close()

            warnings = _memory_check.check_memory_health(workspace)

        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()