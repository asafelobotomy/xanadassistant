"""Tests for xanadEval static analysis commands: tokens, check, errors, yaml helpers."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xanadEval_test_support import (
    xe,
    _MINIMAL_SKILL, _NO_FRONTMATTER, _CONTENT_OVER_BUDGET,
)


class TokensCommandTests(unittest.TestCase):

    def _tokens(self, content: str, fmt: str = "text") -> tuple[str, int]:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        self.addCleanup(Path(path).unlink, missing_ok=True)
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

    def test_spec_steps_or_modules_exempt_for_reference_skill(self) -> None:
        ref_skill = "---\nname: test-skill\ntype: reference\ndescription: \"A reference skill with no procedural steps\"\n---\n\n# T\n\n## When to use\n\n- yes\n\n## When NOT to use\n\n- no\n\n## Verify\n\n- [ ] ok\n"
        output, _ = self._check(ref_skill, fmt="json")
        data = json.loads(output)
        wf_check = next(c for c in data["spec_checks"] if c["id"] == "spec-steps-or-modules")
        self.assertTrue(wf_check["pass"])
        mc_check = next(c for c in data["advisory_checks"] if c["id"] == "module-count")
        self.assertTrue(mc_check["pass"])

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
        # Indented lines inside fenced code blocks must not contribute to depth.
        self.assertEqual(xe._max_nesting_depth("# H\n\n```yaml\n  - a:\n    - b\n```\n- outer\n"), 1)


if __name__ == "__main__":
    unittest.main()
