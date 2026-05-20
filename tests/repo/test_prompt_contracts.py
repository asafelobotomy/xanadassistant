from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class PromptContractTests(unittest.TestCase):
    def test_commit_agent_does_not_reference_undeclared_git_tools(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        frontmatter, body = content.split("---\n", 2)[1:]
        match = re.search(r"^tools:\s*(\[[^\n]+\])$", frontmatter, re.MULTILINE)
        self.assertIsNotNone(match)
        declared_tools = {
            token.strip()
            for token in match.group(1).strip("[]").split(",")
            if token.strip()
        }
        referenced_git_tools = set(re.findall(r"\bgit_[a-z0-9_]+\b", body))
        undeclared = referenced_git_tools - declared_tools
        self.assertEqual(
            undeclared,
            set(),
            f"Commit agent references undeclared git tools: {sorted(undeclared)}",
        )

    def test_commit_agent_prefers_git_mcp_for_opening_inspection(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("Prefer `git_status`", content)
        self.assertIn("`git_diff_staged_stat`", content)
        self.assertIn("`git_diff_unstaged_stat`", content)

    def test_commit_agent_prefers_git_mcp_for_selective_unstage_and_stash_actions(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("Prefer `git_reset`", content)
        self.assertIn("`git_stash_apply`", content)
        self.assertIn("`git_stash_drop`", content)

    def test_commit_agent_prefers_git_mcp_for_exact_tag_push(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("Prefer `git_push_tag`", content)

    def test_commit_agent_prefers_git_mcp_for_straightforward_pushes(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("Prefer `git_push`", content)

    def test_commit_agent_prefers_git_mcp_for_noninteractive_commit_and_rebase(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("Prefer `git_commit`", content)
        self.assertIn("Prefer `git_rebase`", content)

    def test_commit_agent_prefers_structured_stash_mutation_tools(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("structured envelope", content)
        self.assertIn("`git_stash_apply`", content)
        self.assertIn("`git_stash_drop`", content)

    def test_commit_agent_consumes_structured_push_and_rebase_fields(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("`status`", content)
        self.assertIn("`summary`", content)
        self.assertIn("`stderr`", content)
        self.assertIn("failed `git_push`", content)
        self.assertIn("failed `git_rebase`", content)

    def test_commit_agent_prefers_structured_pull_results(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("Prefer `git_pull`", content)
        self.assertIn("failed `git_pull`", content)

    def test_commit_agent_prefers_git_mcp_for_fetch_branch_and_stash_workflows(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")

        self.assertIn("Prefer `git_fetch`", content)
        self.assertIn("Prefer `git_create_branch`", content)
        self.assertIn("Prefer `git_checkout`", content)
        self.assertIn("Prefer `git_delete_branch`", content)
        self.assertIn("Prefer `git_stash`", content)
        self.assertIn("Prefer `git_stash_pop`", content)

    def test_commit_agent_prefers_git_log_and_diff_for_inspection(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("Prefer `git_log`", content)
        self.assertIn("`git_diff_unstaged`", content)
        self.assertIn("`git_diff_staged`", content)

    def test_commit_agent_prefers_git_add_for_staging(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("`git_add`", content)

    def test_commit_agent_requires_showing_full_message_in_approval_prompt(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        # The agent must instruct that the full proposed message is shown verbatim
        # before the user approves — either via the legacy phrasing or the current one.
        shows_verbatim = (
            "include the exact proposed commit subject and body verbatim" in content
            or "full proposed commit message" in content
        )
        self.assertTrue(shows_verbatim, "commit.agent.md must require showing the full message verbatim")
        self.assertTrue(
            "before answering" in content or "Do not commit without acknowledgement" in content,
            "commit.agent.md must require acknowledgement before committing",
        )

    def test_repo_copilot_instructions_use_canonical_preflight_before_commit(self) -> None:
        instruction_paths = [
            REPO_ROOT / "template" / "copilot-instructions.md",
            REPO_ROOT / ".github" / "copilot-instructions.md",
        ]

        for instruction_path in instruction_paths:
            with self.subTest(path=instruction_path):
                content = instruction_path.read_text(encoding="utf-8")
                self.assertIn("python3 scripts/drift_preflight.py", content)
                self.assertIn("before commit", content.lower())

    def test_template_prompts_use_serialized_plan_setup_flow(self) -> None:
        prompt_paths = [
            REPO_ROOT / "template" / "prompts" / "bootstrap.md",
            REPO_ROOT / "template" / "prompts" / "setup.md",
        ]
        for prompt_path in prompt_paths:
            with self.subTest(prompt=prompt_path.name):
                content = prompt_path.read_text(encoding="utf-8")
                self.assertIn("--plan-out", content)
                self.assertIn("--plan .xanadAssistant/tmp/setup-plan.json", content)
                self.assertRegex(content, re.compile(r"(xanadAssistant|xanadBootstrap)\.py setup \\\n(?:.+\\\n)*\s+--plan \.xanadAssistant/tmp/setup-plan\.json"))
                self.assertNotRegex(content, re.compile(r"(xanadAssistant|xanadBootstrap)\.py apply \\\n(?:.+\\\n)*\s+--answers "))

    def test_readme_uses_serialized_plan_setup_flow(self) -> None:
        content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("--plan-out .xanadAssistant/tmp/setup-plan.json", content)
        self.assertIn("--plan .xanadAssistant/tmp/setup-plan.json --json", content)
        self.assertIn("xanadBootstrap.py setup --workspace . \\", content)
        self.assertNotRegex(content, re.compile(r"xanadBootstrap.py apply \\\n(?:.+\\\n)*\s+--answers "))

    def test_active_docs_do_not_teach_apply_as_supported_command(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        cli_surface = (REPO_ROOT / "docs" / "contracts" / "cli-surface.md").read_text(encoding="utf-8")
        self.assertNotIn("| `update` | Inspect + plan + apply in one step. |", readme)
        self.assertNotIn("| `repair` | Inspect + repair plan + apply in one step. |", readme)
        self.assertNotIn("4. Run `apply`", readme)
        self.assertNotIn("approved apply through one top-level command", cli_surface)
        self.assertNotIn("Writes a serialized lifecycle plan for later apply.", cli_surface)

    def test_cli_surface_documents_health_check_command(self) -> None:
        cli_surface = (REPO_ROOT / "docs" / "contracts" / "cli-surface.md").read_text(encoding="utf-8")

        self.assertIn("- `health-check`", cli_surface)
        self.assertIn("`health-check`", cli_surface)
        self.assertIn("Collects a workspace health check report for maintainers.", cli_surface)

    def test_readme_and_protocol_document_agent_follow_up_customization(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        protocol = (REPO_ROOT / "docs" / "contracts" / "lifecycle-protocol.md").read_text(encoding="utf-8")

        self.assertIn("installed-agent follow-up knobs", readme)
        self.assertIn("agent customization answers", readme)
        self.assertIn("inspect.result.agentCustomization", protocol)
        self.assertIn("authoritative replay store", protocol)

    def test_setup_and_bootstrap_prompts_document_agent_follow_up_batch(self) -> None:
        prompt_paths = [
            REPO_ROOT / "template" / "prompts" / "bootstrap.md",
            REPO_ROOT / "template" / "prompts" / "setup.md",
        ]

        for prompt_path in prompt_paths:
            with self.subTest(prompt=prompt_path.name):
                content = prompt_path.read_text(encoding="utf-8")
                self.assertIn("- `agent`", content)
                self.assertIn("batch: \"agent\"", content)
                self.assertIn("rerun `plan setup`", content)


class PromptReviewSkillContractTests(unittest.TestCase):
    SKILL_PATH = REPO_ROOT / "skills" / "promptReview" / "SKILL.md"

    def _content(self) -> str:
        return self.SKILL_PATH.read_text(encoding="utf-8")

    def test_prompt_review_skill_file_exists(self) -> None:
        self.assertTrue(self.SKILL_PATH.exists(), "skills/promptReview/SKILL.md must exist")

    def test_prompt_review_skill_has_required_frontmatter_fields(self) -> None:
        content = self._content()
        frontmatter = content.split("---\n", 2)[1]
        self.assertIn("name: promptReview", frontmatter)
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
        # Module 6 must describe resolving markdown links and token references
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
        # waza quality (LLM-as-judge) is now an inline rubric applied by the reviewing agent
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
        # Step 0 is dissolved — waza commands now live inside each relevant module
        self.assertNotIn("## Step 0", content)
        self.assertNotIn("## Module 7", content)

    def test_prompt_review_skill_integrates_llm_as_judge_in_modules(self) -> None:
        content = self._content()
        # LLM-as-judge appears within Module 1, not as a separate numbered module
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
        import json

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
        """All servers must pin the same mcp[cli] version.

        Prevents intra-file drift where different servers silently diverge to
        different pins after manual edits.
        """
        import json

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
        import json

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
        import json

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