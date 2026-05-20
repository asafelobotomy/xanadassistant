"""Tests for xanadEval generation commands: suggest, coverage, main entrypoint, security."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xanadEval_test_support import xe, _MINIMAL_SKILL


class SuggestCommandTests(unittest.TestCase):

    def test_dry_run_outputs_eval_yaml_content(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_suggest(str(p), dry_run=True)
        output = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("eval.yaml", output)
        self.assertIn("test-skill", output)
        self.assertIn("tasks", output)

    def test_dry_run_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                xe.cmd_suggest(str(p), dry_run=True)
            eval_yaml = Path(d) / "evals" / "test-skill" / "eval.yaml"
            self.assertFalse(eval_yaml.exists())

    def test_apply_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "skills" / "test-skill"
            skill_dir.mkdir(parents=True)
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                xe.cmd_suggest(str(p), dry_run=False)
            root = Path(d) / "evals" / "test-skill"
            self.assertTrue((root / "eval.yaml").exists())
            self.assertTrue((root / "tasks" / "positive-trigger-1.yaml").exists())
            self.assertTrue((root / "tasks" / "negative-trigger-1.yaml").exists())
            self.assertIn("test-skill", (root / "eval.yaml").read_text())

    def test_suggest_generates_behavior_grader(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                xe.cmd_suggest(str(p), dry_run=True)
        output = buf.getvalue()
        self.assertIn("behavior", output)
        self.assertIn("max_tokens", output)

    def test_suggest_generates_negative_trigger_task(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                xe.cmd_suggest(str(p), dry_run=True)
        output = buf.getvalue()
        self.assertIn("negative-trigger-1", output)
        self.assertIn("negative", output)

    def test_suggest_dry_run_outside_skills_warns(self) -> None:
        """--dry-run must emit a layout warning when SKILL.md is not under skills/."""
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            err = io.StringIO()
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err):
                code = xe.cmd_suggest(str(p), dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("skills", err.getvalue())
        self.assertIn("eval.yaml", buf.getvalue())

    def test_suggest_apply_write_failure_returns_2(self) -> None:
        """An OSError writing eval scaffold files returns exit 2."""
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "skills" / "test-skill"
            skill_dir.mkdir(parents=True)
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            with mock.patch.object(Path, "write_text",
                                   side_effect=OSError("disk full")):
                err_buf = io.StringIO()
                with redirect_stderr(err_buf):
                    code = xe.cmd_suggest(str(p), dry_run=False)
        self.assertEqual(code, 2)
        self.assertIn("cannot write", err_buf.getvalue())


class MainEntrypointTests(unittest.TestCase):

    def _run_main(self, argv: list[str]) -> tuple[str, int]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = xe.main(argv)
        return buf.getvalue(), code

    def test_tokens_subcommand_via_main(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(_MINIMAL_SKILL)
            path = f.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
        _, code = self._run_main(["tokens", path])
        self.assertEqual(code, 0)

    def test_suggest_dry_run_via_main(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            output, code = self._run_main(["suggest", "--dry-run", str(p)])
        self.assertEqual(code, 0)
        self.assertIn("eval.yaml", output)

    def test_format_flag_accepted_after_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            output, code = self._run_main(["check", str(p), "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIn("compliance", data)

    def test_format_flag_before_subcommand_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            output, code = self._run_main(["--format", "json", "check", str(p)])
        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIn("compliance", data)


class SuggestSecurityTests(unittest.TestCase):

    def _suggest_apply(self, name_value: str) -> int:
        dangerous = _MINIMAL_SKILL.replace("name: test-skill", f"name: {name_value}")
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(dangerous, encoding="utf-8")
            buf = io.StringIO()
            err_buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err_buf):
                return xe.cmd_suggest(str(p), dry_run=False)

    def test_dotdot_name_rejected(self) -> None:
        self.assertEqual(self._suggest_apply("../evil"), 2)

    def test_slash_in_name_rejected(self) -> None:
        self.assertEqual(self._suggest_apply("a/b"), 2)

    def test_backslash_in_name_rejected(self) -> None:
        self.assertEqual(self._suggest_apply("a\\\\b"), 2)

    def test_dot_prefix_rejected(self) -> None:
        self.assertEqual(self._suggest_apply(".hidden"), 2)


class CoverageCommandTests(unittest.TestCase):

    def _make_skill(self, root: Path, skill_name: str, content: str | None = None) -> Path:
        skill_dir = root / "skills" / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        p = skill_dir / "SKILL.md"
        p.write_text(content or _MINIMAL_SKILL.replace("test-skill", skill_name), encoding="utf-8")
        return p

    def _make_eval(self, root: Path, skill_name: str, task_count: int = 1) -> None:
        eval_dir = root / "evals" / skill_name
        (eval_dir / "tasks").mkdir(parents=True, exist_ok=True)
        (eval_dir / "eval.yaml").write_text(f"name: {skill_name}-eval\n", encoding="utf-8")
        for i in range(task_count):
            (eval_dir / "tasks" / f"task-{i}.yaml").write_text(f"id: t{i}\n", encoding="utf-8")

    def _coverage(self, root: Path, fmt: str = "text") -> tuple[str, int]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = xe.cmd_coverage(str(root), fmt)
        return buf.getvalue(), code

    def test_coverage_returns_1_when_any_skill_missing_eval(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._make_skill(root, "alpha")
            _, code = self._coverage(root)
        self.assertEqual(code, 1)

    def test_coverage_returns_0_when_all_skills_covered(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._make_skill(root, "alpha")
            self._make_eval(root, "alpha", task_count=1)
            _, code = self._coverage(root)
        self.assertEqual(code, 0)

    def test_coverage_partial_when_eval_yaml_present_but_no_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._make_skill(root, "alpha")
            eval_dir = root / "evals" / "alpha"
            eval_dir.mkdir(parents=True)
            (eval_dir / "eval.yaml").write_text("name: alpha-eval\n", encoding="utf-8")
            output, _ = self._coverage(root, fmt="json")
        data = json.loads(output)
        alpha = next(s for s in data["skills"] if s["name"] == "alpha")
        self.assertEqual(alpha["status"], "partial")

    def test_coverage_json_structure(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._make_skill(root, "alpha")
            self._make_skill(root, "beta")
            self._make_eval(root, "alpha", task_count=2)
            output, _ = self._coverage(root, fmt="json")
        data = json.loads(output)
        for key in ("total", "covered", "partial", "missing", "coverage_pct", "skills"):
            self.assertIn(key, data)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["covered"], 1)
        self.assertEqual(data["missing"], 1)

    def test_coverage_empty_root_exits_1_with_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            err_buf = io.StringIO()
            with redirect_stderr(err_buf):
                code = xe.cmd_coverage(d, "text")
        self.assertEqual(code, 1)
        self.assertIn("no SKILL.md", err_buf.getvalue())

    def test_coverage_via_main(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._make_skill(root, "alpha")
            self._make_eval(root, "alpha", task_count=1)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.main(["coverage", str(root)])
        self.assertEqual(code, 0)
        self.assertIn("alpha", buf.getvalue())

    def test_coverage_counts_inline_tasks(self) -> None:
        """Inline dict tasks in the eval spec must be counted (not only *.yaml files)."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._make_skill(root, "alpha")
            eval_dir = root / "evals" / "alpha"
            eval_dir.mkdir(parents=True)
            spec = {
                "name": "alpha-eval",
                "tasks": [
                    {"id": "t1", "prompt": "p1"},
                    {"id": "t2", "prompt": "p2"},
                ],
            }
            (eval_dir / "eval.yaml").write_text(json.dumps(spec), encoding="utf-8")
            output, code = self._coverage(root, fmt="json")
        data = json.loads(output)
        alpha = next(s for s in data["skills"] if s["name"] == "alpha")
        self.assertEqual(alpha["task_count"], 2)
        self.assertEqual(alpha["status"], "covered")
        self.assertEqual(code, 0)

    def test_coverage_counts_json_task_files(self) -> None:
        """Tasks referenced via a glob (*.json) must be counted, not only *.yaml files."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._make_skill(root, "alpha")
            eval_dir = root / "evals" / "alpha"
            (eval_dir / "tasks").mkdir(parents=True)
            spec = {
                "name": "alpha-eval",
                "tasks": ["tasks/*.json"],
            }
            (eval_dir / "eval.yaml").write_text(json.dumps(spec), encoding="utf-8")
            (eval_dir / "tasks" / "t1.json").write_text(
                json.dumps({"id": "t1", "prompt": "p"}), encoding="utf-8"
            )
            output, code = self._coverage(root, fmt="json")
        data = json.loads(output)
        alpha = next(s for s in data["skills"] if s["name"] == "alpha")
        self.assertEqual(alpha["task_count"], 1)
        self.assertEqual(alpha["status"], "covered")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
