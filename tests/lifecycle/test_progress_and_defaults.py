from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _defaults
from scripts.lifecycle._xanad import _progress
from scripts.lifecycle._xanad._errors import _State


class ProgressTests(unittest.TestCase):
    def test_color_helpers_respect_environment_and_tty(self) -> None:
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}, clear=False):
            self.assertFalse(_progress._color_enabled())

        with mock.patch.dict(os.environ, {"FORCE_COLOR": "1"}, clear=False):
            self.assertTrue(_progress._color_enabled())

        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("sys.stderr.isatty", return_value=False):
            self.assertFalse(_progress._color_enabled())
            self.assertEqual(_progress._ansi("32", "ok"), "ok")

    def test_log_progress_and_emit_agent_progress_cover_command_variants(self) -> None:
        original_log = _State.log_file
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                log_path = Path(tmpdir) / "progress.log"
                with log_path.open("w", encoding="utf-8") as handle, redirect_stderr(io.StringIO()) as stderr:
                    _State.log_file = handle
                    _progress._log_progress("hello")
                    _progress.emit_agent_progress(
                        {
                            "command": "inspect",
                            "warnings": [{"code": "warn"}],
                            "result": {"installState": "installed", "manifestSummary": {"declared": 3}},
                        }
                    )
                    _progress.emit_agent_progress(
                        {
                            "command": "check",
                            "status": "drift",
                            "result": {"summary": {"missing": 2}},
                        }
                    )
                    _progress.emit_agent_progress(
                        {
                            "command": "interview",
                            "result": {"questionCount": 4},
                        }
                    )
                    _progress.emit_agent_progress(
                        {
                            "command": "plan",
                            "status": "approval-required",
                            "result": {
                                "installState": "installed",
                                "writes": {"add": 1, "replace": 0, "merge": 0, "archiveRetired": 0, "deleted": 0},
                                "conflicts": [{"class": "managed-drift"}],
                                "approvalRequired": True,
                            },
                        }
                    )
                    _progress.emit_agent_progress(
                        {
                            "command": "apply",
                            "status": "ok",
                            "result": {
                                "writes": {"added": 1, "replaced": 2},
                                "summary": {"path": ".github/copilot-version.md"},
                                "validation": {"status": "passed"},
                                "dryRun": True,
                            },
                        }
                    )
                output = stderr.getvalue()
                logged = log_path.read_text(encoding="utf-8")
        finally:
            _State.log_file = original_log

        self.assertIn("xanadAssistant", output)
        self.assertIn("Warnings: 1", output)
        self.assertIn("Check status: drift", output)
        self.assertIn("Questions emitted: 4", output)
        self.assertIn("Waiting on Copilot", output)
        self.assertIn("Dry run: no files were written.", output)
        self.assertIn("hello", logged)

    def test_emit_payload_and_not_implemented_payload(self) -> None:
        payload = {"command": "inspect", "result": {"installState": "installed", "manifestSummary": {"declared": 1}}, "warnings": []}
        with mock.patch("scripts.lifecycle._xanad._progress.emit_agent_progress") as emit_agent_progress, mock.patch(
            "scripts.lifecycle._xanad._progress.emit_json"
        ) as emit_json, mock.patch(
            "scripts.lifecycle._xanad._progress.emit_json_lines"
        ) as emit_json_lines:
            _progress.emit_payload(payload, "agent", False)
            _progress.emit_payload(payload, "quiet", False)
            _progress.emit_payload(payload, "quiet", True)

        self.assertEqual(emit_agent_progress.call_count, 1)
        self.assertEqual(emit_json.call_count, 2)
        self.assertEqual(emit_json_lines.call_count, 1)
        not_implemented = _progress.build_not_implemented_payload("update", Path("/workspace"), Path("/package"), "repair")
        self.assertEqual(not_implemented["status"], "not-implemented")
        self.assertEqual(not_implemented["errors"][0]["details"]["mode"], "repair")


class DefaultsTests(unittest.TestCase):
    def test_derive_effective_plan_defaults_seeds_answers_and_ownership(self) -> None:
        with mock.patch(
            "scripts.lifecycle._xanad._interview.build_interview_questions",
            return_value=[
                {"id": "profile.selected", "kind": "choice", "options": ["balanced"], "default": "balanced"},
                {"id": "mcp.enabled", "kind": "confirm", "default": False},
            ],
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.resolve_question_answers",
            return_value=({"profile.selected": "balanced", "mcp.enabled": True}, [], []),
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_a.resolve_ownership_by_surface",
            return_value={"agents": "local"},
        ):
            answers, ownership = _defaults.derive_effective_plan_defaults(
                {"canonicalSurfaces": ["hook-scripts", "mcp-config"]},
                {"profileRegistry": {"profiles": [{"id": "balanced", "setupAnswerDefaults": {"mcp.enabled": True}}]}},
                {"managedFiles": []},
                {"profile": "balanced", "setupAnswers": {}, "selectedPacks": [], "mcpEnabled": True},
            )

        self.assertEqual(answers["profile.selected"], "balanced")
        self.assertTrue(answers["hooks.enabled"])
        self.assertEqual(ownership, {"agents": "local"})


if __name__ == "__main__":
    unittest.main()