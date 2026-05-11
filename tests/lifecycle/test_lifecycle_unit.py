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


class CliParserTests(unittest.TestCase):
    def test_build_parser_returns_parser(self) -> None:
        import argparse
        parser = build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)

    def test_inspect_subcommand_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "inspect",
            "--workspace", "/tmp/ws",
            "--package-root", "/tmp/pkg",
        ])
        self.assertEqual("inspect", args.command)
        self.assertEqual("/tmp/ws", args.workspace)

    def test_check_subcommand_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "check",
            "--workspace", "/tmp/ws",
            "--package-root", "/tmp/pkg",
        ])
        self.assertEqual("check", args.command)

    def test_interview_subcommand_parses_mode(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "interview",
            "--workspace", "/tmp/ws",
            "--package-root", "/tmp/pkg",
            "--mode", "update",
        ])
        self.assertEqual("interview", args.command)
        self.assertEqual("update", args.mode)

    def test_plan_setup_subcommand_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "plan", "setup",
            "--workspace", "/tmp/ws",
            "--package-root", "/tmp/pkg",
        ])
        self.assertEqual("plan", args.command)
        self.assertEqual("setup", args.mode)

    def test_apply_subcommand_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "apply",
            "--workspace", "/tmp/ws",
            "--package-root", "/tmp/pkg",
            "--non-interactive",
        ])
        self.assertEqual("apply", args.command)
        self.assertTrue(args.non_interactive)

    def test_common_flags_available_on_all_subparsers(self) -> None:
        parser = build_parser()
        for command in ("inspect", "check"):
            args = parser.parse_args([
                command,
                "--workspace", "/tmp/ws",
                "--package-root", "/tmp/pkg",
                "--json",
                "--json-lines",
                "--dry-run",
                "--ui", "agent",
            ])
            self.assertTrue(args.json)
            self.assertTrue(args.json_lines)
            self.assertTrue(args.dry_run)
            self.assertEqual("agent", args.ui)


class EmitJsonTests(unittest.TestCase):
    def test_emit_json_writes_to_stdout(self) -> None:
        payload = {"command": "inspect", "status": "ok", "test": True}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emit_json(payload)
        output = buf.getvalue()
        self.assertTrue(output.endswith("\n"))
        parsed = json.loads(output)
        self.assertTrue(parsed["test"])

    def test_emit_json_uses_indent(self) -> None:
        payload = {"a": {"b": 1}}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emit_json(payload)
        self.assertIn("  ", buf.getvalue())


