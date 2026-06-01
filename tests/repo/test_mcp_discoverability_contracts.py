from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class McpDiscoverabilityContractTests(unittest.TestCase):
    def test_lifecycle_surfaces_route_setup_not_retired_apply(self) -> None:
        agent = (REPO_ROOT / "agents" / "xanadLifecycle.agent.md").read_text(encoding="utf-8")
        routing = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertNotIn("apply setup", agent)
        self.assertNotIn("; `apply` otherwise", agent)
        self.assertNotIn("Apply only after approval", agent)
        self.assertNotIn("python3 xanadAssistant.py apply", agent)
        self.assertIn("; `setup` otherwise", agent)
        self.assertIn("Write only after approval", agent)
        self.assertIn("python3 xanadAssistant.py setup", agent)
        self.assertNotIn("plan, apply, update", routing)
        self.assertIn("plan, update, repair", routing)
        self.assertIn("plan`, `setup`, `update", routing)

    def test_docs_agent_uses_installed_docs_pack_link_checker_path(self) -> None:
        content = (REPO_ROOT / "agents" / "docs.agent.md").read_text(encoding="utf-8")
        self.assertIn("python3 .github/mcp/scripts/docsLinkCheck.py", content)
        self.assertNotIn("python3 packs/docs/mcp/docsLinkCheck.py", content)

    def test_pack_readmes_describe_installed_tool_scripts_not_default_mcp_servers(self) -> None:
        for relative_path in (
            "packs/devops/README.md",
            "packs/docs/README.md",
            "packs/lean/README.md",
            "packs/mlops/README.md",
            "packs/oss/README.md",
            "packs/secure/README.md",
            "packs/shapeup/README.md",
            "packs/tdd/README.md",
        ):
            content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertIn("**Tool scripts**", content)
                self.assertIn("default core MCP server roster", content)
                self.assertNotIn("| **MCP** |", content)

    def test_pack_skills_and_prompts_do_not_assume_unregistered_pack_servers(self) -> None:
        oss_prompt = (REPO_ROOT / "packs" / "oss" / "prompts" / "oss-changelog.prompt.md").read_text(encoding="utf-8")
        oss_skill = (REPO_ROOT / "packs" / "oss" / "skills" / "ossChangelog" / "SKILL.md").read_text(encoding="utf-8")
        secure_skill = (REPO_ROOT / "packs" / "secure" / "skills" / "dependencyAudit" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("optional `ossGitLog` pack server", oss_prompt)
        self.assertIn("optional `ossGitLog` pack server", oss_skill)
        self.assertIn("`security` MCP server", secure_skill)
        self.assertNotIn("secureOsv hook", secure_skill)


if __name__ == "__main__":
    unittest.main()