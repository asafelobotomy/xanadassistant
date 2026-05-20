"""Tests for xanadEval runtime commands: run, grade, results list/view/compare."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xanadEval_test_support import xe, DynamicTestBase


class RunCommandTests(DynamicTestBase, unittest.TestCase):
    """Tests for cmd_run — executing eval tasks against GitHub Models."""

    def test_run_requires_token(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=False):
            for key in ("GITHUB_TOKEN", "GH_TOKEN"):
                os.environ.pop(key, None)
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_run("fake.yaml", "gpt-4o-mini", 1, "text")
        self.assertEqual(code, 2)

    @mock.patch("xanadEval._call_model",
                return_value="This response mentions test-skill content.")
    def test_run_executes_tasks_and_saves_results(self, _mock) -> None:
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_path = self._write_eval(dp)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = xe.cmd_run(str(eval_path), "gpt-4o-mini", 1, "text")
                self.assertEqual(code, 0)
                results_dir = dp / xe._DEFAULT_RESULTS_DIR
                self.assertTrue(results_dir.exists())
                self.assertEqual(len(list(results_dir.glob("*.json"))), 1)

    @mock.patch("xanadEval._call_model", return_value="test skill response")
    def test_run_json_output_has_summary_and_tasks(self, _mock) -> None:
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_path = self._write_eval(dp)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = xe.cmd_run(str(eval_path), "gpt-4o-mini", 1, "json")
                self.assertIn(code, (0, 1))
                data = json.loads(buf.getvalue())
                self.assertIn("summary", data)
                self.assertIn("tasks", data)
                self.assertEqual(data["tasks"][0]["id"], "task-1")

    @mock.patch("xanadEval._call_model", return_value="any response")
    def test_run_non_dict_task_document_returns_2(self, _mock) -> None:
        """A task file that parses to a list (not a dict) must produce a controlled exit 2."""
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_dir = dp / "evals" / "test-skill"
                (eval_dir / "tasks").mkdir(parents=True)
                spec = {
                    "name": "test-skill-eval",
                    "graders": [{"type": "text", "name": "x", "config": {"contains": ["test"]}}],
                    "tasks": ["tasks/*.yaml"],
                }
                (eval_dir / "eval.yaml").write_text(json.dumps(spec), encoding="utf-8")
                # Write a list instead of a mapping
                (eval_dir / "tasks" / "t1.yaml").write_text(
                    json.dumps(["not", "a", "dict"]), encoding="utf-8"
                )
                err = io.StringIO()
                with redirect_stderr(err):
                    code = xe.cmd_run(str(eval_dir / "eval.yaml"), "gpt-4o-mini", 1, "text")
        self.assertEqual(code, 2)
        self.assertIn("task", err.getvalue().lower())

    @mock.patch("xanadEval._call_model", return_value="anything")
    def test_run_path_traversal_in_skill_name_is_sanitized(self, _mock) -> None:
        """A spec name containing path separators must not escape the results directory."""
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_dir = dp / "evals" / "test-skill"
                (eval_dir / "tasks").mkdir(parents=True)
                spec = {
                    "name": "../../evil",
                    "graders": [{"type": "text", "name": "x", "config": {"contains": ["anything"]}}],
                    "tasks": ["tasks/*.yaml"],
                }
                eval_yaml = eval_dir / "eval.yaml"
                eval_yaml.write_text(json.dumps(spec), encoding="utf-8")
                (eval_dir / "tasks" / "t1.yaml").write_text(
                    json.dumps({"id": "task-1", "prompt": "test"}), encoding="utf-8"
                )
                xe.cmd_run(str(eval_yaml), "gpt-4o-mini", 1, "text")
                results_dir = dp / ".xanadEval"
                self.assertTrue(results_dir.exists(), "Results directory must be created")
                resolved_base = str(results_dir.resolve())
                for f in results_dir.iterdir():
                    self.assertTrue(
                        str(f.resolve()).startswith(resolved_base),
                        f"Result file escaped results dir: {f}",
                    )

    @mock.patch("xanadEval._call_model")
    def test_multi_trial_aggregates_all_responses(self, mock_call) -> None:
        """trials=2 should grade every response, not just responses[0]."""
        mock_call.side_effect = [
            "response mentioning test-skill content",
            "response about unrelated topics",
        ]
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_path = self._write_eval(dp)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = xe.cmd_run(str(eval_path), "gpt-4o-mini", 2, "json")
                data = json.loads(buf.getvalue())
        self.assertEqual(mock_call.call_count, 2)
        grader = data["tasks"][0]["graders"][0]
        self.assertEqual(grader.get("trials"), 2)
        self.assertFalse(data["tasks"][0]["passed"])

    @mock.patch("xanadEval._call_model", return_value="any response")
    def test_empty_grader_set_task_fails_closed(self, _mock) -> None:
        """A task with only unsupported graders must fail, not silently pass."""
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_dir = dp / "evals" / "test-skill"
                (eval_dir / "tasks").mkdir(parents=True)
                spec = {
                    "name": "test-skill-eval",
                    "graders": [
                        {"type": "code", "name": "unsupported", "config": {}}
                    ],
                    "tasks": ["tasks/*.yaml"],
                }
                eval_yaml = eval_dir / "eval.yaml"
                eval_yaml.write_text(json.dumps(spec), encoding="utf-8")
                (eval_dir / "tasks" / "t1.yaml").write_text(
                    json.dumps({"id": "task-1", "prompt": "test"}), encoding="utf-8"
                )
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = xe.cmd_run(str(eval_yaml), "gpt-4o-mini", 1, "json")
                data = json.loads(buf.getvalue())
        self.assertFalse(data["tasks"][0]["passed"])
        self.assertEqual(code, 1)

    @mock.patch("xanadEval._call_model", return_value="x" * 1000)
    def test_run_stores_full_response(self, _mock) -> None:
        """Responses longer than 800 chars must be stored untruncated for re-grading."""
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_path = self._write_eval(dp)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = xe.cmd_run(str(eval_path), "gpt-4o-mini", 1, "json")
                data = json.loads(buf.getvalue())
        self.assertIn(code, (0, 1))
        self.assertEqual(len(data["tasks"][0]["response"]), 1000)
        self.assertNotIn("\u2026", data["tasks"][0]["response"])

    @mock.patch("xanadEval._call_model", return_value="any response")
    def test_run_write_failure_returns_2(self, _mock) -> None:
        """A filesystem error during result save must return exit 2."""
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with mock.patch("os.replace", side_effect=OSError("disk full")):
                with tempfile.TemporaryDirectory() as d:
                    dp = Path(d)
                    self._write_skill(dp)
                    eval_path = self._write_eval(dp)
                    err = io.StringIO()
                    with redirect_stderr(err):
                        code = xe.cmd_run(str(eval_path), "gpt-4o-mini", 1, "text")
        self.assertEqual(code, 2)
        self.assertIn("cannot save", err.getvalue())

    def test_run_symlink_task_escape_rejected(self) -> None:
        """A task symlink pointing outside the eval directory must be rejected."""
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_path = self._write_eval(dp)
                eval_dir = eval_path.parent
                outside = dp / "secret.yaml"
                outside.write_text(json.dumps({"id": "evil", "prompt": "p"}), encoding="utf-8")
                (eval_dir / "tasks" / "link.yaml").symlink_to(outside)
                err = io.StringIO()
                with redirect_stderr(err):
                    code = xe.cmd_run(str(eval_path), "gpt-4o-mini", 1, "text")
        self.assertEqual(code, 2)
        self.assertIn("cannot load tasks", err.getvalue())


class GradeCommandTests(DynamicTestBase, unittest.TestCase):
    """Tests for cmd_grade — re-running graders on existing results."""

    def test_grade_missing_results_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            self._write_skill(dp)
            eval_path = self._write_eval(dp)
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_grade(str(eval_path), "/nonexistent/results.json", None, "text")
        self.assertEqual(code, 2)

    def test_grade_reruns_graders_and_writes_graded_at(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            self._write_skill(dp)
            eval_path = self._write_eval(dp)
            result_path = self._write_result(dp)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_grade(str(eval_path), str(result_path), None, "text")
            self.assertIn(code, (0, 1))
            updated = json.loads(result_path.read_text())
            self.assertIn("graded_at", updated)

    def test_grade_without_token_and_prompt_graders_returns_2(self) -> None:
        """cmd_grade must fail fast without touching the results file when prompt graders need a token."""
        with mock.patch.dict("os.environ", {}, clear=False):
            for key in ("GITHUB_TOKEN", "GH_TOKEN"):
                os.environ.pop(key, None)
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_dir = dp / "evals" / "test-skill"
                (eval_dir / "tasks").mkdir(parents=True)
                spec = {
                    "name": "test-skill-eval",
                    "graders": [
                        {"type": "prompt", "name": "judge", "config": {"rubric": "helpful?"}}
                    ],
                    "tasks": ["tasks/*.yaml"],
                }
                eval_yaml = eval_dir / "eval.yaml"
                eval_yaml.write_text(json.dumps(spec), encoding="utf-8")
                result_path = self._write_result(dp)
                original_content = result_path.read_text(encoding="utf-8")
                err = io.StringIO()
                with redirect_stderr(err):
                    code = xe.cmd_grade(str(eval_yaml), str(result_path), None, "text")
                self.assertEqual(code, 2)
                self.assertIn("GITHUB_TOKEN", err.getvalue())
                self.assertEqual(result_path.read_text(encoding="utf-8"), original_content)

    def test_grade_reapplies_expected_absent_from_saved_graders(self) -> None:
        """cmd_grade must re-apply expected_absent patterns persisted in the saved result."""
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_dir = dp / "evals" / "test-skill"
                (eval_dir / "tasks").mkdir(parents=True)
                spec = {
                    "name": "test-skill-eval",
                    "graders": [{"type": "text", "name": "ref", "config": {"contains": ["test"]}}],
                    "tasks": [],
                }
                eval_yaml = eval_dir / "eval.yaml"
                eval_yaml.write_text(json.dumps(spec), encoding="utf-8")
                result = {
                    "eval": str(eval_yaml),
                    "skill": "test-skill-eval",
                    "model": "gpt-4o-mini",
                    "timestamp": "2026-05-20T12:00:00Z",
                    "summary": {"total": 1, "passed": 0, "pass_rate": 0.0, "score": 0.5},
                    "tasks": [{
                        "id": "task-1",
                        "prompt": "p",
                        "response": "test contains forbidden_word here",
                        "graders": [
                            {"type": "text", "name": "ref", "pass": True, "score": 1.0},
                            {"type": "expected_absent", "name": "forbidden_word",
                             "pass": False, "score": 0.0},
                        ],
                        "passed": False,
                        "score": 0.5,
                    }],
                }
                result_path = dp / "run-result.json"
                result_path.write_text(json.dumps(result), encoding="utf-8")
                code = xe.cmd_grade(str(eval_yaml), str(result_path), None, "text")
                updated = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        absent_graders = [g for g in updated["tasks"][0]["graders"]
                          if g.get("type") == "expected_absent"]
        self.assertEqual(len(absent_graders), 1)
        self.assertFalse(absent_graders[0]["pass"])

    def test_grade_write_failure_returns_2(self) -> None:
        """A filesystem error during result save must return exit 2."""
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                self._write_skill(dp)
                eval_path = self._write_eval(dp)
                result_path = self._write_result(dp)
                err = io.StringIO()
                with redirect_stderr(err):
                    code = xe.cmd_grade(str(eval_path), str(result_path), None, "text")
        self.assertEqual(code, 2)
        self.assertIn("cannot save", err.getvalue())

    @mock.patch("xanadEval._call_model",
                return_value='{"score": 0.9, "reasoning": "good"}')
    def test_grade_cli_model_defaults_to_stored_model(self, mock_call) -> None:
        """Omitting --model from the grade CLI uses the model stored in the results file."""
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            with tempfile.TemporaryDirectory() as d:
                dp = Path(d)
                eval_dir = dp / "evals" / "test-skill"
                (eval_dir / "tasks").mkdir(parents=True)
                spec = {
                    "name": "test-skill-eval",
                    "graders": [{"type": "prompt", "name": "j",
                                 "config": {"rubric": "good?"}}],
                    "tasks": [],
                }
                eval_yaml = eval_dir / "eval.yaml"
                eval_yaml.write_text(json.dumps(spec), encoding="utf-8")
                result = {
                    "eval": str(eval_yaml),
                    "skill": "test-skill",
                    "model": "custom-stored-model",
                    "timestamp": "2026-05-20T12:00:00Z",
                    "summary": {"total": 1, "passed": 1, "pass_rate": 1.0, "score": 1.0},
                    "tasks": [{"id": "t1", "prompt": "p", "response": "r",
                               "graders": [], "passed": True, "score": 1.0}],
                }
                result_path = dp / "run.json"
                result_path.write_text(json.dumps(result), encoding="utf-8")
                xe.main(["grade", str(eval_yaml), str(result_path)])
        mock_call.assert_called()
        self.assertEqual(mock_call.call_args[0][1], "custom-stored-model")


if __name__ == "__main__":
    unittest.main()
