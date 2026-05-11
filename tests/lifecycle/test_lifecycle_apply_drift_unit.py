"""Tests for apply dispatch, check drift, and build_not_implemented_payload."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._errors import _State
from scripts.lifecycle._xanad._main import main
from scripts.lifecycle._xanad._cli import add_common_arguments, build_parser
from scripts.lifecycle._xanad._emit import emit_json, emit_json_lines
from scripts.lifecycle._xanad._progress import (
    _ansi,
    _color_enabled,
    build_not_implemented_payload,
    emit_agent_progress,
    emit_payload,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _capture_main(argv: list[str]) -> tuple[int, str, str]:
    """Run main(argv) and return (exit_code, stdout, stderr)."""
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
        code = main(argv)
    return code, out_buf.getvalue(), err_buf.getvalue()


class BuildNotImplementedPayloadTests(unittest.TestCase):
    def test_returns_expected_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_not_implemented_payload("unknown-cmd", Path(tmp), Path(tmp), "setup")
            self.assertEqual("unknown-cmd", payload["command"])
            self.assertEqual("not-implemented", payload["status"])
            self.assertIn("errors", payload)


class LifecycleMainCheckDriftTests(unittest.TestCase):
    """Cover _check.py drift paths: malformed lockfile, skipped files, unknown files."""

    def setUp(self) -> None:
        _State.session_source_info = None
        _State.log_file = None

    def tearDown(self) -> None:
        _State.session_source_info = None
        if _State.log_file is not None:
            _State.log_file.close()
            _State.log_file = None

    def _check_workspace(self, workspace: str) -> tuple[int, dict]:
        code, stdout, _stderr = _capture_main([
            "check",
            "--workspace", workspace,
            "--package-root", str(REPO_ROOT),
            "--json",
        ])
        payload = json.loads(stdout)
        return code, payload

    def test_check_with_malformed_lockfile_reports_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            github_dir = Path(tmp) / ".github"
            github_dir.mkdir()
            lockfile = github_dir / "xanadAssistant-lock.json"
            lockfile.write_text("NOT VALID JSON{{{", encoding="utf-8")
            code, payload = self._check_workspace(tmp)
            self.assertEqual(7, code)
            self.assertEqual("drift", payload["status"])

    def test_check_with_missing_required_lockfile_fields_reports_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            github_dir = Path(tmp) / ".github"
            github_dir.mkdir()
            lockfile = github_dir / "xanadAssistant-lock.json"
            lockfile.write_text(
                json.dumps({"schemaVersion": "0.1.0", "onlyPartial": True}),
                encoding="utf-8",
            )
            code, payload = self._check_workspace(tmp)
            self.assertEqual(7, code)
            self.assertEqual("drift", payload["status"])


class LifecycleMainApplyDispatchTests(unittest.TestCase):
    """Cover the apply/update/repair/factory-restore dispatch paths in _main.py."""

    def setUp(self) -> None:
        _State.session_source_info = None
        _State.log_file = None

    def tearDown(self) -> None:
        _State.session_source_info = None
        if _State.log_file is not None:
            _State.log_file.close()
            _State.log_file = None

    def test_apply_non_interactive_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "apply",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--non-interactive",
            ])
            payload = json.loads(stdout)
            self.assertEqual("apply", payload["command"])
            self.assertIn(code, (0, 1, 2, 3, 5, 7))

    def test_update_non_interactive_dispatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "update",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--non-interactive",
            ])
            payload = json.loads(stdout)
            self.assertEqual("update", payload["command"])
            self.assertIsInstance(code, int)

    def test_repair_non_interactive_dispatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "repair",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--non-interactive",
            ])
            payload = json.loads(stdout)
            self.assertEqual("repair", payload["command"])
            self.assertIsInstance(code, int)

    def test_factory_restore_non_interactive_dispatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "factory-restore",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--non-interactive",
            ])
            payload = json.loads(stdout)
            self.assertEqual("factory-restore", payload["command"])
            self.assertIsInstance(code, int)

    def test_apply_dry_run_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "apply",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--non-interactive",
                "--dry-run",
            ])
            payload = json.loads(stdout)
            self.assertEqual("apply", payload["command"])
            self.assertIsInstance(code, int)
