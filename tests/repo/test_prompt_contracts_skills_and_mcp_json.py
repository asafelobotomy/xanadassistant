from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class AgenticReviewSkillContractTests(unittest.TestCase):
    SKILL_PATH = REPO_ROOT / "skills" / "agenticReview" / "SKILL.md"

    def _content(self) -> str:
        return self.SKILL_PATH.read_text(encoding="utf-8")

    def test_prompt_review_skill_file_exists(self) -> None:
        self.assertTrue(self.SKILL_PATH.exists(), "skills/agenticReview/SKILL.md must exist")

    def test_prompt_review_skill_has_required_frontmatter_fields(self) -> None:
        content = self._content()
        frontmatter = content.split("---\n", 2)[1]
        self.assertIn("name: agenticReview", frontmatter)
        self.assertIn("description:", frontmatter)

    def test_prompt_review_skill_covers_all_six_modules(self) -> None:
        content = self._content()
        self.assertIn("Module 1", content)
        self.assertIn("Module 2", content)
        self.assertIn("Module 3", content)
        self.assertIn("Module 4", content)
        self.assertIn("Module 5", content)
        self.assertIn("Module 6", content)

    def test_prompt_review_skill_names_all_six_traits(self) -> None:
        content = self._content()
        self.assertIn("Contradiction", content)
        self.assertIn("Ambiguity", content)
        self.assertIn("Persona", content)
        self.assertIn("Cognitive Load", content)
        self.assertIn("Coverage", content)
        self.assertIn("Composition", content)

    def test_prompt_review_skill_defines_finding_output_prefixes(self) -> None:
        content = self._content()
        self.assertIn("contradiction:", content)
        self.assertIn("ambiguity:", content)
        self.assertIn("persona:", content)
        self.assertIn("cognitive-load:", content)
        self.assertIn("coverage-gap:", content)
        self.assertIn("composition:", content)

    def test_prompt_review_skill_defines_severity_levels(self) -> None:
        content = self._content()
        for level in ("Critical", "High", "Medium", "Low"):
            self.assertIn(level, content)

    def test_prompt_review_skill_covers_all_four_file_types(self) -> None:
        content = self._content()
        self.assertIn(".prompt.md", content)
        self.assertIn(".agent.md", content)
        self.assertIn("SKILL.md", content)
        self.assertIn(".instructions.md", content)

    def test_prompt_review_skill_has_when_to_use_and_when_not_to_use(self) -> None:
        content = self._content()
        self.assertIn("## When to use", content)
        self.assertIn("## When NOT to use", content)

    def test_prompt_review_skill_has_verify_checklist(self) -> None:
        content = self._content()
        self.assertIn("## Verify", content)
        self.assertIn("- [ ]", content)

    def test_prompt_review_skill_composition_module_reads_imports(self) -> None:
        content = self._content()
        self.assertIn("Markdown link", content)
        self.assertIn("{{", content)

    def test_prompt_review_skill_defines_merge_decision_outcomes(self) -> None:
        content = self._content()
        self.assertIn("ready to merge", content)
        self.assertIn("needs revision before merge", content)
        self.assertIn("block", content)

    def test_prompt_review_skill_cognitive_load_module_provides_thresholds(self) -> None:
        content = self._content()
        self.assertIn("nesting depth", content)
        self.assertIn("threshold", content)

    def test_prompt_review_skill_references_xanadEval_check_command(self) -> None:
        content = self._content()
        self.assertIn("xanadEval check", content)

    def test_prompt_review_skill_integrates_quality_self_assessment(self) -> None:
        content = self._content()
        self.assertIn("LLM-as-judge", content)
        self.assertIn("Clarity", content)
        self.assertIn("Completeness", content)

    def test_prompt_review_skill_references_xanadEval_tokens_command(self) -> None:
        content = self._content()
        self.assertIn("xanadEval tokens", content)

    def test_prompt_review_skill_references_xanadEval_suggest_command(self) -> None:
        content = self._content()
        self.assertIn("xanadEval.py suggest", content)

    def test_prompt_review_skill_has_step_zero_automated_prescan(self) -> None:
        content = self._content()
        self.assertNotIn("## Step 0", content)
        self.assertNotIn("## Module 7", content)

    def test_prompt_review_skill_integrates_llm_as_judge_in_modules(self) -> None:
        content = self._content()
        self.assertIn("LLM-as-judge", content)
        self.assertNotIn("Module 7", content)

    def test_prompt_review_skill_maps_quality_dimensions_to_modules(self) -> None:
        content = self._content()
        self.assertIn("Clarity", content)
        self.assertIn("Completeness", content)
        self.assertIn("scope-precision", content)
        self.assertIn("Scope coverage", content)
        self.assertIn("Anti-patterns", content)

    def test_prompt_review_skill_verify_checklist_covers_xanadEval_steps(self) -> None:
        content = self._content()
        verify_section = content.split("## Verify", 1)[1]
        self.assertIn("xanadEval tokens", verify_section)
        self.assertIn("xanadEval check", verify_section)
        self.assertIn("LLM-as-judge", verify_section)
        self.assertNotIn("Step 0 pre-scan", verify_section)


