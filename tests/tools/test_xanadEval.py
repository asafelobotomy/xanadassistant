"""Tests for tools/xanadEval/xanadEval.py — the bundled static analyser."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

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
    + ("word " * (xe.TOKEN_BUDGET * xe._CHARS_PER_TOKEN + 200))
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
        for key in ("token_estimate", "sections", "workflow_steps"):
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
        for key in ("token_estimate", "token_budget", "sections", "code_blocks",
                    "workflow_steps_detected", "max_nesting_depth"):
            self.assertIn(key, data)
        self.assertEqual(data["token_budget"], xe.TOKEN_BUDGET)

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
        for item in data["spec_checks"]:
            for key in ("id", "pass", "detail"):
                self.assertIn(key, item)

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
            self.assertTrue((root / "tasks" / "basic-invocation.yaml").exists())
            self.assertIn("test-skill", (root / "eval.yaml").read_text())


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


if __name__ == "__main__":
    unittest.main()
