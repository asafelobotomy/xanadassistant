from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class PromptContractTests(unittest.TestCase):
    def _declared_tools(self, agent_filename: str) -> set[str]:
        content = (REPO_ROOT / "agents" / agent_filename).read_text(encoding="utf-8")
        frontmatter = content.split("---\n", 2)[1]
        match = re.search(r"^tools:\s*(\[[^\n]+\])$", frontmatter, re.MULTILINE)
        self.assertIsNotNone(match, f"tools frontmatter missing from {agent_filename}")
        return {
            token.strip()
            for token in match.group(1).strip("[]").split(",")
            if token.strip()
        }

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

    def test_commit_agent_prefers_git_mcp_for_tag_creation(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("Prefer `git_tag`", content)

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

    def test_commit_agent_prefers_structured_pr_creation_over_gh(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("`create_pull_request` (GitHub MCP)", content)
        self.assertIn("`githubRepo`", content)
        self.assertIn("`gh pr create` via `runCommands` only when the `create_pull_request` MCP tool is unavailable", content)

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
        # The agent must require showing the full proposed message verbatim before approval.
        shows_verbatim = (
            "include the exact proposed commit subject and body verbatim" in content
            or "full proposed commit message" in content
        )
        self.assertTrue(shows_verbatim, "commit.agent.md must require showing the full message verbatim")
        self.assertTrue(
            "before answering" in content or "Do not commit without acknowledgement" in content,
            "commit.agent.md must require acknowledgement before committing",
        )

    def test_commit_agent_prefers_git_merge_for_merge_continue(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("`git_merge`", content)
        self.assertIn("git_merge` action `continue`", content)

    def test_commit_agent_prefers_create_release_for_github_releases(self) -> None:
        content = (REPO_ROOT / "agents" / "commit.agent.md").read_text(encoding="utf-8")
        self.assertIn("`create_release` (GitHub MCP)", content)
        self.assertIn("`gh release create` via `runCommands` only when the `create_release` MCP tool is unavailable", content)

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

    def test_repo_copilot_instructions_use_exact_lifecycle_mcp_tool_names(self) -> None:
        instruction_paths = [
            REPO_ROOT / "template" / "copilot-instructions.md",
            REPO_ROOT / ".github" / "copilot-instructions.md",
        ]
        for instruction_path in instruction_paths:
            with self.subTest(path=instruction_path):
                content = instruction_path.read_text(encoding="utf-8")
                self.assertNotIn("`lifecycle.*`", content)
                self.assertIn("`lifecycle_inspect`", content)
                self.assertIn("`lifecycle_factory_restore`", content)

    def test_xanad_lifecycle_agent_declares_referenced_lifecycle_tools(self) -> None:
        declared = self._declared_tools("xanadLifecycle.agent.md")
        self.assertTrue(
            {
                "lifecycle_inspect",
                "lifecycle_check",
                "lifecycle_interview",
                "lifecycle_plan_setup",
                "lifecycle_setup",
                "lifecycle_update",
                "lifecycle_repair",
                "lifecycle_factory_restore",
            }.issubset(declared)
        )

    def test_deps_agent_declares_security_memory_and_time_tools(self) -> None:
        declared = self._declared_tools("deps.agent.md")
        self.assertTrue(
            {"query_osv", "query_deps", "memory_dump", "memory_set", "elapsed"}.issubset(declared)
        )

    def test_researcher_agent_declares_documented_mcp_tools(self) -> None:
        declared = self._declared_tools("researcher.agent.md")
        self.assertTrue(
            {
                "resolve_library_id",
                "query_docs",
                "get_repo",
                "get_file_contents",
                "search_code",
                "list_issues",
                "get_issue",
                "list_pull_requests",
                "get_pull_request",
                "list_releases",
                "list_workflow_runs",
                "memory_dump",
                "memory_set",
                "elapsed",
            }.issubset(declared)
        )

    def test_read_heavy_agents_declare_filesystem_memory_and_time_tools(self) -> None:
        for agent_filename in [
            "review.agent.md",
            "debugger.agent.md",
            "planner.agent.md",
            "docs.agent.md",
        ]:
            with self.subTest(agent=agent_filename):
                declared = self._declared_tools(agent_filename)
                self.assertTrue(
                    {
                        "read_file",
                        "list_directory",
                        "search_files",
                        "file_info",
                        "memory_dump",
                        "memory_set",
                        "elapsed",
                    }.issubset(declared)
                )

    def test_read_heavy_agents_prefer_filesystem_tools_for_read_only_inspection(self) -> None:
        for agent_filename in [
            "review.agent.md",
            "debugger.agent.md",
            "planner.agent.md",
            "docs.agent.md",
        ]:
            with self.subTest(agent=agent_filename):
                content = (REPO_ROOT / "agents" / agent_filename).read_text(encoding="utf-8")
                self.assertIn("When the `filesystem` server is connected", content)
                self.assertIn("`read_file`", content)
                self.assertIn("`list_directory`", content)
                self.assertIn("`search_files`", content)
                self.assertIn("`file_info`", content)

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

    def test_readme_documents_mcp_precedence_and_server_availability(self) -> None:
        content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("prefer these structured MCP tools over generic terminal or shell execution", content)
        self.assertIn("`github` and `sqlite` are shipped disabled by default", content)
        self.assertIn("`xanadTools`, `git`, `web`, `devDocs`, `time`, `memory`, `security`, `filesystem`, and `sequential-thinking`", content)
        self.assertIn("prefer the structured `lifecycle_*` MCP tools first", content)

    def test_tool_mcp_contracts_document_exact_server_ids_and_explicit_fallbacks(self) -> None:
        boundary = (REPO_ROOT / "docs" / "contracts" / "tool-mcp-boundary.md").read_text(encoding="utf-8")
        v1 = (REPO_ROOT / "docs" / "contracts" / "tool-mcp-v1.md").read_text(encoding="utf-8")
        self.assertIn("prefer the structured MCP tool first", boundary)
        self.assertIn("reference these exact configured server ids", boundary)
        self.assertIn("fall back to its documented native tool or CLI path", boundary)
        self.assertIn("matching server id is connected", v1)
        self.assertIn("reference exact server ids such as `xanadTools`, `security`, `devDocs`, `memory`, `time`, and `filesystem`", v1)
        self.assertIn("fallback must be an explicit documented native tool or CLI path", v1)

    def test_template_mcp_config_preserves_default_server_availability_contract(self) -> None:
        config = json.loads((REPO_ROOT / "template" / "vscode" / "mcp.json").read_text(encoding="utf-8"))
        servers = config["servers"]

        self.assertTrue(servers["github"]["disabled"])
        self.assertTrue(servers["sqlite"]["disabled"])

        for server_id in (
            "xanadTools",
            "git",
            "web",
            "devDocs",
            "time",
            "memory",
            "security",
            "filesystem",
            "sequential-thinking",
        ):
            with self.subTest(server_id=server_id):
                self.assertIn(server_id, servers)
                self.assertFalse(servers[server_id].get("disabled", False))

    def test_installed_mcp_config_matches_template_defaults_and_scripts(self) -> None:
        template = json.loads((REPO_ROOT / "template" / "vscode" / "mcp.json").read_text(encoding="utf-8"))
        installed = json.loads((REPO_ROOT / ".vscode" / "mcp.json").read_text(encoding="utf-8"))

        self.assertEqual(template["servers"], installed["servers"])

        for server_id, config in installed["servers"].items():
            with self.subTest(server_id=server_id):
                script_path = Path(config["args"][-1].replace("${workspaceFolder}/", ""))
                self.assertTrue((REPO_ROOT / script_path).exists(), f"Configured MCP script missing for {server_id}: {script_path}")

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
        self.assertIn("- `health-report`", cli_surface)
        self.assertIn("`health-report`", cli_surface)
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


if __name__ == "__main__":
    unittest.main()