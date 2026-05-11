"""Direct unit tests for the lifecycle CLI — calls _main.main(argv) directly to cover
dispatch paths, emit functions, check/progress modules, and the _cli parser."""

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


class LifecycleMainInspectTests(unittest.TestCase):
    def setUp(self) -> None:
        _State.session_source_info = None
        _State.log_file = None

    def tearDown(self) -> None:
        _State.session_source_info = None
        if _State.log_file is not None:
            _State.log_file.close()
            _State.log_file = None

    def test_inspect_json_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "inspect",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
            ])
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertEqual("inspect", payload["command"])

    def test_inspect_json_lines_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "inspect",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json-lines",
            ])
            self.assertEqual(0, code)
            lines = [json.loads(line) for line in stdout.strip().splitlines()]
            self.assertGreater(len(lines), 0)
            commands = {e["command"] for e in lines}
            self.assertIn("inspect", commands)

    def test_inspect_agent_ui_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, _stderr = _capture_main([
                "inspect",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--ui", "agent",
            ])
            self.assertEqual(0, code)

    def test_json_and_json_lines_conflict_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "inspect",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--json-lines",
            ])
            self.assertEqual(2, code)
            payload = json.loads(stdout)
            self.assertEqual("error", payload["status"])

    def test_inspect_with_log_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "lifecycle.log"
            code, _stdout, _stderr = _capture_main([
                "inspect",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--log-file", str(log_path),
            ])
            self.assertEqual(0, code)
            self.assertTrue(log_path.exists())


class LifecycleMainCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        _State.session_source_info = None
        _State.log_file = None

    def tearDown(self) -> None:
        _State.session_source_info = None
        if _State.log_file is not None:
            _State.log_file.close()
            _State.log_file = None

    def test_check_json_returns_valid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "check",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
            ])
            self.assertIn(code, (0, 7))
            payload = json.loads(stdout)
            self.assertEqual("check", payload["command"])

    def test_check_json_lines_emits_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "check",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json-lines",
            ])
            self.assertIn(code, (0, 7))
            lines = [json.loads(line) for line in stdout.strip().splitlines()]
            self.assertGreater(len(lines), 0)

    def test_check_agent_ui_returns_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = _capture_main([
                "check",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--ui", "agent",
            ])
            self.assertIn(code, (0, 7))


class LifecycleMainInterviewTests(unittest.TestCase):
    def setUp(self) -> None:
        _State.session_source_info = None
        _State.log_file = None

    def tearDown(self) -> None:
        _State.session_source_info = None
        if _State.log_file is not None:
            _State.log_file.close()
            _State.log_file = None

    def test_interview_setup_mode_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "interview",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--mode", "setup",
            ])
            self.assertEqual(0, code)
            payload = json.loads(stdout)
            self.assertEqual("interview", payload["command"])

    def test_interview_agent_ui(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, stderr = _capture_main([
                "interview",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--mode", "setup",
                "--ui", "agent",
            ])
            self.assertEqual(0, code)

    def test_interview_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "interview",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json-lines",
                "--mode", "setup",
            ])
            self.assertEqual(0, code)
            lines = stdout.strip().splitlines()
            self.assertGreater(len(lines), 0)


class LifecycleMainPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        _State.session_source_info = None
        _State.log_file = None

    def tearDown(self) -> None:
        _State.session_source_info = None
        if _State.log_file is not None:
            _State.log_file.close()
            _State.log_file = None

    def test_plan_setup_non_interactive_returns_zero_or_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "plan", "setup",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--non-interactive",
            ])
            self.assertIn(code, (0, 1))
            payload = json.loads(stdout)
            self.assertEqual("plan", payload["command"])

    def test_plan_setup_with_plan_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan_out = Path(tmp) / "plan.json"
            code, stdout, _stderr = _capture_main([
                "plan", "setup",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--non-interactive",
                "--plan-out", str(plan_out),
            ])
            self.assertIn(code, (0, 1))
            if plan_out.exists():
                data = json.loads(plan_out.read_text(encoding="utf-8"))
                self.assertIsInstance(data, dict)

    def test_plan_json_lines_emits_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "plan", "setup",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json-lines",
                "--non-interactive",
            ])
            self.assertIn(code, (0, 1))
            lines = [json.loads(line) for line in stdout.strip().splitlines()]
            self.assertGreater(len(lines), 0)

    def test_plan_agent_ui(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _stdout, _stderr = _capture_main([
                "plan", "setup",
                "--workspace", tmp,
                "--package-root", str(REPO_ROOT),
                "--json",
                "--non-interactive",
                "--ui", "agent",
            ])
            self.assertIn(code, (0, 1))


class LifecycleMainSourceResolutionErrorTests(unittest.TestCase):
    def setUp(self) -> None:
        _State.session_source_info = None
        _State.log_file = None

    def tearDown(self) -> None:
        _State.session_source_info = None
        if _State.log_file is not None:
            _State.log_file.close()
            _State.log_file = None

    def test_missing_source_and_package_root_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, _stderr = _capture_main([
                "inspect",
                "--workspace", tmp,
                "--json",
            ])
            self.assertNotEqual(0, code)
            payload = json.loads(stdout)
            self.assertEqual("error", payload["status"])



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
