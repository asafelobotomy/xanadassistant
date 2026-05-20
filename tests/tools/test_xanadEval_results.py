"""Tests for xanadEval results commands: list, view, compare."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xanadEval_test_support import xe, DynamicTestBase


class ResultsCommandTests(DynamicTestBase, unittest.TestCase):
    """Tests for cmd_results_list, cmd_results_view, and cmd_compare_results."""

    def test_results_list_shows_saved_runs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            self._write_result(dp, "run-a")
            self._write_result(dp, "run-b")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_results_list(str(dp), "text")
        self.assertEqual(code, 0)
        self.assertIn("run-a", buf.getvalue())

    def test_results_list_empty_dir_returns_1(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_results_list(d, "text")
        self.assertEqual(code, 1)

    def test_results_view_shows_task_breakdown(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            result_path = self._write_result(Path(d))
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_results_view(str(result_path), "text")
        self.assertEqual(code, 0)
        self.assertIn("task-1", buf.getvalue())

    def test_results_view_json_is_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            result_path = self._write_result(Path(d))
            buf = io.StringIO()
            with redirect_stdout(buf):
                xe.cmd_results_view(str(result_path), "json")
        data = json.loads(buf.getvalue())
        self.assertIn("tasks", data)

    def test_compare_results_shows_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            r1 = self._write_result(dp, "run-a", pass_rate=0.0)
            r2 = self._write_result(dp, "run-b", pass_rate=1.0)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_compare_results([str(r1), str(r2)], "text")
        self.assertEqual(code, 0)
        self.assertIn("task-1", buf.getvalue())

    def test_compare_results_needs_two_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            r = self._write_result(Path(d))
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_compare_results([str(r)], "text")
        self.assertEqual(code, 2)

    def test_results_view_null_score_returns_0(self) -> None:
        """cmd_results_view must display '?' for null or non-numeric score values."""
        with tempfile.TemporaryDirectory() as d:
            result = {
                "eval": "evals/test-skill/eval.yaml",
                "skill": "test-skill",
                "model": "gpt-4o-mini",
                "timestamp": "2026-05-20T12:00:00Z",
                "summary": {"total": 1, "passed": 0, "pass_rate": 0.0, "score": None},
                "tasks": [{
                    "id": "task-1",
                    "prompt": "p",
                    "response": "r",
                    "graders": [],
                    "passed": False,
                    "score": None,
                }],
            }
            result_path = Path(d) / "run.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_results_view(str(result_path), "text")
        self.assertEqual(code, 0)
        self.assertIn("?", buf.getvalue())

    def test_results_view_string_pass_rate_returns_0(self) -> None:
        """cmd_results_view must display '?' when pass_rate is a non-numeric string."""
        with tempfile.TemporaryDirectory() as d:
            result = {
                "eval": "evals/test-skill/eval.yaml",
                "skill": "test-skill",
                "model": "gpt-4o-mini",
                "timestamp": "2026-05-20T12:00:00Z",
                "summary": {"total": 1, "passed": 0, "pass_rate": "bad", "score": 0.0},
                "tasks": [],
            }
            result_path = Path(d) / "run.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_results_view(str(result_path), "text")
        self.assertEqual(code, 0)
        self.assertIn("?", buf.getvalue())

    def test_results_list_string_numeric_fields_returns_0(self) -> None:
        """cmd_results_list must not crash when summary numeric fields are non-numeric strings."""
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            result = {
                "eval": "evals/test-skill/eval.yaml",
                "skill": "test-skill",
                "model": "gpt-4o-mini",
                "timestamp": "2026-05-20T12:00:00Z",
                "summary": {"total": 1, "passed": 0, "pass_rate": "bad", "score": "bad"},
                "tasks": [],
            }
            (dp / "run-result.json").write_text(json.dumps(result), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = xe.cmd_results_list(str(dp), "text")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
