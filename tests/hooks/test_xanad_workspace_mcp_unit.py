"""Unit tests for xanadWorkspaceMcp.py utility and protocol functions."""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks" / "scripts"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    """Load a hook module from HOOKS_DIR by filename stem."""
    path = HOOKS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_hyphen(filename: str):
    """Load a hook module with a hyphen in its filename."""
    path = HOOKS_DIR / filename
    mod_name = filename.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class XanadWorkspaceMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Need to add hooks/scripts to sys.path so the module can import _xanad_mcp_source
        if str(HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_DIR))
        cls.mod = _load_hyphen("xanadWorkspaceMcp.py")

    def test_reject_shell_metacharacters_clean(self):
        result = self.mod.reject_shell_metacharacters("python3 -m unittest")
        self.assertIsNone(result)

    def test_reject_shell_metacharacters_pipe(self):
        result = self.mod.reject_shell_metacharacters("ls | grep foo")
        self.assertIsNotNone(result)
        self.assertIn("|", result)

    def test_reject_shell_metacharacters_semicolon(self):
        result = self.mod.reject_shell_metacharacters("echo hi; rm -rf /")
        self.assertIsNotNone(result)

    def test_reject_shell_metacharacters_subshell(self):
        result = self.mod.reject_shell_metacharacters("echo $(whoami)")
        self.assertIsNotNone(result)

    def test_tail_text_short(self):
        result = self.mod.tail_text("line1\nline2\nline3")
        self.assertEqual("line1\nline2\nline3", result)

    def test_tail_text_empty(self):
        result = self.mod.tail_text("")
        self.assertIsNone(result)

    def test_tail_text_truncated_max_lines(self):
        text = "\n".join(f"line{i}" for i in range(100))
        result = self.mod.tail_text(text, max_lines=5)
        self.assertIsNotNone(result)
        lines = result.splitlines()
        self.assertLessEqual(len(lines), 5)

    def test_tail_text_truncated_max_chars(self):
        long_line = "x" * 5000
        result = self.mod.tail_text(long_line, max_chars=100)
        self.assertIsNotNone(result)
        self.assertLessEqual(len(result), 100)

    def test_build_tool_result_minimal(self):
        r = self.mod.build_tool_result(status="ok", summary="all good")
        self.assertEqual("ok", r["status"])
        self.assertEqual("all good", r["summary"])

    def test_build_tool_result_with_command_and_exit_code(self):
        r = self.mod.build_tool_result(
            status="ok", summary="done", command="python3 test.py", exit_code=0,
        )
        self.assertEqual("python3 test.py", r["command"])
        self.assertEqual(0, r["exitCode"])

    def test_build_tool_result_stdout_tail(self):
        r = self.mod.build_tool_result(status="ok", summary="done", stdout="hello world")
        self.assertIn("stdoutTail", r)
        self.assertIn("hello world", r["stdoutTail"])

    def test_build_tool_result_empty_stdout_omitted(self):
        r = self.mod.build_tool_result(status="ok", summary="done", stdout="")
        self.assertNotIn("stdoutTail", r)

    def test_build_unavailable_result(self):
        r = self.mod.build_unavailable_result("not ready", extra="value")
        self.assertEqual("unavailable", r["status"])
        self.assertEqual("not ready", r["summary"])
        self.assertEqual("value", r["extra"])

    def test_parse_json_payload_valid(self):
        result = self.mod._parse_json_payload('{"status": "ok"}')
        self.assertEqual({"status": "ok"}, result)

    def test_parse_json_payload_empty(self):
        result = self.mod._parse_json_payload("")
        self.assertIsNone(result)

    def test_parse_json_payload_invalid_json(self):
        result = self.mod._parse_json_payload("not json {{{")
        self.assertIsNone(result)

    def test_parse_json_payload_non_dict(self):
        result = self.mod._parse_json_payload("[1, 2, 3]")
        self.assertIsNone(result)

    def test_parse_key_commands_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# No key commands here\n")
            fpath = Path(f.name)
        try:
            result = self.mod.parse_key_commands(fpath)
            self.assertEqual([], result)
        finally:
            fpath.unlink(missing_ok=True)

    def test_parse_key_commands_missing_file(self):
        result = self.mod.parse_key_commands(Path("/nonexistent_path/file.md"))
        self.assertEqual([], result)

    def test_parse_key_commands_with_table(self):
        content = "## Key Commands\n\n| Task | Command |\n|------|------|\n| Run tests | python3 -m unittest |\n\n## Other\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            fpath = Path(f.name)
        try:
            result = self.mod.parse_key_commands(fpath)
            self.assertEqual(1, len(result))
            self.assertEqual("Run tests", result[0]["label"])
            self.assertEqual("python3 -m unittest", result[0]["command"])
        finally:
            fpath.unlink(missing_ok=True)

    def test_read_lockfile_missing(self):
        # Override WORKSPACE_LOCKFILE_PATH to a nonexistent file
        orig = self.mod.WORKSPACE_LOCKFILE_PATH
        self.mod.WORKSPACE_LOCKFILE_PATH = Path("/nonexistent/xanadAssistant-lock.json")
        try:
            result = self.mod.read_lockfile()
            self.assertIsNone(result)
        finally:
            self.mod.WORKSPACE_LOCKFILE_PATH = orig

    def test_read_lockfile_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json{{{")
            fpath = Path(f.name)
        orig = self.mod.WORKSPACE_LOCKFILE_PATH
        self.mod.WORKSPACE_LOCKFILE_PATH = fpath
        try:
            result = self.mod.read_lockfile()
            self.assertIsNone(result)
        finally:
            self.mod.WORKSPACE_LOCKFILE_PATH = orig
            fpath.unlink(missing_ok=True)

    def test_workspace_root_valid_when_github_exists(self):
        # The installed workspace (REPO_ROOT) has a .github dir
        orig = self.mod.WORKSPACE_ROOT
        self.mod.WORKSPACE_ROOT = REPO_ROOT
        try:
            result = self.mod.workspace_root_valid()
            self.assertTrue(result)
        finally:
            self.mod.WORKSPACE_ROOT = orig

    def test_workspace_root_invalid_without_github(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = self.mod.WORKSPACE_ROOT
            self.mod.WORKSPACE_ROOT = Path(tmp)
            try:
                result = self.mod.workspace_root_valid()
                self.assertFalse(result)
            finally:
                self.mod.WORKSPACE_ROOT = orig

    def test_resolve_lifecycle_cli_found(self):
        cli, reason = self.mod.resolve_lifecycle_cli(REPO_ROOT)
        self.assertIsNotNone(cli)
        self.assertIsNone(reason)

    def test_resolve_lifecycle_cli_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            cli, reason = self.mod.resolve_lifecycle_cli(Path(tmp))
        self.assertIsNone(cli)
        self.assertIsNotNone(reason)

    def test_fastmcp_instance(self):
        from mcp.server.fastmcp import FastMCP
        self.assertIsInstance(self.mod.mcp, FastMCP)

    def test_fastmcp_tool_count(self):
        tools = self.mod.mcp._tool_manager._tools
        self.assertEqual(13, len(tools))

    def test_fastmcp_workspace_tool_names(self):
        tools = self.mod.mcp._tool_manager._tools
        for name in ("workspace_show_key_commands", "workspace_run_tests", "workspace_run_check_loc", "workspace_validate_lockfile", "workspace_show_install_state"):
            self.assertIn(name, tools)

    def test_fastmcp_lifecycle_tool_names(self):
        tools = self.mod.mcp._tool_manager._tools
        for name in ("lifecycle_inspect", "lifecycle_check", "lifecycle_interview", "lifecycle_plan_setup", "lifecycle_apply", "lifecycle_update", "lifecycle_repair", "lifecycle_factory_restore"):
            self.assertIn(name, tools)

    def test_fastmcp_workspace_show_key_commands_returns_json(self):
        import json
        result = json.loads(self.mod.workspace_show_key_commands())
        self.assertIn("status", result)

    def test_fastmcp_lifecycle_interview_invalid_mode_returns_unavailable(self):
        import json
        result = json.loads(self.mod.lifecycle_interview(mode="not-valid"))
        self.assertEqual("unavailable", result["status"])



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
