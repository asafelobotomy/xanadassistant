"""Coverage gap tests for xanadWorkspaceMcp.py helper and tool functions."""
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


class XanadWorkspaceMcpCoverageATests(unittest.TestCase):
    """Coverage-targeted tests for uncovered paths in xanadWorkspaceMcp.py."""

    @classmethod
    def setUpClass(cls):
        if str(HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_DIR))
        cls.mod = _load_hyphen("xanadWorkspaceMcp.py")

    def _with_workspace(self, instructions_content: str | None = None):
        """Context manager: returns a TemporaryDirectory with .github created."""
        import contextlib
        @contextlib.contextmanager
        def _cm():
            with tempfile.TemporaryDirectory() as tmp:
                ws = Path(tmp)
                (ws / ".github").mkdir()
                orig_root = self.mod.WORKSPACE_ROOT
                orig_instructions = self.mod.WORKSPACE_INSTRUCTIONS_PATH
                orig_lockfile = self.mod.WORKSPACE_LOCKFILE_PATH
                self.mod.WORKSPACE_ROOT = ws
                self.mod.WORKSPACE_INSTRUCTIONS_PATH = ws / ".github" / "copilot-instructions.md"
                self.mod.WORKSPACE_LOCKFILE_PATH = ws / ".github" / "xanadAssistant-lock.json"
                if instructions_content is not None:
                    self.mod.WORKSPACE_INSTRUCTIONS_PATH.write_text(instructions_content, encoding="utf-8")
                try:
                    yield ws
                finally:
                    self.mod.WORKSPACE_ROOT = orig_root
                    self.mod.WORKSPACE_INSTRUCTIONS_PATH = orig_instructions
                    self.mod.WORKSPACE_LOCKFILE_PATH = orig_lockfile
        return _cm()

    _KEY_COMMANDS_MD = "## Key Commands\n\n| Task | Command |\n|---|---|\n| Run tests | `python3 -m unittest` |\n| LOC gate | `python3 scripts/check_loc.py` |\n"

    def test_resolve_key_command_found(self):
        """resolve_key_command line 42: returns command for label."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            result = self.mod.resolve_key_command("Run tests")
        self.assertEqual("python3 -m unittest", result)

    def test_resolve_key_command_not_found(self):
        """resolve_key_command line 42: returns None for unknown label."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            result = self.mod.resolve_key_command("No Such Label")
        self.assertIsNone(result)

    def test_resolve_lifecycle_package_root_explicit_valid(self):
        """resolve_lifecycle_package_root lines 51-62: explicit packageRoot that exists."""
        root, reason = self.mod.resolve_lifecycle_package_root(str(REPO_ROOT))
        self.assertEqual(REPO_ROOT, root)
        self.assertIsNone(reason)

    def test_resolve_lifecycle_package_root_explicit_empty_string(self):
        """resolve_lifecycle_package_root line 52: empty packageRoot string → error."""
        root, reason = self.mod.resolve_lifecycle_package_root("   ")
        self.assertIsNone(root)
        self.assertIn("packageRoot", reason)

    def test_resolve_lifecycle_package_root_from_lockfile_packageroot(self):
        """resolve_lifecycle_package_root lines 55-62: packageRoot from lockfile."""
        import json as _json
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / ".github").mkdir()
            lockfile = {"package": {"packageRoot": str(REPO_ROOT)}}
            lockfile_path = ws / ".github" / "xanadAssistant-lock.json"
            lockfile_path.write_text(_json.dumps(lockfile), encoding="utf-8")
            orig = self.mod.WORKSPACE_LOCKFILE_PATH
            self.mod.WORKSPACE_LOCKFILE_PATH = lockfile_path
            try:
                root, reason = self.mod.resolve_lifecycle_package_root(None)
            finally:
                self.mod.WORKSPACE_LOCKFILE_PATH = orig
        self.assertEqual(REPO_ROOT, root)
        self.assertIsNone(reason)

    def test_resolve_lifecycle_package_root_no_source_no_lockfile(self):
        """resolve_lifecycle_package_root line 75: no source → error."""
        orig = self.mod.WORKSPACE_LOCKFILE_PATH
        self.mod.WORKSPACE_LOCKFILE_PATH = Path("/nonexistent/lockfile.json")
        try:
            root, reason = self.mod.resolve_lifecycle_package_root(None)
        finally:
            self.mod.WORKSPACE_LOCKFILE_PATH = orig
        self.assertIsNone(root)
        self.assertIn("source", reason.lower())

    def test_resolve_lifecycle_package_root_source_from_lockfile(self):
        """resolve_lifecycle_package_root lines 66-74: source taken from lockfile."""
        import json as _json
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = {"package": {"source": "github:owner/no-such-repo"}}
            lockfile_path = Path(tmp) / "lock.json"
            lockfile_path.write_text(_json.dumps(lockfile), encoding="utf-8")
            orig = self.mod.WORKSPACE_LOCKFILE_PATH
            self.mod.WORKSPACE_LOCKFILE_PATH = lockfile_path
            try:
                root, reason = self.mod.resolve_lifecycle_package_root(None)
            finally:
                self.mod.WORKSPACE_LOCKFILE_PATH = orig
        # Should fail resolving (network error or no cache), not the "no source" error
        self.assertIsNone(root)
        self.assertIsNotNone(reason)

    def test_resolve_lifecycle_package_root_invalid_value_type(self):
        """resolve_lifecycle_package_root lines 77-78: non-string version → error."""
        root, reason = self.mod.resolve_lifecycle_package_root(
            None, source_arg="github:owner/repo", version_arg=123,
        )
        self.assertIsNone(root)
        self.assertIn("version", reason)

    def test_run_argv_success(self):
        """run_argv lines 124-138: subprocess returns 0 → ok status."""
        with patch.object(self.mod, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
            result = self.mod.run_argv(["/bin/echo", "test"])
        self.assertEqual("ok", result["status"])

    def test_run_argv_failure(self):
        """run_argv: subprocess returns nonzero → failed status."""
        with patch.object(self.mod, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=1, stdout="", stderr="error!")
            result = self.mod.run_argv(["/bin/false"])
        self.assertEqual("failed", result["status"])

    def test_run_argv_with_parse_payload_ok(self):
        """run_argv parse_payload=True: valid JSON payload → ok + payload key."""
        payload = '{"status": "ok", "command": "inspect"}'
        with patch.object(self.mod, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
            result = self.mod.run_argv(["/bin/echo"], parse_payload=True)
        self.assertEqual("ok", result["status"])
        self.assertIn("payload", result)

    def test_run_argv_with_parse_payload_error_in_payload(self):
        """run_argv parse_payload=True: payload status='error' → failed."""
        payload = '{"status": "error", "command": "check"}'
        with patch.object(self.mod, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
            result = self.mod.run_argv(["/bin/echo"], parse_payload=True)
        self.assertEqual("failed", result["status"])

    def test_run_lifecycle_command_success(self):
        """run_lifecycle_command lines 174-195: all guards pass → run_argv called."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.run_lifecycle_command("inspect", package_root_arg=str(REPO_ROOT))
        self.assertEqual("ok", result["status"])
        mock_argv.assert_called_once()

    def test_run_lifecycle_command_with_mode_as_flag(self):
        """run_lifecycle_command: mode and mode_as_flag extend argv."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), mode="setup", mode_as_flag=True)
        self.assertEqual("ok", result["status"])
        argv_arg = mock_argv.call_args[0][0]
        self.assertIn("--mode", argv_arg)
        self.assertIn("setup", argv_arg)

    def test_run_lifecycle_command_with_mode_not_flag(self):
        """run_lifecycle_command: mode without mode_as_flag → mode appended directly."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), mode="setup", mode_as_flag=False)
        argv_arg = mock_argv.call_args[0][0]
        self.assertIn("setup", argv_arg)
        self.assertNotIn("--mode", argv_arg)

    def test_run_lifecycle_command_bad_answers_path(self):
        """run_lifecycle_command: nonexistent answersPath → unavailable."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), answers_path="/nonexistent/answers.json")
        self.assertEqual("unavailable", result["status"])
        self.assertIn("answersPath", result["summary"])

    def test_run_lifecycle_command_non_interactive_true(self):
        """run_lifecycle_command: non_interactive=True → --non-interactive in argv."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), non_interactive=True)
        argv_arg = mock_argv.call_args[0][0]
        self.assertIn("--non-interactive", argv_arg)

    def test_run_lifecycle_command_non_interactive_bad_value(self):
        """run_lifecycle_command: non_interactive='yes' → unavailable."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), non_interactive="yes")
        self.assertEqual("unavailable", result["status"])
        self.assertIn("nonInteractive", result["summary"])

    def test_run_lifecycle_command_dry_run_true(self):
        """run_lifecycle_command: dry_run=True → --dry-run in argv."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), dry_run=True)
        argv_arg = mock_argv.call_args[0][0]
        self.assertIn("--dry-run", argv_arg)

    def test_lifecycle_interview_valid_mode_calls_run_lifecycle_command(self):
        """lifecycle_interview: valid mode → run_lifecycle_command called with mode_as_flag=True."""
        import json
        with patch.object(self.mod, "run_lifecycle_command", return_value={"status": "ok", "summary": "done"}) as mock_cmd:
            with self._with_workspace(self._KEY_COMMANDS_MD):
                result = json.loads(self.mod.lifecycle_interview(packageRoot=str(REPO_ROOT), mode="setup"))
        self.assertEqual("ok", result["status"])
        mock_cmd.assert_called_once()
        call_kwargs = mock_cmd.call_args[1]
        self.assertEqual("setup", call_kwargs.get("mode"))
        self.assertTrue(call_kwargs.get("mode_as_flag"))



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