class TemplateMcpJsonContractTests(unittest.TestCase):
    """Regression tests for template/vscode/mcp.json contract.

    Unpinned --from mcp[cli] args cause merge-json-object updates to silently
    overwrite user version pins (GitHub issue #2). All --from args must use a
    pinned specifier so that the merge result matches the user's installed state.
    """

    _PIN_RE = re.compile(r"^mcp\[cli\]==\d+\.\d+\.\d+$")

    def test_all_server_from_args_are_pinned_to_semver(self) -> None:
        mcp_json = json.loads(
            (REPO_ROOT / "template" / "vscode" / "mcp.json").read_text(encoding="utf-8")
        )
        for server_name, server_cfg in mcp_json.get("servers", {}).items():
            args = server_cfg.get("args", [])
            from_indices = [i for i, v in enumerate(args) if v == "--from"]
            for idx in from_indices:
                pkg_arg = args[idx + 1] if idx + 1 < len(args) else ""
                with self.subTest(server=server_name):
                    self.assertRegex(
                        pkg_arg,
                        self._PIN_RE,
                        f"Server '{server_name}' --from arg must be pinned (mcp[cli]==X.Y.Z), got '{pkg_arg}'",
                    )

    def test_all_servers_use_the_same_mcp_cli_version(self) -> None:
        mcp_json = json.loads(
            (REPO_ROOT / "template" / "vscode" / "mcp.json").read_text(encoding="utf-8")
        )
        pins: dict[str, str] = {}
        for server_name, server_cfg in mcp_json.get("servers", {}).items():
            args = server_cfg.get("args", [])
            from_indices = [i for i, v in enumerate(args) if v == "--from"]
            for idx in from_indices:
                pkg_arg = args[idx + 1] if idx + 1 < len(args) else ""
                if self._PIN_RE.match(pkg_arg):
                    pins[server_name] = pkg_arg

        unique_pins = set(pins.values())
        self.assertLessEqual(
            len(unique_pins),
            1,
            f"All servers must use the same mcp[cli] pin. Found multiple: {unique_pins}. Per-server: {pins}",
        )

    def test_devdocs_server_is_enabled_by_default_in_template_and_repo_workspace(self) -> None:
        template_mcp = json.loads(
            (REPO_ROOT / "template" / "vscode" / "mcp.json").read_text(encoding="utf-8")
        )
        workspace_mcp = json.loads(
            (REPO_ROOT / ".vscode" / "mcp.json").read_text(encoding="utf-8")
        )

        template_server = template_mcp.get("servers", {}).get("devDocs")
        workspace_server = workspace_mcp.get("servers", {}).get("devDocs")

        self.assertIsNotNone(template_server)
        self.assertIsNotNone(workspace_server)
        self.assertFalse(template_server.get("disabled", False))
        self.assertFalse(workspace_server.get("disabled", False))

    def test_template_and_repo_mcp_json_use_canonical_serialization(self) -> None:
        for path in (
            REPO_ROOT / "template" / "vscode" / "mcp.json",
            REPO_ROOT / ".vscode" / "mcp.json",
        ):
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                parsed = json.loads(content)
                self.assertEqual(content, json.dumps(parsed, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
