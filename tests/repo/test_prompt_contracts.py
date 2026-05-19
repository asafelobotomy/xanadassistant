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

        self.assertIn("include the exact proposed commit subject and body verbatim", content)
        self.assertIn("before answering", content)

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