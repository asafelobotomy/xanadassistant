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
        repo_root = Path(__file__).resolve().parents[1]

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
        repo_root = Path(__file__).resolve().parents[1]
        expected_keywords = {
            "commit.agent.md": ["Use when", "commit", "push", "preflight", "pull requests", "PR bodies"],
            "explore.agent.md": ["Use when", "read-only", "file discovery", "symbol discovery"],
            "review.agent.md": ["Use when", "code review", "security review", "regression-risk"],
            "lifecycle-planning.agent.md": ["Use when", "inspect workspace", "repair install", "factory restore"],
        }

        for filename, keywords in expected_keywords.items():
            with self.subTest(agent=filename):
                frontmatter = _parse_agent_frontmatter(repo_root / "agents" / filename)
                description = frontmatter.get("description", "")
                for keyword in keywords:
                    self.assertIn(keyword, description)
                self.assertIn("tools", frontmatter)
                self.assertNotEqual("[]", frontmatter["tools"])
                self.assertIn("agents", frontmatter)

    def test_instructions_define_agent_routing_table(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        for path in [repo_root / "template" / "copilot-instructions.md", repo_root / ".github" / "copilot-instructions.md"]:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("## Agent Routing", text)
                self.assertIn("Route specialist work to the matching agent", text)
                self.assertIn("| Git status, staging, commit messages", text)
                self.assertIn("| Broad read-only codebase exploration", text)
                self.assertIn("| Code review, architecture review", text)
                self.assertIn("| xanad-assistant inspect, check, plan", text)

    def test_instructions_define_memory_routing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        for path in [repo_root / "template" / "copilot-instructions.md", repo_root / ".github" / "copilot-instructions.md"]:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("## Memory", text)
                self.assertIn("/memories/session/", text)
                self.assertIn("/memories/repo/", text)
                self.assertIn("docs/memory.md", text)
                self.assertIn("not as lifecycle authority", text)


if __name__ == "__main__":
    unittest.main()