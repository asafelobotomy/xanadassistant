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


class XanadWorkspaceMcpCoverageBTests(unittest.TestCase):
    """Coverage-targeted tests for uncovered paths in xanadWorkspaceMcp.py (part B)."""

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

    def test_lifecycle_plan_setup_passes_fixed_mode(self):
        """lifecycle_plan_setup: always passes mode='setup' to run_lifecycle_command."""
        import json
        with patch.object(self.mod, "run_lifecycle_command", return_value={"status": "ok", "summary": "done"}) as mock_cmd:
            result = json.loads(self.mod.lifecycle_plan_setup(packageRoot=str(REPO_ROOT)))
        self.assertEqual("ok", result["status"])
        call_kwargs = mock_cmd.call_args[1]
        self.assertEqual("setup", call_kwargs.get("mode"))

    def test_show_key_commands_no_commands_in_file(self):
        """tool_workspace_show_key_commands line 202: instructions exist but no commands."""
        with self._with_workspace("# No key commands table here\n") as _ws:
            result = self.mod.tool_workspace_show_key_commands({})
        self.assertEqual("unavailable", result["status"])

    def test_run_tests_success(self):
        """tool_workspace_run_tests lines 213-220: valid setup → run_argv called."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "tests passed"}):
                result = self.mod.tool_workspace_run_tests({})
        self.assertEqual("ok", result["status"])

    def test_run_tests_full_scope(self):
        """tool_workspace_run_tests: scope=full → run_argv called without extra args."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.tool_workspace_run_tests({"scope": "full"})
        self.assertEqual("ok", result["status"])
        argv_arg = mock_argv.call_args[0][0]
        self.assertNotIn("--extra", argv_arg)

    def test_run_tests_no_command_in_instructions(self):
        """tool_workspace_run_tests: no 'Run tests' command → unavailable."""
        with self._with_workspace("## Key Commands\n\n| Task | Command |\n|---|---|\n| LOC gate | `python3 scripts/check_loc.py` |\n") as _ws:
            result = self.mod.tool_workspace_run_tests({})
        self.assertEqual("unavailable", result["status"])

    def test_run_tests_command_with_shell_metachar(self):
        """tool_workspace_run_tests line 218: command with shell metachar → unavailable."""
        with self._with_workspace("## Key Commands\n\n| Task | Command |\n|---|---|\n| Run tests | `python3 -m unittest; echo pwned` |\n") as _ws:
            result = self.mod.tool_workspace_run_tests({})
        self.assertEqual("unavailable", result["status"])

    def test_run_check_loc_success(self):
        """tool_workspace_run_check_loc lines 225-228: valid LOC gate → run_argv."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "loc pass"}):
                result = self.mod.tool_workspace_run_check_loc({})
        self.assertEqual("ok", result["status"])

    def test_validate_lockfile_success(self):
        """tool_workspace_validate_lockfile lines 236-240: lockfile has all required keys."""
        import json as _json
        lockfile = {
            "schemaVersion": "0.1.0", "package": {}, "manifest": {},
            "timestamps": {}, "files": [],
        }
        with self._with_workspace() as ws:
            (ws / ".github" / "xanadAssistant-lock.json").write_text(_json.dumps(lockfile), encoding="utf-8")
            result = self.mod.tool_workspace_validate_lockfile({})
        self.assertEqual("ok", result["status"])
        self.assertIn("lockfile", result)

    def test_validate_lockfile_missing_keys(self):
        """tool_workspace_validate_lockfile: lockfile missing keys → failed."""
        import json as _json
        with self._with_workspace() as ws:
            (ws / ".github" / "xanadAssistant-lock.json").write_text(
                _json.dumps({"schemaVersion": "0.1.0"}), encoding="utf-8",
            )
            result = self.mod.tool_workspace_validate_lockfile({})
        self.assertEqual("failed", result["status"])
        self.assertIn("missingKeys", result)

    def test_show_install_state_with_payload(self):
        """tool_workspace_show_install_state lines 242-250: ok result with payload."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            fake_result = {
                "status": "ok",
                "summary": "check done",
                "payload": {"result": {"installState": "installed", "drift": {}}},
            }
            with patch.object(self.mod, "run_lifecycle_command", return_value=fake_result):
                result = self.mod.tool_workspace_show_install_state({})
        self.assertEqual("ok", result["status"])
        self.assertEqual("installed", result.get("installState"))

    def test_show_install_state_no_payload(self):
        """tool_workspace_show_install_state: non-ok result → returned as-is."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            fake_result = {"status": "failed", "summary": "check failed"}
            with patch.object(self.mod, "run_lifecycle_command", return_value=fake_result):
                result = self.mod.tool_workspace_show_install_state({})
        self.assertEqual("failed", result["status"])

    def test_resolve_lifecycle_package_root_version_arg(self):
        """resolve_lifecycle_package_root line 81: version_arg → resolve_github_release path."""
        fake_path = Path("/fake/release/path")
        with patch.object(self.mod, "resolve_github_release", return_value=fake_path) as mock_gr:
            root, reason = self.mod.resolve_lifecycle_package_root(
                None, source_arg="github:owner/repo", version_arg="v1.0.0",
            )
        self.assertEqual(fake_path, root)
        self.assertIsNone(reason)
        mock_gr.assert_called_once()

    def test_lifecycle_apply_passes_answers_non_interactive_dry_run(self):
        """lifecycle_apply: answersPath/nonInteractive/dryRun forwarded to run_lifecycle_command."""
        import json
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            answers_file = f.name
        try:
            with patch.object(self.mod, "run_lifecycle_command", return_value={"status": "ok", "summary": "done"}) as mock_cmd:
                with self._with_workspace(self._KEY_COMMANDS_MD):
                    result = json.loads(self.mod.lifecycle_apply(
                        packageRoot=str(REPO_ROOT),
                        answersPath=answers_file,
                        nonInteractive=True,
                        dryRun=True,
                    ))
            call_kwargs = mock_cmd.call_args[1]
            self.assertEqual(answers_file, call_kwargs.get("answers_path"))
            self.assertTrue(call_kwargs.get("non_interactive"))
            self.assertTrue(call_kwargs.get("dry_run"))
        finally:
            import os as _os
            _os.unlink(answers_file)

    def test_run_lifecycle_command_workspace_invalid(self):
        """run_lifecycle_command line 175: workspace invalid → unavailable."""
        import tempfile as _tmp
        with _tmp.TemporaryDirectory() as tmp:
            orig = self.mod.WORKSPACE_ROOT
            self.mod.WORKSPACE_ROOT = Path(tmp) / "no_github_here"
            try:
                result = self.mod.run_lifecycle_command("inspect", package_root_arg=str(REPO_ROOT))
            finally:
                self.mod.WORKSPACE_ROOT = orig
        self.assertEqual("unavailable", result["status"])

    def test_run_lifecycle_command_bad_package_root(self):
        """run_lifecycle_command line 178: bad package_root → unavailable."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            result = self.mod.run_lifecycle_command("inspect", package_root_arg="/nonexistent_path_xyz")
        self.assertEqual("unavailable", result["status"])

    def test_run_lifecycle_command_no_cli_in_package_root(self):
        """run_lifecycle_command line 181: package_root with no CLI script → unavailable."""
        with tempfile.TemporaryDirectory() as tmp:
            with self._with_workspace(self._KEY_COMMANDS_MD):
                result = self.mod.run_lifecycle_command("inspect", package_root_arg=tmp)
        self.assertEqual("unavailable", result["status"])
        self.assertIn("CLI", result["summary"])

    def test_run_lifecycle_command_valid_answers_path(self):
        """run_lifecycle_command line 189: valid answers_path → --answers appended."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            answers_file = f.name
        try:
            with self._with_workspace(self._KEY_COMMANDS_MD):
                with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                    result = self.mod.run_lifecycle_command(
                        "apply", package_root_arg=str(REPO_ROOT), answers_path=answers_file,
                    )
            argv_arg = mock_argv.call_args[0][0]
            self.assertIn("--answers", argv_arg)
            self.assertIn(answers_file, argv_arg)
        finally:
            import os as _os
            _os.unlink(answers_file)

    def test_run_check_loc_no_loc_command(self):
        """tool_workspace_run_check_loc line 227: no LOC gate command → unavailable."""
        with self._with_workspace("## Key Commands\n\n| Task | Command |\n|---|---|\n| Run tests | `python3 -m unittest` |\n"):
            result = self.mod.tool_workspace_run_check_loc({})
        self.assertEqual("unavailable", result["status"])
        self.assertIn("LOC gate", result["summary"])

    def test_validate_lockfile_no_workspace(self):
        """tool_workspace_validate_lockfile: workspace invalid → unavailable."""
        orig = self.mod.WORKSPACE_ROOT
        self.mod.WORKSPACE_ROOT = Path("/nonexistent_workspace_xyz")
        try:
            result = self.mod.tool_workspace_validate_lockfile({})
        finally:
            self.mod.WORKSPACE_ROOT = orig
        self.assertEqual("unavailable", result["status"])

    def test_show_install_state_no_workspace(self):
        """tool_workspace_show_install_state line 244: workspace invalid → unavailable."""
        orig = self.mod.WORKSPACE_ROOT
        self.mod.WORKSPACE_ROOT = Path("/nonexistent_workspace_xyz")
        try:
            result = self.mod.tool_workspace_show_install_state({})
        finally:
            self.mod.WORKSPACE_ROOT = orig
        self.assertEqual("unavailable", result["status"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

if __name__ == "__main__":  # pragma: no cover
    unittest.main()
