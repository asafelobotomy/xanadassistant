"""Tests for emit_json_lines and ProgressTests in the lifecycle engine."""
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
        self.assertIn("xanadAssistant", buf.getvalue())

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
        self.assertIn("xanadAssistant", err_buf.getvalue())

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
                self.assertIn("xanadAssistant", log_content)
            finally:
                if _State.log_file is not None:
                    _State.log_file.close()
                    _State.log_file = None



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
