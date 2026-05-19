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
    """cmd_tokens produces correct structural metrics."""

    def _tokens(
        self, content: str, fmt: str = "text"
    ) -> tuple[str, int]:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = xe.cmd_tokens(path, fmt)
        return buf.getvalue(), code

    def test_exits_zero(self) -> None:
        _, code = self._tokens(_MINIMAL_SKILL)
        self.assertEqual(code, 0)

    def test_text_output_contains_token_estimate(self) -> None:
        output, _ = self._tokens(_MINIMAL_SKILL)
        self.assertIn("token_estimate", output)

    def test_text_output_contains_sections(self) -> None:
        output, _ = self._tokens(_MINIMAL_SKILL)
        self.assertIn("sections", output)

    def test_text_output_contains_workflow_status(self) -> None:
        output, _ = self._tokens(_MINIMAL_SKILL)
        self.assertIn("workflow_steps", output)

    def test_workflow_detected_for_numbered_list(self) -> None:
        output, _ = self._tokens(_MINIMAL_SKILL, fmt="json")
        self.assertTrue(json.loads(output)["workflow_steps_detected"])

    def test_workflow_not_detected_for_prose(self) -> None:
        prose = (
            "---\nname: x\ndescription: \"x\"\n---\n\n"
            "Some prose only. No numbered steps here.\n"
        )
        output, _ = self._tokens(prose, fmt="json")
        self.assertFalse(json.loads(output)["workflow_steps_detected"])

    def test_json_format_has_all_required_keys(self) -> None:
        output, _ = self._tokens(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        for key in (
            "token_estimate",
            "token_budget",
            "sections",
            "code_blocks",
            "workflow_steps_detected",
            "max_nesting_depth",
        ):
            self.assertIn(key, data)

    def test_token_budget_constant_present_in_json(self) -> None:
        output, _ = self._tokens(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        self.assertEqual(data["token_budget"], xe.TOKEN_BUDGET)

    def test_code_block_count(self) -> None:
        with_blocks = _MINIMAL_SKILL + "\n```python\nprint('hi')\n```\n"
        output, _ = self._tokens(with_blocks, fmt="json")
        self.assertGreaterEqual(json.loads(output)["code_blocks"], 1)


class CheckCommandTests(unittest.TestCase):
    """cmd_check reports compliance and exits correctly."""

    def _check(
        self, content: str, skill_name: str = "test-skill", fmt: str = "text"
    ) -> tuple[str, int]:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / skill_name
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(content, encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_check(str(p), fmt)
        return buf.getvalue(), code

    def test_exits_zero_for_valid_skill(self) -> None:
        _, code = self._check(_MINIMAL_SKILL)
        self.assertEqual(code, 0)

    def test_exits_nonzero_for_missing_frontmatter(self) -> None:
        _, code = self._check(_NO_FRONTMATTER)
        self.assertNotEqual(code, 0)

    def test_exits_nonzero_for_token_budget_violation(self) -> None:
        _, code = self._check(_CONTENT_OVER_BUDGET)
        self.assertNotEqual(code, 0)

    def test_exits_nonzero_for_name_dir_mismatch(self) -> None:
        wrong_name = _MINIMAL_SKILL.replace("name: test-skill", "name: other-skill")
        _, code = self._check(wrong_name, skill_name="test-skill")
        self.assertNotEqual(code, 0)

    def test_output_contains_compliance_level(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL)
        self.assertIn("compliance", output)

    def test_compliance_high_for_valid_skill(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        self.assertIn(data["compliance"], ("High", "Medium-High"))

    def test_json_has_spec_and_advisory_checks(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        self.assertIn("spec_checks", data)
        self.assertIn("advisory_checks", data)

    def test_json_spec_checks_have_required_fields(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        for item in data["spec_checks"]:
            self.assertIn("id", item)
            self.assertIn("pass", item)
            self.assertIn("detail", item)

    def test_spec_frontmatter_id_present(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL, fmt="json")
        ids = {c["id"] for c in json.loads(output)["spec_checks"]}
        self.assertIn("spec-frontmatter", ids)

    def test_spec_dir_match_fails_on_mismatch(self) -> None:
        wrong_name = _MINIMAL_SKILL.replace("name: test-skill", "name: other-skill")
        output, _ = self._check(wrong_name, skill_name="test-skill", fmt="json")
        data = json.loads(output)
        dir_check = next(
            c for c in data["spec_checks"] if c["id"] == "spec-dir-match"
        )
        self.assertFalse(dir_check["pass"])

    def test_advisory_module_count_within_range(self) -> None:
        output, _ = self._check(_MINIMAL_SKILL, fmt="json")
        data = json.loads(output)
        mc = next(
            c for c in data["advisory_checks"] if c["id"] == "module-count"
        )
        self.assertTrue(mc["pass"])

    def test_advisory_over_specificity_flag(self) -> None:
        # 11 bullet points in a single section triggers over-specificity
        many_rules = _MINIMAL_SKILL + "\n## Extra\n\n" + "\n".join(
            f"- Rule {i}" for i in range(11)
        ) + "\n"
        output, _ = self._check(many_rules, fmt="json")
        data = json.loads(output)
        os_check = next(
            c for c in data["advisory_checks"] if c["id"] == "over-specificity"
        )
        self.assertFalse(os_check["pass"])


class SuggestCommandTests(unittest.TestCase):
    """cmd_suggest produces eval YAML scaffold."""

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

    def test_apply_writes_eval_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skills_dir = Path(d) / "skills"
            skill_dir = skills_dir / "test-skill"
            skill_dir.mkdir(parents=True)
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                xe.cmd_suggest(str(p), dry_run=False)
            eval_yaml = Path(d) / "evals" / "test-skill" / "eval.yaml"
            self.assertTrue(eval_yaml.exists(), "eval.yaml should be written")

    def test_apply_writes_task_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skills_dir = Path(d) / "skills"
            skill_dir = skills_dir / "test-skill"
            skill_dir.mkdir(parents=True)
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                xe.cmd_suggest(str(p), dry_run=False)
            task_yaml = (
                Path(d)
                / "evals"
                / "test-skill"
                / "tasks"
                / "basic-invocation.yaml"
            )
            self.assertTrue(task_yaml.exists(), "basic-invocation.yaml should be written")

    def test_apply_eval_yaml_contains_skill_name(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skills_dir = Path(d) / "skills"
            skill_dir = skills_dir / "test-skill"
            skill_dir.mkdir(parents=True)
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                xe.cmd_suggest(str(p), dry_run=False)
            content = (Path(d) / "evals" / "test-skill" / "eval.yaml").read_text()
            self.assertIn("test-skill", content)


class MainEntrypointTests(unittest.TestCase):
    """main() argv dispatch works end-to-end."""

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

    def test_check_subcommand_via_main_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            output, _ = self._run_main(["--format", "json", "check", str(p)])
        data = json.loads(output)
        self.assertIn("compliance", data)

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
    """_read() exits cleanly on bad or missing input."""

    def test_missing_file_exits_with_code_2(self) -> None:
        err_buf = io.StringIO()
        with redirect_stderr(err_buf), self.assertRaises(SystemExit) as cm:
            xe.cmd_tokens("/nonexistent/path/__no_such_file__.md", "text")
        self.assertEqual(cm.exception.code, 2)

    def test_missing_file_prints_to_stderr(self) -> None:
        err_buf = io.StringIO()
        with redirect_stderr(err_buf), self.assertRaises(SystemExit):
            xe.cmd_tokens("/nonexistent/path/__no_such_file__.md", "text")
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
    """CRLF and BOM content is parsed without error."""

    def _check_codeonly(self, content: str) -> int:
        with tempfile.TemporaryDirectory() as d:
            skill_dir = Path(d) / "test-skill"
            skill_dir.mkdir()
            p = skill_dir / "SKILL.md"
            p.write_bytes(content.encode("utf-8"))
            buf = io.StringIO()
            with redirect_stdout(buf):
                return xe.cmd_check(str(p), "text")

    def test_crlf_frontmatter_is_parsed_correctly(self) -> None:
        crlf = _MINIMAL_SKILL.replace("\n", "\r\n")
        code = self._check_codeonly(crlf)
        self.assertEqual(code, 0)

    def test_bom_prefixed_content_is_parsed_correctly(self) -> None:
        bom = "\ufeff" + _MINIMAL_SKILL
        code = self._check_codeonly(bom)
        self.assertEqual(code, 0)


class EvalPresenceAdvisoryTests(unittest.TestCase):
    """eval-presence advisory reflects filesystem state."""

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
    """suggest rejects unsafe frontmatter names."""

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
    """_yaml_str() escapes values correctly."""

    def test_plain_string(self) -> None:
        self.assertEqual(xe._yaml_str("hello"), '"hello"')

    def test_double_quote_escaped(self) -> None:
        self.assertEqual(xe._yaml_str('say "hi"'), '"say \\"hi\\""')

    def test_colon_is_included(self) -> None:
        result = xe._yaml_str("key: value")
        self.assertTrue(result.startswith('"'))
        self.assertTrue(result.endswith('"'))
        self.assertIn("key: value", result)

    def test_newline_escaped(self) -> None:
        self.assertEqual(xe._yaml_str("line1\nline2"), '"line1\\nline2"')

    def test_backslash_escaped(self) -> None:
        self.assertEqual(xe._yaml_str("back\\slash"), '"back\\\\slash"')


class MaxNestingDepthTests(unittest.TestCase):
    """_max_nesting_depth() returns correct values including 0 for no-list files."""

    def test_returns_zero_for_no_list_content(self) -> None:
        prose = "# Title\n\nSome paragraph text. No lists here.\n"
        self.assertEqual(xe._max_nesting_depth(prose), 0)

    def test_returns_one_for_top_level_only(self) -> None:
        content = "# H\n\n- item a\n- item b\n"
        self.assertEqual(xe._max_nesting_depth(content), 1)

    def test_returns_two_for_one_level_nested(self) -> None:
        content = "# H\n\n- item\n  - nested\n"
        self.assertEqual(xe._max_nesting_depth(content), 2)


if __name__ == "__main__":
    unittest.main()
