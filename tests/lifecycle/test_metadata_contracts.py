from __future__ import annotations

import unittest
from pathlib import Path

from scripts.lifecycle.generate_manifest import load_json
from tests.schema_validation import validate_instance


def _parse_agent_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError(f"{path} is missing YAML frontmatter")
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return values
        if not line or line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key] = value.strip().strip('"')
    raise AssertionError(f"{path} has unterminated YAML frontmatter")


class MetadataContractTests(unittest.TestCase):
    def test_pack_profile_and_catalog_metadata_match_schemas(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]

        pack_schema = load_json(repo_root / "template/setup/pack-registry.schema.json")
        pack_registry = load_json(repo_root / "template/setup/pack-registry.json")
        profile_schema = load_json(repo_root / "template/setup/profile-registry.schema.json")
        profile_registry = load_json(repo_root / "template/setup/profile-registry.json")
        catalog_schema = load_json(repo_root / "template/setup/catalog.schema.json")
        catalog = load_json(repo_root / "template/setup/catalog.json")

        validate_instance(pack_registry, pack_schema, pack_schema)
        validate_instance(profile_registry, profile_schema, profile_schema)
        validate_instance(catalog, catalog_schema, catalog_schema)

        self.assertEqual(["core-instructions", "prompts"], pack_registry["coreSurfaces"])
        self.assertEqual(
            ["memory", "lean", "review", "research", "workspace-ops"],
            [pack["id"] for pack in pack_registry["packs"]],
        )
        self.assertEqual(
            ["balanced", "lean", "ultra-lean"],
            [profile["id"] for profile in profile_registry["profiles"]],
        )
        self.assertEqual("policy+registries", catalog["generatedFrom"])
        self.assertEqual("core", catalog["surfaceLayers"]["core-instructions"])
        self.assertEqual("core", catalog["surfaceLayers"]["prompts"])

    def test_agent_routing_frontmatter_is_explicit(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        expected_keywords = {
            "commit.agent.md": ["Use when", "commit", "push", "preflight", "pull requests", "PR bodies"],
            "debugger.agent.md": ["Use when", "diagnosing failures", "root causes", "regressions"],
            "docs.agent.md": ["Use when", "documentation", "migration notes", "technical guides"],
            "explore.agent.md": ["Use when", "read-only", "file discovery", "symbol discovery"],
            "planner.agent.md": ["Use when", "scoped execution plans", "phased remediation", "before implementation"],
            "researcher.agent.md": ["Use when", "external documentation", "upstream behavior", "source-backed comparisons"],
            "review.agent.md": ["Use when", "code review", "security review", "regression-risk"],
            "xanad-lifecycle.agent.md": ["Use when", "inspect workspace", "repair install", "factory restore"],
        }

        for filename, keywords in expected_keywords.items():
            with self.subTest(agent=filename):
                frontmatter = _parse_agent_frontmatter(repo_root / "agents" / filename)
                description = frontmatter.get("description", "")
                for keyword in keywords:
                    self.assertIn(keyword, description)
                self.assertIn("tools", frontmatter)
                self.assertNotEqual("[]", frontmatter["tools"])
                if filename != "explore.agent.md":
                    self.assertIn("agents", frontmatter)

                if filename == "xanad-lifecycle.agent.md":
                    self.assertIn("model", frontmatter)
                    self.assertIn("agent", frontmatter["tools"])

                if filename in {"debugger.agent.md", "planner.agent.md", "researcher.agent.md"}:
                    self.assertEqual("false", frontmatter.get("user-invocable"))
                    self.assertIn("agent", frontmatter["tools"])

    def test_instructions_define_agent_routing_table(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        for path in [repo_root / "template" / "copilot-instructions.md", repo_root / ".github" / "copilot-instructions.md"]:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("## Agent Routing", text)
                self.assertIn("Route specialist work to the matching agent", text)
                self.assertIn("| Git status, staging, commit messages", text)
                self.assertIn("| Broad read-only codebase exploration", text)
                self.assertIn("| Root-cause diagnosis, failing tests", text)
                self.assertIn("| Complex multi-step planning, phased rollout", text)
                self.assertIn("| External documentation, upstream behavior", text)
                self.assertIn("| Documentation updates, migration notes", text)
                self.assertIn("| Code review, architecture review", text)
                self.assertIn("| xanad-assistant inspect, check, plan", text)
                self.assertIn("Debugger", text)
                self.assertIn("Docs", text)
                self.assertIn("Planner", text)
                self.assertIn("Researcher", text)
                self.assertIn("xanad-lifecycle", text)

    def test_instructions_define_memory_routing(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        for path in [repo_root / "template" / "copilot-instructions.md", repo_root / ".github" / "copilot-instructions.md"]:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("## Memory", text)
                self.assertIn("/memories/session/", text)
                self.assertIn("/memories/repo/", text)
                self.assertIn("docs/memory.md", text)
                self.assertIn("not as lifecycle authority", text)

    def test_root_agents_document_captures_specialist_routing(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        text = (repo_root / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("# Agent Routing", text)
        self.assertIn("This file is the canonical routing map", text)
        self.assertIn("`Debugger` | no | Root-cause diagnosis", text)
        self.assertIn("`Docs` | yes | Documentation updates", text)
        self.assertIn("`Planner` | no | Complex multi-step planning", text)
        self.assertIn("`Researcher` | no | External documentation", text)
        self.assertIn("| Root-cause diagnosis, failing tests", text)
        self.assertIn("| Complex multi-step planning, phased rollout", text)
        self.assertIn("| External documentation, upstream behavior", text)
        self.assertIn("| Documentation updates, migration notes", text)
        self.assertIn("## Recommended Handoff Patterns", text)
        self.assertIn("| `Review` | `Debugger` |", text)
        self.assertIn("| `Researcher` | `Docs` |", text)
        self.assertIn("| `xanad-lifecycle` | `Planner` |", text)
        self.assertIn("`inspect workspace`", text)
        self.assertIn("Remember this for next time", text)


if __name__ == "__main__":
    unittest.main()