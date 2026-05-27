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
        passed, _ = xe._grade_text("response about skills", {"pattern": "(?i)skill"})
        self.assertTrue(passed)
        passed, _ = xe._grade_text("response about topics", {"pattern": "(?i)skill"})
        self.assertFalse(passed)

    def test_grade_text_contains_and_semantics(self) -> None:
        """All items in 'contains' must be present (AND semantics)."""
        passed, score = xe._grade_text("Hello world", {"contains": ["world"]})
        self.assertTrue(passed)
        self.assertEqual(score, 1.0)
        passed, score = xe._grade_text("Hello world", {"contains": ["missing"]})
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)
        # Both items must appear — partial match → fail with partial score
        passed, score = xe._grade_text("Hello world", {"contains": ["hello", "missing"]})
        self.assertFalse(passed)
        self.assertAlmostEqual(score, 0.5)

    def test_grade_text_not_contains(self) -> None:
        """not_contains: listed strings must NOT appear."""
        passed, score = xe._grade_text("Hello world", {"not_contains": ["missing"]})
        self.assertTrue(passed)
        self.assertEqual(score, 1.0)
        passed, score = xe._grade_text("Hello world", {"not_contains": ["world"]})
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)

    def test_grade_text_regex_match(self) -> None:
        """regex_match: all patterns must match."""
        passed, score = xe._grade_text("error: code 404", {"regex_match": [r"\d+"]})
        self.assertTrue(passed)
        passed, score = xe._grade_text("no numbers here", {"regex_match": [r"\d+"]})
        self.assertFalse(passed)
        # Two patterns: only first matches → partial score
        passed, score = xe._grade_text("error 404", {
            "regex_match": [r"\d+", r"(?i)success"]
        })
        self.assertFalse(passed)
        self.assertAlmostEqual(score, 0.5)

    def test_grade_text_regex_not_match(self) -> None:
        """regex_not_match: none of the patterns may match."""
        passed, _ = xe._grade_text("clean output", {"regex_not_match": [r"(?i)error"]})
        self.assertTrue(passed)
        passed, _ = xe._grade_text("fatal error occurred", {"regex_not_match": [r"(?i)error"]})
        self.assertFalse(passed)

    def test_grade_text_partial_scoring_mixed(self) -> None:
        """Multiple checks across keys contribute to partial score."""
        # contains "hello" ✓, not_contains "world" ✗ (world IS present)
        passed, score = xe._grade_text("hello world", {
            "contains": ["hello"],
            "not_contains": ["world"],
        })
        self.assertFalse(passed)
        self.assertAlmostEqual(score, 0.5)

    def test_grade_text_no_criteria_passes(self) -> None:
        passed, score = xe._grade_text("anything", {})
        self.assertTrue(passed)
        self.assertEqual(score, 1.0)

    # ── grade_behavior ───────────────────────────────────────────────────────

    def test_grade_behavior_checks_token_budget(self) -> None:
        long_response = "word " * 500
        passed, _ = xe._grade_behavior(long_response, {"max_tokens": 10})
        self.assertFalse(passed)
        passed, _ = xe._grade_behavior("ok", {"max_tokens": 10000})
        self.assertTrue(passed)

    def test_grade_behavior_min_tokens(self) -> None:
        passed, score = xe._grade_behavior("short", {"min_tokens": 10000})
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)
        passed, score = xe._grade_behavior("short", {"min_tokens": 1})
        self.assertTrue(passed)

    def test_grade_behavior_partial_score_max_and_min(self) -> None:
        """Both max_tokens and min_tokens can be configured; partial scoring applies."""
        # response within min but over max → one check fails
        long = "word " * 100
        passed, score = xe._grade_behavior(long, {"min_tokens": 1, "max_tokens": 5})
        self.assertFalse(passed)
        self.assertAlmostEqual(score, 0.5)

    def test_grade_behavior_no_constraints_passes(self) -> None:
        passed, score = xe._grade_behavior("anything", {"max_tool_calls": 5})
        self.assertTrue(passed)
        self.assertEqual(score, 1.0)

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
        graders = [{"type": "unsupported_custom_type", "name": "complex", "config": {}}]
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


class JSONSchemaGraderTests(unittest.TestCase):
    """Tests for the json_schema grader type via _grade_json_schema and _run_graders."""

    def test_invalid_json_fails(self) -> None:
        passed, score, feedback = xe._grade_json_schema("not json", {})
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)
        self.assertIn("JSON", feedback)

    def test_valid_json_no_schema_passes(self) -> None:
        passed, score, _ = xe._grade_json_schema('{"status": "ok"}', {})
        self.assertTrue(passed)
        self.assertEqual(score, 1.0)

    def test_valid_json_with_inline_schema_passes(self) -> None:
        schema = {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"type": "string"}},
        }
        response = json.dumps({"status": "ok"})
        try:
            import jsonschema  # noqa: F401
            passed, score, _ = xe._grade_json_schema(response, {"schema": schema})
            self.assertTrue(passed)
            self.assertEqual(score, 1.0)
        except ImportError:
            self.skipTest("jsonschema not installed")

    def test_valid_json_schema_violation_fails(self) -> None:
        schema = {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"type": "integer"}},
        }
        response = json.dumps({"status": "not-an-int"})
        try:
            import jsonschema  # noqa: F401
            passed, score, feedback = xe._grade_json_schema(response, {"schema": schema})
            self.assertFalse(passed)
            self.assertEqual(score, 0.0)
            self.assertTrue(feedback)
        except ImportError:
            self.skipTest("jsonschema not installed")

    def test_missing_schema_file_fails(self) -> None:
        passed, score, feedback = xe._grade_json_schema(
            '{"x": 1}', {"schema_file": "/nonexistent/schema.json"}
        )
        self.assertFalse(passed)
        self.assertIn("schema_file", feedback)

    def test_run_graders_json_schema_type_recognised(self) -> None:
        """json_schema grader must be dispatched (not skipped) via _run_graders."""
        graders = [{"type": "json_schema", "name": "valid_json", "config": {}}]
        results = xe._run_graders('{"key": "value"}', graders, "gpt-4o-mini", "")
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0]["pass"])
        self.assertTrue(results[0]["pass"])

    def test_run_graders_json_schema_invalid_response(self) -> None:
        graders = [{"type": "json_schema", "name": "valid_json", "config": {}}]
        results = xe._run_graders("plain text", graders, "gpt-4o-mini", "")
        self.assertFalse(results[0]["pass"])
        self.assertEqual(results[0]["score"], 0.0)


