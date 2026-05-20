"""Tests for xanadEval grader functions and extract_first_json_object."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xanadEval_test_support import xe, DynamicTestBase


class GraderUnitTests(DynamicTestBase, unittest.TestCase):
    """Unit tests for _grade_text, _grade_behavior, _run_graders, _grade_prompt_judge,
    _extract_first_json_object, and related helpers. No real API calls are made."""

    # ── grade_text ───────────────────────────────────────────────────────────

    def test_grade_text_matches_pattern(self) -> None:
        self.assertTrue(xe._grade_text("response about skills", {"pattern": "(?i)skill"}))
        self.assertFalse(xe._grade_text("response about topics", {"pattern": "(?i)skill"}))

    def test_grade_text_matches_contains(self) -> None:
        self.assertTrue(xe._grade_text("Hello world", {"contains": ["world"]}))
        self.assertFalse(xe._grade_text("Hello world", {"contains": ["missing"]}))

    def test_grade_text_no_criteria_passes(self) -> None:
        self.assertTrue(xe._grade_text("anything", {}))

    # ── grade_behavior ───────────────────────────────────────────────────────

    def test_grade_behavior_checks_token_budget(self) -> None:
        long_response = "word " * 500
        self.assertFalse(xe._grade_behavior(long_response, {"max_tokens": 10}))
        self.assertTrue(xe._grade_behavior("ok", {"max_tokens": 10000}))

    def test_grade_behavior_no_max_tokens_passes(self) -> None:
        self.assertTrue(xe._grade_behavior("anything", {"max_tool_calls": 5}))

    # ── run_graders ──────────────────────────────────────────────────────────

    def test_run_graders_returns_records(self) -> None:
        graders = [
            {"type": "text", "name": "has_word", "config": {"contains": ["test"]}},
            {"type": "behavior", "name": "short", "config": {"max_tokens": 10000}},
        ]
        results = xe._run_graders("test response", graders, "gpt-4o-mini", "")
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]["pass"])
        self.assertTrue(results[1]["pass"])

    def test_run_graders_skips_unknown_type(self) -> None:
        graders = [{"type": "code", "name": "complex", "config": {}}]
        results = xe._run_graders("any", graders, "gpt-4o-mini", "")
        self.assertIsNone(results[0]["pass"])
        self.assertIn("skipped", results[0])

    def test_run_graders_skips_prompt_without_token(self) -> None:
        graders = [{"type": "prompt", "name": "judge", "config": {"rubric": "helpful?"}}]
        results = xe._run_graders("any", graders, "gpt-4o-mini", "")
        self.assertIsNone(results[0]["pass"])
        self.assertIn("skipped", results[0])

    # ── grade_prompt_judge ───────────────────────────────────────────────────

    @mock.patch(
        "xanadEval._call_model",
        return_value='{"score": 0.9, "reasoning": {"note": "clear", "detail": "well written"}}',
    )
    def test_grade_prompt_judge_handles_nested_json(self, _mock) -> None:
        """_grade_prompt_judge must succeed when the model returns nested JSON."""
        passed, score = xe._grade_prompt_judge(
            "good response", {"rubric": "helpful?", "threshold": 0.7},
            "gpt-4o-mini", "fake-token",
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 0.9)

    @mock.patch(
        "xanadEval._call_model",
        return_value='{bad JSON} {"score": 0.8, "reasoning": "fine"}',
    )
    def test_grade_prompt_judge_skips_malformed_prefix(self, _mock) -> None:
        """_extract_first_json_object must skip a malformed prefix and find the valid object."""
        passed, score = xe._grade_prompt_judge(
            "response", {"rubric": "helpful?", "threshold": 0.7},
            "gpt-4o-mini", "fake-token",
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 0.8)

    @mock.patch(
        "xanadEval._call_model",
        return_value='{"score": 0.9, "reasoning": "ok"}',
    )
    def test_grade_prompt_judge_invalid_threshold_returns_fail(self, _mock) -> None:
        """An invalid threshold type must return (False, 0.0) without crashing."""
        passed, score = xe._grade_prompt_judge(
            "response", {"rubric": "helpful?", "threshold": {"nested": "dict"}},
            "gpt-4o-mini", "fake-token",
        )
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)

    # ── extract_first_json_object ─────────────────────────────────────────────

    def test_extract_first_json_object_skips_malformed_prefix(self) -> None:
        """Malformed balanced span before a valid object must be skipped."""
        result = xe._extract_first_json_object('{bad} {"score": 0.5}')
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["score"], 0.5)  # type: ignore[index]

    def test_extract_first_json_object_handles_brace_in_string(self) -> None:
        """raw_decode must handle a } inside a JSON string value without failing."""
        result = xe._extract_first_json_object('{"summary": "close } brace", "score": 1}')
        self.assertIsNotNone(result)
        self.assertEqual(result["score"], 1)  # type: ignore[index]
        self.assertIn("}", result["summary"])  # type: ignore[index]

    # ── compare_results null/added/removed ────────────────────────────────────

    def test_compare_results_null_scores_do_not_crash(self) -> None:
        """Shared tasks with null scores must not crash cmd_compare_results."""
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            make = lambda name, score: {  # noqa: E731
                "eval": "e.yaml", "skill": "s", "model": "m",
                "timestamp": "2026-01-01T00:00:00Z",
                "summary": {"total": 1, "passed": 0, "pass_rate": 0.0, "score": None},
                "tasks": [{"id": "task-1", "prompt": "p", "response": "r",
                           "graders": [], "passed": False, "score": score}],
            }
            r1 = dp / "base.json"
            r2 = dp / "cmp.json"
            r1.write_text(json.dumps(make("base", None)), encoding="utf-8")
            r2.write_text(json.dumps(make("cmp", None)), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code_text = xe.cmd_compare_results([str(r1), str(r2)], "text")
            buf2 = io.StringIO()
            with redirect_stdout(buf2):
                code_json = xe.cmd_compare_results([str(r1), str(r2)], "json")
        self.assertEqual(code_text, 0)
        self.assertEqual(code_json, 0)
        data = json.loads(buf2.getvalue())
        self.assertEqual(data["task_deltas"][0]["task"], "task-1")

    def test_compare_results_reports_added_and_removed_tasks(self) -> None:
        """Tasks present in only one file should appear with status 'added' or 'removed'."""
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            baseline = {
                "eval": "e.yaml", "skill": "s", "model": "m",
                "timestamp": "2026-01-01T00:00:00Z",
                "summary": {"total": 1, "passed": 1, "pass_rate": 1.0, "score": 1.0},
                "tasks": [{"id": "task-1", "prompt": "p", "response": "r",
                           "graders": [], "passed": True, "score": 1.0}],
            }
            compare = {
                "eval": "e.yaml", "skill": "s", "model": "m",
                "timestamp": "2026-01-02T00:00:00Z",
                "summary": {"total": 1, "passed": 1, "pass_rate": 1.0, "score": 1.0},
                "tasks": [{"id": "task-2", "prompt": "p", "response": "r",
                           "graders": [], "passed": True, "score": 1.0}],
            }
            r1 = dp / "base.json"
            r2 = dp / "cmp.json"
            r1.write_text(json.dumps(baseline), encoding="utf-8")
            r2.write_text(json.dumps(compare), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_compare_results([str(r1), str(r2)], "json")
            data = json.loads(buf.getvalue())
        statuses = {d["task"]: d["status"] for d in data["task_deltas"]}
        self.assertEqual(statuses.get("task-1"), "removed")
        self.assertEqual(statuses.get("task-2"), "added")
        self.assertEqual(code, 0)

    # ── _load_tasks traversal guard ───────────────────────────────────────────

    def test_load_tasks_rejects_dotdot_traversal(self) -> None:
        """_load_tasks must raise ValueError for task refs containing '..' parts."""
        with tempfile.TemporaryDirectory() as d:
            eval_dir = Path(d) / "evals" / "test-skill"
            eval_dir.mkdir(parents=True)
            with self.assertRaises(ValueError):
                xe._load_tasks(eval_dir, ["../../evil.yaml"])

    def test_load_tasks_rejects_absolute_paths(self) -> None:
        """_load_tasks must raise ValueError for absolute task refs."""
        with tempfile.TemporaryDirectory() as d:
            eval_dir = Path(d) / "evals" / "test-skill"
            eval_dir.mkdir(parents=True)
            with self.assertRaises(ValueError):
                xe._load_tasks(eval_dir, ["/etc/passwd"])


if __name__ == "__main__":
    unittest.main()
