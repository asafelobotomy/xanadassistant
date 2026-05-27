"""Tests for the workspace_grade_human MCP tool."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.mcp_servers._xanad_workspace_mcp_support import XanadWorkspaceMcpTestCaseMixin


def _make_results(task_id: str, *, pending: bool = True) -> dict:
    return {
        "eval": "test.yaml",
        "tasks": [
            {
                "id": task_id,
                "prompt": "test prompt",
                "response": "test response",
                "graders": [
                    {
                        "type": "human",
                        "name": "review",
                        "pass": None,
                        "score": None,
                        "pending": pending,
                        "criteria": ["Is it clear?"],
                    }
                ],
                "passed": None,
                "score": None,
            }
        ],
    }


class WorkspaceGradeHumanTests(XanadWorkspaceMcpTestCaseMixin, unittest.TestCase):
    """Tests for tool_workspace_grade_human (backing the workspace_grade_human MCP tool)."""

    def _write_results(self, tmpdir: str, task_id: str, **kw) -> Path:
        path = Path(tmpdir) / "results.json"
        path.write_text(json.dumps(_make_results(task_id, **kw)), encoding="utf-8")
        return path

    def _call(self, module, results_path: Path, task_id: str, score: float, rationale: str = "") -> dict:
        return module.tool_workspace_grade_human(
            {"resultsPath": str(results_path), "taskId": task_id, "score": score, "rationale": rationale}
        )

    def test_patches_pending_grader(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as d:
                    results_path = self._write_results(d, "task-1")
                    with self._workspace_ready(module), mock.patch.object(
                        module, "WORKSPACE_ROOT", Path(d)
                    ):
                        result = self._call(module, results_path, "task-1", 0.8)
                    self.assertEqual(result["status"], "ok")
                    patched = json.loads(results_path.read_text())
                    g = patched["tasks"][0]["graders"][0]
                    self.assertFalse(g["pending"])
                    self.assertAlmostEqual(g["score"], 0.8)
                    self.assertTrue(g["pass"])

    def test_task_not_found_returns_failed(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as d:
                    results_path = self._write_results(d, "task-1")
                    with self._workspace_ready(module), mock.patch.object(
                        module, "WORKSPACE_ROOT", Path(d)
                    ):
                        result = self._call(module, results_path, "task-999", 0.8)
                    self.assertEqual(result["status"], "failed")

    def test_no_pending_grader_returns_failed(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as d:
                    results_path = self._write_results(d, "task-1", pending=False)
                    with self._workspace_ready(module), mock.patch.object(
                        module, "WORKSPACE_ROOT", Path(d)
                    ):
                        result = self._call(module, results_path, "task-1", 0.8)
                    self.assertEqual(result["status"], "failed")

    def test_score_clamped_high(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as d:
                    results_path = self._write_results(d, "t")
                    with self._workspace_ready(module), mock.patch.object(
                        module, "WORKSPACE_ROOT", Path(d)
                    ):
                        self._call(module, results_path, "t", 999.0)
                    g = json.loads(results_path.read_text())["tasks"][0]["graders"][0]
                    self.assertEqual(g["score"], 1.0)

    def test_score_clamped_low(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as d:
                    results_path = self._write_results(d, "t")
                    with self._workspace_ready(module), mock.patch.object(
                        module, "WORKSPACE_ROOT", Path(d)
                    ):
                        self._call(module, results_path, "t", -5.0)
                    g = json.loads(results_path.read_text())["tasks"][0]["graders"][0]
                    self.assertEqual(g["score"], 0.0)
                    self.assertFalse(g["pass"])

    def test_rationale_stored(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as d:
                    results_path = self._write_results(d, "t")
                    with self._workspace_ready(module), mock.patch.object(
                        module, "WORKSPACE_ROOT", Path(d)
                    ):
                        self._call(module, results_path, "t", 0.7, "looked good")
                    g = json.loads(results_path.read_text())["tasks"][0]["graders"][0]
                    self.assertEqual(g["rationale"], "looked good")

    def test_workspace_not_valid_returns_unavailable(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with mock.patch.object(module, "workspace_root_valid", return_value=False):
                    result = module.tool_workspace_grade_human(
                        {"resultsPath": "any.json", "taskId": "task-1", "score": 1.0, "rationale": ""}
                    )
                self.assertEqual(result["status"], "unavailable")

    def test_nonexistent_file_returns_unavailable(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as d:
                    with self._workspace_ready(module), mock.patch.object(
                        module, "WORKSPACE_ROOT", Path(d)
                    ):
                        result = module.tool_workspace_grade_human({
                            "resultsPath": str(Path(d) / "missing.json"),
                            "taskId": "task-1", "score": 1.0, "rationale": "",
                        })
                self.assertEqual(result["status"], "unavailable")

    def test_task_score_re_aggregated_after_patch(self) -> None:
        """Task-level score is re-aggregated after patching the human grader."""
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as d:
                    # Two graders: text (already scored 1.0) + human (pending)
                    data = {
                        "tasks": [{
                            "id": "t",
                            "graders": [
                                {"type": "text", "name": "t", "pass": True, "score": 1.0},
                                {"type": "human", "name": "h", "pass": None,
                                 "score": None, "pending": True},
                            ],
                            "passed": None,
                            "score": None,
                        }]
                    }
                    p = Path(d) / "r.json"
                    p.write_text(json.dumps(data), encoding="utf-8")
                    with self._workspace_ready(module), mock.patch.object(
                        module, "WORKSPACE_ROOT", Path(d)
                    ):
                        module.tool_workspace_grade_human(
                            {"resultsPath": str(p), "taskId": "t", "score": 0.5, "rationale": ""}
                        )
                    task = json.loads(p.read_text())["tasks"][0]
                    self.assertAlmostEqual(task["score"], 0.75)  # (1.0 + 0.5) / 2
                    self.assertTrue(task["passed"])


if __name__ == "__main__":
    unittest.main()