class ProgramGraderTests(unittest.TestCase):
    """Tests for the program grader type via _grade_program and _run_graders."""

    def test_exit_zero_passes(self) -> None:
        passed, score, _ = xe._grade_program("hello", {"command": "true"})
        self.assertTrue(passed)
        self.assertEqual(score, 1.0)

    def test_exit_nonzero_fails(self) -> None:
        passed, score, _ = xe._grade_program("hello", {"command": "false"})
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)

    def test_missing_command_field_fails(self) -> None:
        passed, score, feedback = xe._grade_program("hello", {})
        self.assertFalse(passed)
        self.assertIn("command", feedback)

    def test_missing_executable_fails_gracefully(self) -> None:
        passed, score, feedback = xe._grade_program(
            "hello", {"command": "__nonexistent_cmd_xyz__"}
        )
        self.assertFalse(passed)
        self.assertIn("not found", feedback)

    def test_run_graders_program_type_recognised(self) -> None:
        """program grader must be dispatched (not skipped) via _run_graders."""
        graders = [{"type": "program", "name": "always_pass",
                    "config": {"command": "true"}}]
        results = xe._run_graders("any", graders, "gpt-4o-mini", "")
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0]["pass"])
        self.assertTrue(results[0]["pass"])


class LlmGraderTests(DynamicTestBase, unittest.TestCase):
    """Unit tests for _grade_llm (LLM-as-judge with rubric 1\u20135 \u2192 0\u20131)."""

    @mock.patch("xanadEval._call_model", return_value='{"score": 5, "reasoning": "excellent"}')
    def test_score_5_normalises_to_1(self, _m) -> None:
        passed, score, reasoning = xe._grade_llm(
            "great response", {"rubric": "Rate quality"}, "gpt-4o-mini", "tok"
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 1.0)
        self.assertIn("excellent", reasoning)

    @mock.patch("xanadEval._call_model", return_value='{"score": 1, "reasoning": "poor"}')
    def test_score_1_normalises_to_0(self, _m) -> None:
        passed, score, _ = xe._grade_llm(
            "bad response", {"rubric": "Rate quality", "threshold": 0.1}, "gpt-4o-mini", "tok"
        )
        self.assertFalse(passed)
        self.assertAlmostEqual(score, 0.0)

    @mock.patch("xanadEval._call_model", return_value='{"score": 3, "reasoning": "ok"}')
    def test_score_3_normalises_to_half(self, _m) -> None:
        _, score, _ = xe._grade_llm(
            "ok response", {"rubric": "Rate quality"}, "gpt-4o-mini", "tok"
        )
        self.assertAlmostEqual(score, 0.5)

    def test_missing_rubric_fails(self) -> None:
        passed, score, feedback = xe._grade_llm("r", {}, "gpt-4o-mini", "tok")
        self.assertFalse(passed)
        self.assertIn("rubric", feedback)

    def test_run_graders_skips_llm_without_token(self) -> None:
        graders = [{"type": "llm", "name": "j", "config": {"rubric": "Is it good?"}}]
        results = xe._run_graders("any", graders, "gpt-4o-mini", "")
        self.assertIsNone(results[0]["pass"])
        self.assertIn("skipped", results[0])


class LlmComparisonGraderTests(DynamicTestBase, unittest.TestCase):
    """Unit tests for _grade_llm_comparison (response vs reference)."""

    @mock.patch("xanadEval._call_model", return_value='{"score": 4, "reasoning": "close"}')
    def test_score_4_normalises_correctly(self, _m) -> None:
        passed, score, reasoning = xe._grade_llm_comparison(
            "good response", {"reference": "ideal answer"}, "gpt-4o-mini", "tok"
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 0.75)
        self.assertIn("close", reasoning)

    def test_missing_reference_fails(self) -> None:
        passed, score, feedback = xe._grade_llm_comparison("r", {}, "gpt-4o-mini", "tok")
        self.assertFalse(passed)
        self.assertIn("reference", feedback)

    def test_run_graders_skips_llm_comparison_without_token(self) -> None:
        graders = [{"type": "llm_comparison", "name": "cmp",
                    "config": {"reference": "expected output"}}]
        results = xe._run_graders("any", graders, "gpt-4o-mini", "")
        self.assertIsNone(results[0]["pass"])
        self.assertIn("skipped", results[0])

    @mock.patch("xanadEval._call_model", return_value="not valid json at all")
    def test_unexpected_response_fails_gracefully(self, _m) -> None:
        passed, score, feedback = xe._grade_llm_comparison(
            "response", {"reference": "ideal"}, "gpt-4o-mini", "tok"
        )
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)


if __name__ == "__main__":
    unittest.main()
