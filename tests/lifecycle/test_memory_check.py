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


class McpStructureAuditTests(unittest.TestCase):
    def _make_package_root(self, tmpdir: str, server_ids: list[str]) -> Path:
        package_root = Path(tmpdir) / "pkg"
        mcp_source = package_root / "template" / "vscode"
        mcp_source.mkdir(parents=True)
        servers = {sid: {"command": "node"} for sid in server_ids}
        (mcp_source / "mcp.json").write_text(json.dumps({"servers": servers}), encoding="utf-8")
        return package_root

    def _make_manifest(self, package_root: Path) -> dict:
        mcp_target = ".vscode/mcp.json"
        return {
            "managedFiles": [
                {
                    "id": mcp_target,
                    "target": mcp_target,
                    "source": "template/vscode/mcp.json",
                    "strategy": "merge-json-object",
                }
            ],
            "retiredMcpServers": [],
            "retiredFiles": [],
        }

    def test_no_warnings_when_mcp_servers_match_expected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "ws"
            workspace.mkdir()
            expected_ids = ["serverA", "serverB"]
            package_root = self._make_package_root(tmpdir, expected_ids)
            manifest = self._make_manifest(package_root)
            vscode = workspace / ".vscode"
            vscode.mkdir()
            (vscode / "mcp.json").write_text(
                json.dumps({"servers": {"serverA": {}, "serverB": {}}}), encoding="utf-8"
            )

            warnings = _memory_check.check_mcp_structure_health(workspace, package_root, manifest)

        self.assertEqual(warnings, [])

    def test_mcp_extra_server_warning_for_unexpected_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "ws"
            workspace.mkdir()
            package_root = self._make_package_root(tmpdir, ["expected"])
            manifest = self._make_manifest(package_root)
            vscode = workspace / ".vscode"
            vscode.mkdir()
            (vscode / "mcp.json").write_text(
                json.dumps({"servers": {"expected": {}, "surprise": {}}}), encoding="utf-8"
            )

            warnings = _memory_check.check_mcp_structure_health(workspace, package_root, manifest)

        codes = {w["code"] for w in warnings}
        self.assertIn("mcp-extra-server", codes)
        extra = next(w for w in warnings if w["code"] == "mcp-extra-server")
        self.assertIn("surprise", extra["details"]["serverIds"])

    def test_mcp_retired_server_warning_for_retired_server_still_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "ws"
            workspace.mkdir()
            package_root = self._make_package_root(tmpdir, ["current"])
            manifest = self._make_manifest(package_root)
            manifest["retiredMcpServers"] = [{"serverId": "legacy", "retiredIn": "0.4.0"}]
            vscode = workspace / ".vscode"
            vscode.mkdir()
            (vscode / "mcp.json").write_text(
                json.dumps({"servers": {"current": {}, "legacy": {}}}), encoding="utf-8"
            )

            warnings = _memory_check.check_mcp_structure_health(workspace, package_root, manifest)

        codes = {w["code"] for w in warnings}
        self.assertIn("mcp-retired-server", codes)
        retired_w = next(w for w in warnings if w["code"] == "mcp-retired-server")
        self.assertIn("legacy", retired_w["details"]["retiredServerIds"])


if __name__ == "__main__":
    unittest.main()
