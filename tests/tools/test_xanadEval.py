"""Tests for tools/xanadEval/xanadEval.py — the bundled static analyser."""
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

# Resolve the tool without installing it as a package.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "tools" / "xanadEval")
)
import xanadEval as xe  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixture content
# ---------------------------------------------------------------------------

_MINIMAL_SKILL = """\
---
name: test-skill
description: "A minimal skill used for xanadEval unit tests"
---

# Test Skill

> Skill metadata: version "1.0"; tags [test].

## When to use

- When running xanadEval tests
- When verifying minimal compliance

## When NOT to use

- When not running xanadEval tests

## Module 1 — Alpha

1. Do the first thing.
2. Do the second thing.
3. Verify the result.

## Module 2 — Beta

- Rule A
- Rule B

## Verify

- [ ] All six modules run
- [ ] Findings table present
"""

_NO_FRONTMATTER = """\
# No Frontmatter File

Some content without any YAML frontmatter.
"""

_CONTENT_OVER_BUDGET = (
    "---\nname: test-skill\ndescription: \"x\"\n---\n\n"
    + ("word " * 17_000)  # ~17,000 BPE tokens — well over the 16,000-token budget
)


class TokensCommandTests(unittest.TestCase):

    def _tokens(self, content: str, fmt: str = "text") -> tuple[str, int]:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = xe.cmd_tokens(path, fmt)
        return buf.getvalue(), code

    def test_text_output_structure(self) -> None:
        output, code = self._tokens(_MINIMAL_SKILL)
        self.assertEqual(code, 0)
        for key in ("token_count", "sections", "workflow_steps"):
            self.assertIn(key, output)

    def test_workflow_detection(self) -> None:
        output, _ = self._tokens(_MINIMAL_SKILL, fmt="json")
        self.assertTrue(json.loads(output)["workflow_steps_detected"])
        prose = "---\nname: x\ndescription: \"x\"\n---\n\nProse only.\n"
        output, _ = self._tokens(prose, fmt="json")
        self.assertFalse(json.loads(output)["workflow_steps_detected"])

    def test_json_format_and_budget(self) -> None:
        output, _ = self._tokens(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        for key in ("token_count", "token_budget", "sections", "code_blocks",
                    "workflow_steps_detected", "max_nesting_depth"):
            self.assertIn(key, data)
        self.assertEqual(data["token_budget"], xe.TOKEN_BUDGET)

    def test_token_count_uses_tiktoken_when_available(self) -> None:
        """When tiktoken is installed, token_count is an exact BPE count."""
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            self.skipTest("tiktoken not installed")
        expected = len(enc.encode(_MINIMAL_SKILL))
        output, _ = self._tokens(_MINIMAL_SKILL, fmt="json")
        self.assertEqual(json.loads(output)["token_count"], expected)

    def test_code_block_count(self) -> None:
        content = _MINIMAL_SKILL + "\n```python\nprint('hi')\n```\n"
        output, _ = self._tokens(content, fmt="json")
        self.assertGreaterEqual(json.loads(output)["code_blocks"], 1)


class CheckCommandTests(unittest.TestCase):

    def _check(self, content: str, skill_name: str = "test-skill", fmt: str = "text") -> tuple[str, int]:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / skill_name
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(content, encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_check(str(p), fmt)
        return buf.getvalue(), code

    def test_exit_codes(self) -> None:
        _, code = self._check(_MINIMAL_SKILL)
        self.assertEqual(code, 0)
        self.assertNotEqual(self._check(_NO_FRONTMATTER)[1], 0)
        self.assertNotEqual(self._check(_CONTENT_OVER_BUDGET)[1], 0)
        wrong = _MINIMAL_SKILL.replace("name: test-skill", "name: other-skill")
        self.assertNotEqual(self._check(wrong, skill_name="test-skill")[1], 0)

    def test_compliance_output(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL)
        self.assertIn("compliance", output)
        output, _ = self._check(_MINIMAL_SKILL, fmt="json")
        self.assertIn(json.loads(output)["compliance"], ("High", "Medium-High"))

    def test_json_structure(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        self.assertIn("spec_checks", data)
        self.assertIn("advisory_checks", data)
        ids = {c["id"] for c in data["spec_checks"]}
        self.assertIn("spec-frontmatter", ids)
        self.assertIn("spec-steps-or-modules", ids)
        for item in data["spec_checks"]:
            for key in ("id", "pass", "detail"):
                self.assertIn(key, item)

    def test_spec_steps_or_modules_passes_on_module_sections(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        check = next(c for c in data["spec_checks"] if c["id"] == "spec-steps-or-modules")
        self.assertTrue(check["pass"])

    def test_spec_steps_or_modules_passes_on_steps_section(self) -> None:
        steps_skill = _MINIMAL_SKILL.replace("## Module 1 — Alpha", "## Steps")
        output, _ = self._check(steps_skill, fmt="json")
        data = json.loads(output)
        check = next(c for c in data["spec_checks"] if c["id"] == "spec-steps-or-modules")
        self.assertTrue(check["pass"])

    def test_spec_steps_or_modules_fails_when_absent(self) -> None:
        no_workflow = "---\nname: test-skill\ndescription: \"x\"\n---\n\n# T\n\n## When to use\n\n- yes\n\n## When NOT to use\n\n- no\n\n## Verify\n\n- [ ] ok\n"
        output, _ = self._check(no_workflow, fmt="json")
        data = json.loads(output)
        check = next(c for c in data["spec_checks"] if c["id"] == "spec-steps-or-modules")
        self.assertFalse(check["pass"])

    def test_advisory_description_quality_short_description(self) -> None:
        short_desc = _MINIMAL_SKILL.replace(
            'description: "A minimal skill used for xanadEval unit tests"',
            'description: "short"',
        )
        output, _ = self._check(short_desc, fmt="json")
        data = json.loads(output)
        dq = next(c for c in data["advisory_checks"] if c["id"] == "description-quality")
        self.assertFalse(dq["pass"])

    def test_advisory_description_quality_adequate_description(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        dq = next(c for c in data["advisory_checks"] if c["id"] == "description-quality")
        self.assertTrue(dq["pass"])

    def test_spec_dir_match_fails_on_mismatch(self) -> None:
        wrong_name = _MINIMAL_SKILL.replace("name: test-skill", "name: other-skill")
        output, _ = self._check(wrong_name, skill_name="test-skill", fmt="json")
        data = json.loads(output)
        dir_check = next(c for c in data["spec_checks"] if c["id"] == "spec-dir-match")
        self.assertFalse(dir_check["pass"])

    def test_advisory_module_count_within_range(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        mc = next(c for c in data["advisory_checks"] if c["id"] == "module-count")
        self.assertTrue(mc["pass"])

    def test_advisory_over_specificity_flag(self) -> None:
        many_rules = _MINIMAL_SKILL + "\n## Extra\n\n" + "\n".join(
            f"- Rule {i}" for i in range(11)
        ) + "\n"
        output, _ = self._check(many_rules, fmt="json")
        data = json.loads(output)
        os_check = next(c for c in data["advisory_checks"] if c["id"] == "over-specificity")
        self.assertFalse(os_check["pass"])


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


class ErrorHandlingTests(unittest.TestCase):

    def test_missing_file_exits_with_stderr_message(self) -> None:
        err_buf = io.StringIO()
        with redirect_stderr(err_buf), self.assertRaises(SystemExit) as cm:
            xe.cmd_tokens("/nonexistent/path/__no_such_file__.md", "text")
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("not found", err_buf.getvalue())

    def test_non_utf8_file_exits_with_code_2(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"\xff\xfe binary rubbish \x00\x01\x02")
            path = f.name
        try:
            err_buf = io.StringIO()
            with redirect_stderr(err_buf), self.assertRaises(SystemExit) as cm:
                xe.cmd_tokens(path, "text")
            self.assertEqual(cm.exception.code, 2)
        finally:
            Path(path).unlink(missing_ok=True)


class FrontmatterNormalisationTests(unittest.TestCase):

    def _check_codeonly(self, content: str) -> int:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_bytes(content.encode("utf-8"))
            buf = io.StringIO()
            with redirect_stdout(buf):
                return xe.cmd_check(str(p), "text")

    def test_crlf_and_bom_parsed_without_error(self) -> None:
        for variant in (_MINIMAL_SKILL.replace("\n", "\r\n"), "\ufeff" + _MINIMAL_SKILL):
            self.assertEqual(self._check_codeonly(variant), 0)


class EvalPresenceAdvisoryTests(unittest.TestCase):

    def _check_json(self, p: Path) -> dict:
        buf = io.StringIO()
        with redirect_stdout(buf):
            xe.cmd_check(str(p), "json")
        return json.loads(buf.getvalue())

    def test_eval_presence_absent_when_no_evals_dir(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "skills" / "test-skill"
            skill_dir.mkdir(parents=True)
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            data = self._check_json(p)
        ep = next(c for c in data["advisory_checks"] if c["id"] == "eval-presence")
        self.assertFalse(ep["pass"])
        self.assertIn("not found", ep["detail"])

    def test_eval_presence_passes_when_eval_yaml_exists(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "skills" / "test-skill"
            skill_dir.mkdir(parents=True)
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            eval_dir = Path(d) / "evals" / "test-skill"
            eval_dir.mkdir(parents=True)
            (eval_dir / "eval.yaml").write_text("name: test-skill-eval\n", encoding="utf-8")
            data = self._check_json(p)
        ep = next(c for c in data["advisory_checks"] if c["id"] == "eval-presence")
        self.assertTrue(ep["pass"])
        self.assertIn("found", ep["detail"])


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


class YamlStrHelperTests(unittest.TestCase):

    def test_yaml_str_escaping(self) -> None:
        self.assertEqual(xe._yaml_str("hello"), '"hello"')
        self.assertEqual(xe._yaml_str('say "hi"'), '"say \\"hi\\""')
        self.assertEqual(xe._yaml_str("line1\nline2"), '"line1\\nline2"')
        self.assertEqual(xe._yaml_str("back\\slash"), '"back\\\\slash"')
        result = xe._yaml_str("key: value")
        self.assertIn("key: value", result)


class MaxNestingDepthTests(unittest.TestCase):

    def test_nesting_depth_values(self) -> None:
        self.assertEqual(xe._max_nesting_depth("# T\n\nProse only.\n"), 0)
        self.assertEqual(xe._max_nesting_depth("# H\n\n- a\n- b\n"), 1)
        self.assertEqual(xe._max_nesting_depth("# H\n\n- a\n  - b\n"), 2)


class CompareCommandTests(unittest.TestCase):
    """Tests for cmd_compare — git-ref token diffing."""

    def _setup_git_repo(self, tmp: Path, content_v1: str, content_v2: str) -> tuple[Path, str]:
        """Create a minimal git repo with two commits; return (skill_path, baseline_ref)."""
        import subprocess as sp
        sp.run(["git", "init", str(tmp)], check=True, capture_output=True)
        sp.run(["git", "-C", str(tmp), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        sp.run(["git", "-C", str(tmp), "config", "user.name", "T"], check=True, capture_output=True)

        skill_dir = tmp / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(content_v1, encoding="utf-8")
        sp.run(["git", "-C", str(tmp), "add", "."], check=True, capture_output=True)
        sp.run(["git", "-C", str(tmp), "commit", "-m", "v1"], check=True, capture_output=True)

        # Get the commit hash of v1 (our baseline)
        result = sp.run(["git", "-C", str(tmp), "rev-parse", "HEAD"],
                        capture_output=True, text=True, check=True)
        baseline_ref = result.stdout.strip()

        # Write v2
        skill_file.write_text(content_v2, encoding="utf-8")
        return skill_file, baseline_ref

    def _compare(self, skill_file: Path, ref: str, **kwargs) -> tuple[str, int]:
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(skill_file.parent.parent.parent)  # repo root
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_compare(
                    ref=ref,
                    paths=[str(skill_file)],
                    skills=False,
                    threshold=kwargs.get("threshold"),
                    strict=kwargs.get("strict", False),
                    fmt=kwargs.get("fmt", "json"),
                )
        finally:
            os.chdir(old_cwd)
        return buf.getvalue(), code

    def test_compare_detects_growth(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1 = "---\nname: my-skill\n---\n\nShort.\n"
            v2 = v1 + "word " * 500
            skill_file, ref = self._setup_git_repo(Path(d), v1, v2)
            output, _ = self._compare(skill_file, ref, fmt="json")
        data = json.loads(output)
        entry = data["files"][0]
        self.assertGreater(entry["new_tokens"], entry["old_tokens"])
        self.assertGreater(entry["delta_pct"], 0)

    def test_compare_exits_1_when_threshold_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1 = "---\nname: my-skill\n---\n\nShort.\n"
            v2 = v1 + "word " * 500
            skill_file, ref = self._setup_git_repo(Path(d), v1, v2)
            _, code = self._compare(skill_file, ref, threshold=5, fmt="json")
        self.assertEqual(code, 1)

    def test_compare_exits_0_when_under_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1 = "---\nname: my-skill\n---\n\n" + "word " * 1000
            v2 = v1 + "word "  # trivially larger
            skill_file, ref = self._setup_git_repo(Path(d), v1, v2)
            _, code = self._compare(skill_file, ref, threshold=50, fmt="json")
        self.assertEqual(code, 0)

    def test_compare_new_file_has_null_old_tokens(self) -> None:
        """A file that doesn't exist in the ref gets status=new and null old_tokens."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            import subprocess as sp
            sp.run(["git", "init", str(tmp)], check=True, capture_output=True)
            sp.run(["git", "-C", str(tmp), "config", "user.email", "t@t.com"], check=True, capture_output=True)
            sp.run(["git", "-C", str(tmp), "config", "user.name", "T"], check=True, capture_output=True)
            # Commit a placeholder so HEAD exists
            (tmp / "README.md").write_text("hi\n")
            sp.run(["git", "-C", str(tmp), "add", "."], check=True, capture_output=True)
            sp.run(["git", "-C", str(tmp), "commit", "-m", "init"], check=True, capture_output=True)
            ref = sp.run(["git", "-C", str(tmp), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()

            skill_dir = tmp / "skills" / "my-skill"
            skill_dir.mkdir(parents=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("---\nname: my-skill\n---\n\nNew file.\n", encoding="utf-8")

            buf = io.StringIO()
            import os; old = os.getcwd(); os.chdir(tmp)
            try:
                with redirect_stdout(buf):
                    xe.cmd_compare(ref, [str(skill_file)], False, None, False, "json")
            finally:
                os.chdir(old)
        data = json.loads(buf.getvalue())
        entry = data["files"][0]
        self.assertEqual(entry["status"], "new")
        self.assertIsNone(entry["old_tokens"])

    def test_compare_no_git_repo_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            import os; old = os.getcwd(); os.chdir(d)
            try:
                err_buf = io.StringIO()
                with redirect_stderr(err_buf):
                    code = xe.cmd_compare("main", [], False, None, False, "text")
            finally:
                os.chdir(old)
        self.assertEqual(code, 2)

    def test_compare_no_paths_and_no_skills_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            err_buf = io.StringIO()
            with redirect_stderr(err_buf):
                code = xe.cmd_compare("main", [], False, None, False, "text")
        self.assertEqual(code, 2)


class ReportCommandTests(unittest.TestCase):
    """Tests for cmd_report — self-contained HTML generation."""

    def _report(self, paths: list[str], output: str | None = None) -> tuple[str, int]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = xe.cmd_report(paths, output)
        return buf.getvalue(), code

    def _make_skill_file(self, d: Path, name: str = "test-skill") -> Path:
        skill_dir = d / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        p = skill_dir / "SKILL.md"
        p.write_text(_MINIMAL_SKILL.replace("test-skill", name), encoding="utf-8")
        return p

    def test_report_writes_html_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._make_skill_file(Path(d))
            out = str(Path(d) / "report.html")
            _, code = self._report([str(p)], output=out)
            self.assertEqual(code, 0)
            self.assertTrue(Path(out).exists())

    def test_report_html_is_valid_structure(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._make_skill_file(Path(d))
            out = str(Path(d) / "report.html")
            self._report([str(p)], output=out)
            html = Path(out).read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("xanadEval Report", html)
        self.assertIn("spec-frontmatter", html)

    def test_report_embeds_json_data(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._make_skill_file(Path(d))
            out = str(Path(d) / "report.html")
            self._report([str(p)], output=out)
            html = Path(out).read_text(encoding="utf-8")
        # The data JSON is embedded in a <script> block
        self.assertIn('"spec-frontmatter"', html)
        self.assertIn('"pass"', html)

    def test_report_covers_multiple_skills(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p1 = self._make_skill_file(root, "alpha")
            p2 = self._make_skill_file(root, "beta")
            out = str(root / "report.html")
            _, code = self._report([str(p1), str(p2)], output=out)
            html = Path(out).read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertIn("alpha", html)
        self.assertIn("beta", html)

    def test_report_default_output_filename(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._make_skill_file(Path(d))
            import os; old = os.getcwd(); os.chdir(d)
            try:
                _, code = self._report([str(p)], output=None)
                self.assertEqual(code, 0)
                self.assertTrue((Path(d) / "xanadEval-report.html").exists())
            finally:
                os.chdir(old)

    def test_report_empty_paths_returns_1(self) -> None:
        err_buf = io.StringIO()
        with redirect_stderr(err_buf):
            code = xe.cmd_report([], None)
        self.assertEqual(code, 1)

    def test_report_via_main(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._make_skill_file(Path(d))
            out = str(Path(d) / "report.html")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.main(["report", str(p), "--output", out])
            self.assertEqual(code, 0)
            self.assertTrue(Path(out).exists())

    def test_report_script_injection_escaped(self) -> None:
        """Data embedded in the <script> block must not contain raw </script>."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            skill_dir = root / "skills" / "test-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            evil = _MINIMAL_SKILL.replace(
                "name: test-skill",
                'name: "test</script><script>alert(1)</script>"',
            )
            p = skill_dir / "SKILL.md"
            p.write_text(evil, encoding="utf-8")
            out = str(root / "report.html")
            with redirect_stdout(io.StringIO()):
                xe.cmd_report([str(p)], output=out)
            html = Path(out).read_text(encoding="utf-8")
        # The injection sequence must not appear raw in the embedded script block
        self.assertNotIn("</script><script>alert", html)

# Shared mock reply for quality/dev scoring
_MOCK_QUALITY_REPLY = (
    '{"clarity": 0.8, "completeness": 0.9, "trigger_precision": 0.7, '
    '"scope_coverage": 0.8, "anti_patterns": 0.9, "overall": 0.82, '
    '"summary": "Good skill with minor gaps."}'
)

_MOCK_DEV_REPLY = (
    '{"clarity": 0.6, "completeness": 0.7, "trigger_precision": 0.5, '
    '"scope_coverage": 0.6, "anti_patterns": 0.8, "overall": 0.64, '
    '"improvements": ["Add examples", "Tighten triggers", "Add Verify section"], '
    '"summary": "Needs clearer trigger phrases."}'
)


class DynamicAnalysisTests(unittest.TestCase):
    """Tests for GitHub Models-backed commands.

    All tests that call the model mock _call_model; no real API calls are made.
    """

    # ── fixture helpers ──────────────────────────────────────────────────────

    def _write_skill(self, d: Path, name: str = "test-skill") -> Path:
        skill_dir = d / "skills" / name
        skill_dir.mkdir(parents=True)
        p = skill_dir / "SKILL.md"
        p.write_text(_MINIMAL_SKILL, encoding="utf-8")
        return p

    def _write_eval(self, d: Path, name: str = "test-skill") -> Path:
        """Write a JSON-format eval spec (valid JSON is also valid YAML)."""
        eval_dir = d / "evals" / name
        (eval_dir / "tasks").mkdir(parents=True)
        spec = {
            "name": f"{name}-eval",
            "graders": [
                {"type": "text", "name": "ref_skill", "config": {"contains": ["test"]}}
            ],
            "tasks": ["tasks/*.yaml"],
        }
        eval_yaml = eval_dir / "eval.yaml"
        eval_yaml.write_text(json.dumps(spec), encoding="utf-8")
        task = {"id": "task-1", "prompt": "Tell me about test-skill"}
        (eval_dir / "tasks" / "t1.yaml").write_text(json.dumps(task), encoding="utf-8")
        return eval_yaml

    def _write_result(self, d: Path, name: str = "run", pass_rate: float = 1.0) -> Path:
        result = {
            "eval": "evals/test-skill/eval.yaml",
            "skill": "test-skill",
            "model": "gpt-4o-mini",
            "timestamp": "2026-05-20T12:00:00Z",
            "summary": {
                "total": 1, "passed": int(pass_rate), "pass_rate": pass_rate,
                "score": pass_rate,
            },
            "tasks": [{
                "id": "task-1",
                "prompt": "test prompt",
                "response": "response mentioning test skill",
                "graders": [{"type": "text", "name": "ref_skill", "pass": True, "score": 1.0}],
                "passed": pass_rate == 1.0,
                "score": pass_rate,
            }],
        }
        p = d / f"{name}-result.json"
        p.write_text(json.dumps(result), encoding="utf-8")
        return p

    def _skill_tmpfile(self) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(_MINIMAL_SKILL)
            return f.name

    # ── grader unit tests (no API) ───────────────────────────────────────────

    def test_grade_text_matches_pattern(self) -> None:
        self.assertTrue(xe._grade_text("response about skills", {"pattern": "(?i)skill"}))
        self.assertFalse(xe._grade_text("response about topics", {"pattern": "(?i)skill"}))

    def test_grade_text_matches_contains(self) -> None:
        self.assertTrue(xe._grade_text("Hello world", {"contains": ["world"]}))
        self.assertFalse(xe._grade_text("Hello world", {"contains": ["missing"]}))

    def test_grade_text_no_criteria_passes(self) -> None:
        self.assertTrue(xe._grade_text("anything", {}))

    def test_grade_behavior_checks_token_budget(self) -> None:
        long_response = "word " * 500
        self.assertFalse(xe._grade_behavior(long_response, {"max_tokens": 10}))
        self.assertTrue(xe._grade_behavior("ok", {"max_tokens": 10000}))

    def test_grade_behavior_no_max_tokens_passes(self) -> None:
        self.assertTrue(xe._grade_behavior("anything", {"max_tool_calls": 5}))

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

    # ── quality ──────────────────────────────────────────────────────────────

    def test_quality_requires_token(self) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {}, clear=False):
            for key in ("GITHUB_TOKEN", "GH_TOKEN"):
                os.environ.pop(key, None)
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_quality(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 2)
        self.assertIn("GITHUB_TOKEN", err.getvalue())

    @mock.patch("xanadEval._call_model", return_value=_MOCK_QUALITY_REPLY)
    def test_quality_text_output(self, _mock) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_quality(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("clarity", out)
        self.assertIn("overall", out)

    @mock.patch("xanadEval._call_model", return_value=_MOCK_QUALITY_REPLY)
    def test_quality_json_output(self, _mock) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_quality(path, "gpt-4o-mini", "json")
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("scores", data)
        self.assertIn("clarity", data["scores"])

    @mock.patch("xanadEval._call_model", return_value="I cannot provide scores.")
    def test_quality_bad_model_response_returns_1(self, _mock) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_quality(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 1)

    # ── dev ──────────────────────────────────────────────────────────────────

    def test_dev_requires_token(self) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {}, clear=False):
            for key in ("GITHUB_TOKEN", "GH_TOKEN"):
                os.environ.pop(key, None)
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_dev(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 2)

    @mock.patch("xanadEval._call_model", return_value=_MOCK_DEV_REPLY)
    def test_dev_surfaces_improvements(self, _mock) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_dev(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("improvements", out)
        self.assertIn("Add examples", out)

    # ── run ──────────────────────────────────────────────────────────────────

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

    # ── grade ─────────────────────────────────────────────────────────────────

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

    # ── results list / view / compare ─────────────────────────────────────────

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

    # ── multi-trial aggregation ─────────────────────────────────────────────────────

    @mock.patch("xanadEval._call_model")
    def test_multi_trial_aggregates_all_responses(self, mock_call) -> None:
        """trials=2 should grade every response, not just responses[0]."""
        # First trial passes text grader (contains "test"); second does not
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
        # 1 pass out of 2 trials → majority fails (1 > 1.0 is False)
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


if __name__ == "__main__":
    unittest.main()
