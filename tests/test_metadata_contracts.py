from __future__ import annotations

import unittest
from pathlib import Path

from scripts.lifecycle.generate_manifest import load_json
from tests.schema_validation import validate_instance


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


if __name__ == "__main__":
    unittest.main()