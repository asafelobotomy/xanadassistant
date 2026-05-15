"""Unit tests for xanadWorkspaceMcp.py tool handlers."""
from __future__ import annotations

import importlib.util
import io
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


class XanadWorkspaceMcpToolTests(unittest.TestCase):
    """Tests for the high-level tool_workspace_* functions."""

    @classmethod
    def setUpClass(cls):
        if str(HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_DIR))
        cls.mod = _load_hyphen("xanadWorkspaceMcp.py")
        # Point workspace at REPO_ROOT (has .github, copilot-instructions.md, etc.)
        cls.orig_root = cls.mod.WORKSPACE_ROOT
        cls.orig_instructions = cls.mod.WORKSPACE_INSTRUCTIONS_PATH
        cls.orig_lockfile = cls.mod.WORKSPACE_LOCKFILE_PATH
        cls.mod.WORKSPACE_ROOT = REPO_ROOT
        cls.mod.WORKSPACE_INSTRUCTIONS_PATH = REPO_ROOT / ".github" / "copilot-instructions.md"
        cls.mod.WORKSPACE_LOCKFILE_PATH = REPO_ROOT / ".github" / "xanadAssistant-lock.json"

    @classmethod
    def tearDownClass(cls):
        cls.mod.WORKSPACE_ROOT = cls.orig_root
        cls.mod.WORKSPACE_INSTRUCTIONS_PATH = cls.orig_instructions
        cls.mod.WORKSPACE_LOCKFILE_PATH = cls.orig_lockfile

    def test_show_key_commands_finds_commands(self):
        result = self.mod.tool_workspace_show_key_commands({})
        self.assertIn(result["status"], ("ok", "unavailable"))

    def test_validate_lockfile_ok_or_unavailable(self):
        result = self.mod.tool_workspace_validate_lockfile({})
        self.assertIn(result["status"], ("ok", "failed", "unavailable"))

    def test_show_key_commands_invalid_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = self.mod.WORKSPACE_ROOT
            self.mod.WORKSPACE_ROOT = Path(tmp)
            try:
                result = self.mod.tool_workspace_show_key_commands({})
                self.assertEqual("unavailable", result["status"])
            finally:
                self.mod.WORKSPACE_ROOT = orig

    def test_validate_lockfile_no_github_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig_root = self.mod.WORKSPACE_ROOT
            orig_lock = self.mod.WORKSPACE_LOCKFILE_PATH
            self.mod.WORKSPACE_ROOT = Path(tmp)
            self.mod.WORKSPACE_LOCKFILE_PATH = Path(tmp) / ".github" / "xanadAssistant-lock.json"
            try:
                result = self.mod.tool_workspace_validate_lockfile({})
                self.assertEqual("unavailable", result["status"])
            finally:
                self.mod.WORKSPACE_ROOT = orig_root
                self.mod.WORKSPACE_LOCKFILE_PATH = orig_lock

    def test_run_tests_invalid_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = self.mod.WORKSPACE_ROOT
            self.mod.WORKSPACE_ROOT = Path(tmp)
            try:
                result = self.mod.tool_workspace_run_tests({})
                self.assertEqual("unavailable", result["status"])
            finally:
                self.mod.WORKSPACE_ROOT = orig

    def test_run_tests_invalid_extra_args(self):
        result = self.mod.tool_workspace_run_tests({"extraArgs": "not-a-list"})
        self.assertEqual("unavailable", result["status"])

    def test_run_tests_full_scope_with_extra_args_fails(self):
        result = self.mod.tool_workspace_run_tests(
            {"scope": "full", "extraArgs": ["--extra"]}
        )
        self.assertEqual("unavailable", result["status"])

    def test_run_check_loc_invalid_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = self.mod.WORKSPACE_ROOT
            self.mod.WORKSPACE_ROOT = Path(tmp)
            try:
                result = self.mod.tool_workspace_run_check_loc({})
                self.assertEqual("unavailable", result["status"])
            finally:
                self.mod.WORKSPACE_ROOT = orig

    def test_workspace_validate_lockfile_fastmcp_returns_json(self):
        import json
        result_json = self.mod.workspace_validate_lockfile()
        result = json.loads(result_json)
        self.assertIn(result["status"], ("ok", "failed", "unavailable"))

    def test_lifecycle_interview_invalid_mode_returns_unavailable(self):
        import json
        result_json = self.mod.lifecycle_interview(mode="invalid_mode")
        result = json.loads(result_json)
        self.assertEqual("unavailable", result["status"])



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