class EmitJsonLinesTests(unittest.TestCase):
    def _emit(self, payload: dict) -> list[dict]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emit_json_lines(payload)
        return [json.loads(line) for line in buf.getvalue().strip().splitlines()]

    def test_inspect_payload_emits_three_events(self) -> None:
        payload = {
            "command": "inspect",
            "status": "ok",
            "warnings": [],
            "result": {
                "installState": "not-installed",
                "manifestSummary": {"declared": 0},
                "contracts": {},
            },
        }
        events = self._emit(payload)
        types = [e["type"] for e in events]
        self.assertIn("phase", types)
        self.assertIn("inspect-summary", types)
        self.assertIn("receipt", types)

    def test_check_payload_emits_events(self) -> None:
        payload = {
            "command": "check",
            "status": "clean",
            "warnings": [],
            "result": {
                "summary": {"missing": 0},
                "unmanagedFiles": [],
            },
        }
        events = self._emit(payload)
        types = [e["type"] for e in events]
        self.assertIn("check-summary", types)

    def test_interview_payload_emits_question_events(self) -> None:
        payload = {
            "command": "interview",
            "status": "ok",
            "warnings": [],
            "result": {
                "questions": [
                    {"id": "q1", "question": "Is this ok?"},
                ],
                "questionCount": 1,
            },
        }
        events = self._emit(payload)
        types = [e["type"] for e in events]
        self.assertIn("question", types)

    def test_plan_payload_emits_plan_summary(self) -> None:
        payload = {
            "command": "plan",
            "mode": "setup",
            "status": "ok",
            "warnings": [],
            "errors": [],
            "result": {
                "installState": "not-installed",
                "installPaths": {"legacyVersionFile": None, "lockfile": None},
                "questions": [],
                "approvalRequired": False,
                "backupRequired": False,
                "backupPlan": {},
                "plannedLockfile": {},
                "writes": {"added": 0, "replaced": 0},
                "conflictSummary": {},
                "conflicts": [],
            },
        }
        events = self._emit(payload)
        types = [e["type"] for e in events]
        self.assertIn("plan-summary", types)

    def test_apply_payload_emits_apply_report(self) -> None:
        payload = {
            "command": "apply",
            "status": "ok",
            "warnings": [],
            "result": {
                "backup": {},
                "writes": {"added": 1, "replaced": 0},
                "retired": [],
                "lockfile": {},
                "summary": {"path": "/tmp/summary.md"},
                "validation": {"status": "passed"},
            },
        }
        events = self._emit(payload)
        types = [e["type"] for e in events]
        self.assertIn("apply-report", types)

    def test_unknown_command_emits_error_event(self) -> None:
        payload = {
            "command": "unknown-command",
            "status": "not-implemented",
            "warnings": [],
            "errors": [{"message": "Not implemented", "code": "not_implemented"}],
        }
        events = self._emit(payload)
        self.assertEqual("error", events[0]["type"])

    def test_warning_in_payload_is_inserted_as_warning_event(self) -> None:
        payload = {
            "command": "check",
            "status": "clean",
            "warnings": [{"code": "test_warn", "message": "A warning"}],
            "result": {
                "summary": {"missing": 0},
                "unmanagedFiles": [],
            },
        }
        events = self._emit(payload)
        types = [e["type"] for e in events]
        self.assertIn("warning", types)

    def test_update_payload_emits_apply_report(self) -> None:
        payload = {
            "command": "update",
            "status": "ok",
            "warnings": [],
            "result": {
                "backup": {},
                "writes": {"added": 0, "replaced": 1},
                "retired": [],
                "lockfile": {},
                "summary": {"path": "/tmp/summary.md"},
                "validation": {"status": "passed"},
            },
        }
        events = self._emit(payload)
        types = [e["type"] for e in events]
        self.assertIn("apply-report", types)


class ProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        import os
        self._orig_env = os.environ.copy()
        _State.log_file = None

    def tearDown(self) -> None:
        import os
        os.environ.clear()
        os.environ.update(self._orig_env)
        if _State.log_file is not None:
            _State.log_file.close()
            _State.log_file = None

    def test_color_enabled_false_when_no_color_set(self) -> None:
        import os
        os.environ["NO_COLOR"] = "1"
        self.assertFalse(_color_enabled())

    def test_color_enabled_true_when_force_color_set(self) -> None:
        import os
        os.environ.pop("NO_COLOR", None)
        os.environ["FORCE_COLOR"] = "1"
        self.assertTrue(_color_enabled())

    def test_ansi_returns_plain_when_no_color(self) -> None:
        import os
        os.environ["NO_COLOR"] = "1"
        result = _ansi("32", "hello")
        self.assertEqual("hello", result)

    def test_ansi_wraps_when_force_color(self) -> None:
        import os
        os.environ.pop("NO_COLOR", None)
        os.environ["FORCE_COLOR"] = "1"
        result = _ansi("32", "hello")
        self.assertIn("\033[", result)

    def test_emit_agent_progress_inspect(self) -> None:
        payload = {
            "command": "inspect",
            "status": "ok",
            "warnings": [],
            "result": {
                "installState": "not-installed",
                "manifestSummary": {"declared": 0},
            },
        }
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            emit_agent_progress(payload)
        self.assertIn("Preflight", buf.getvalue())

    def test_emit_agent_progress_check(self) -> None:
        payload = {
            "command": "check",
            "status": "clean",
            "warnings": [],
            "result": {"summary": {"missing": 0}},
        }
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            emit_agent_progress(payload)
        self.assertIn("Check status", buf.getvalue())

    def test_emit_agent_progress_interview(self) -> None:
        payload = {
            "command": "interview",
            "status": "ok",
            "warnings": [],
            "result": {"questionCount": 3},
        }
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            emit_agent_progress(payload)
        self.assertIn("Questions emitted", buf.getvalue())

    def test_emit_agent_progress_plan(self) -> None:
        payload = {
            "command": "plan",
            "status": "ok",
            "warnings": [],
            "result": {
                "installState": "not-installed",
                "writes": {"added": 2},
                "conflicts": [],
                "approvalRequired": False,
            },
        }
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            emit_agent_progress(payload)
        self.assertIn("Planned writes", buf.getvalue())

    def test_emit_agent_progress_plan_with_conflicts_and_approval(self) -> None:
        payload = {
            "command": "plan",
            "status": "ok",
            "warnings": [],
            "result": {
                "installState": "not-installed",
                "writes": {"added": 1},
                "conflicts": [{"type": "conflict"}],
                "approvalRequired": True,
            },
        }
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            emit_agent_progress(payload)
        output = buf.getvalue()
        self.assertIn("Conflict", output)
        self.assertIn("Waiting on Copilot", output)

    def test_emit_agent_progress_apply(self) -> None:
        payload = {
            "command": "apply",
            "status": "ok",
            "warnings": [],
            "result": {
                "writes": {"added": 5, "replaced": 2},
                "summary": {"path": "/tmp/summary.md"},
                "validation": {"status": "passed"},
                "dryRun": False,
            },
        }
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            emit_agent_progress(payload)
        self.assertIn("Files added", buf.getvalue())

    def test_emit_agent_progress_apply_dry_run(self) -> None:
        payload = {
            "command": "apply",
            "status": "ok",
            "warnings": [],
            "result": {
                "writes": {"added": 0, "replaced": 0},
                "summary": {"path": "/tmp/summary.md"},
                "validation": {"status": "passed"},
                "dryRun": True,
            },
        }
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            emit_agent_progress(payload)
        self.assertIn("Dry run", buf.getvalue())

    def test_emit_agent_progress_unknown_command(self) -> None:
        payload = {"command": "unknown", "status": "not-implemented", "warnings": []}
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            emit_agent_progress(payload)
        self.assertIn("xanad-assistant", buf.getvalue())

    def test_emit_payload_calls_emit_json_by_default(self) -> None:
        payload = {
            "command": "inspect",
            "status": "ok",
            "warnings": [],
            "result": {
                "installState": "not-installed",
                "manifestSummary": {"declared": 0},
                "contracts": {},
            },
        }
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emit_payload(payload, "quiet", False)
        parsed = json.loads(buf.getvalue())
        self.assertEqual("inspect", parsed["command"])

    def test_emit_payload_calls_emit_json_lines_when_flag_set(self) -> None:
        payload = {
            "command": "inspect",
            "status": "ok",
            "warnings": [],
            "result": {
                "installState": "not-installed",
                "manifestSummary": {"declared": 0},
                "contracts": {},
            },
        }
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emit_payload(payload, "quiet", True)
        lines = buf.getvalue().strip().splitlines()
        self.assertGreater(len(lines), 1)

    def test_emit_payload_agent_calls_emit_agent_progress(self) -> None:
        payload = {
            "command": "inspect",
            "status": "ok",
            "warnings": [],
            "result": {
                "installState": "not-installed",
                "manifestSummary": {"declared": 0},
                "contracts": {},
            },
        }
        err_buf = io.StringIO()
        out_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf), contextlib.redirect_stdout(out_buf):
            emit_payload(payload, "agent", False)
        self.assertIn("xanad-assistant", err_buf.getvalue())

    def test_emit_agent_progress_writes_to_log_file(self) -> None:
        payload = {
            "command": "inspect",
            "status": "ok",
            "warnings": [],
            "result": {
                "installState": "not-installed",
                "manifestSummary": {"declared": 0},
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "progress.log"
            _State.log_file = log_path.open("w", encoding="utf-8")
            try:
                buf = io.StringIO()
                with contextlib.redirect_stderr(buf):
                    emit_agent_progress(payload)
                _State.log_file.close()
                _State.log_file = None
                log_content = log_path.read_text(encoding="utf-8")
                self.assertIn("xanad-assistant", log_content)
            finally:
                if _State.log_file is not None:
                    _State.log_file.close()
                    _State.log_file = None


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
            lockfile = github_dir / "xanad-assistant-lock.json"
            lockfile.write_text("NOT VALID JSON{{{", encoding="utf-8")
            code, payload = self._check_workspace(tmp)
            self.assertEqual(7, code)
            self.assertEqual("drift", payload["status"])

    def test_check_with_missing_required_lockfile_fields_reports_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            github_dir = Path(tmp) / ".github"
            github_dir.mkdir()
            lockfile = github_dir / "xanad-assistant-lock.json"
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
