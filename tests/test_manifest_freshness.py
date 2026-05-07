from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle.check_manifest_freshness import compare_catalog_to_generated, compare_manifest_to_generated
from scripts.lifecycle.generate_manifest import generate_catalog, generate_manifest, write_manifest


class ManifestFreshnessTests(unittest.TestCase):
    def test_repo_manifest_is_fresh(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        is_fresh, _current, _generated = compare_manifest_to_generated(
            repo_root,
            "template/setup/install-policy.json",
            "template/setup/install-manifest.json",
        )

        self.assertTrue(is_fresh)

    def test_manifest_freshness_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            (package_root / "template" / "prompts").mkdir(parents=True)
            (package_root / "template" / "prompts" / "setup.md").write_text("setup\n", encoding="utf-8")
            (package_root / "template" / "copilot-instructions.md").write_text("instructions\n", encoding="utf-8")

            policy = {
                "schemaVersion": "0.1.0",
                "canonicalSurfaces": ["core-instructions", "prompts"],
                "sourceRoots": {
                    "template": "template"
                },
                "surfaceSources": {
                    "core-instructions": {
                        "sourceRoot": "template",
                        "path": "copilot-instructions.md",
                        "kind": "file",
                        "layer": "core"
                    },
                    "prompts": {
                        "sourceRoot": "template",
                        "path": "prompts",
                        "kind": "directory",
                        "layer": "core"
                    }
                },
                "targetPathRules": {
                    "core-instructions": {
                        "targetRoot": ".github",
                        "pathPattern": "copilot-instructions.md",
                        "surface": "instructions"
                    },
                    "prompts": {
                        "targetRoot": ".github/prompts",
                        "surface": "prompts"
                    }
                },
                "ownershipDefaults": {
                    "core-instructions": "local",
                    "prompts": "local"
                },
                "strategyDefaults": {
                    "core-instructions": "preserve-marked-markdown-blocks",
                    "prompts": "replace-verbatim"
                },
                "requiredConditions": {},
                "tokenRules": [],
                "chmodRules": {},
                "retiredFilePolicy": {
                    "defaultAction": "report-retired",
                    "entries": []
                },
                "packageFormatDeliveryRules": {},
                "generationSettings": {
                    "manifestSchemaVersion": "0.1.0",
                    "manifestOutput": "template/setup/install-manifest.json",
                    "includeRetiredFiles": True,
                    "unmanagedSourceExcludes": ["template/setup/**"]
                }
            }

            policy_path = package_root / "template" / "setup" / "install-policy.json"
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

            manifest = generate_manifest(package_root, policy)
            manifest["managedFiles"][0]["target"] = ".github/copilot-instructions-stale.md"
            write_manifest(package_root / "template" / "setup" / "install-manifest.json", manifest)

            is_fresh, _current, _generated = compare_manifest_to_generated(
                package_root,
                "template/setup/install-policy.json",
                "template/setup/install-manifest.json",
            )

            self.assertFalse(is_fresh)


class CatalogFreshnessTests(unittest.TestCase):
    def test_repo_catalog_is_fresh(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        is_fresh, _current, _generated = compare_catalog_to_generated(
            repo_root,
            "template/setup/install-policy.json",
            "template/setup/catalog.json",
        )

        self.assertTrue(is_fresh)

    def test_catalog_freshness_detects_drift(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        policy_rel = "template/setup/install-policy.json"

        # Load genuinely-generated catalog, then tamper one field
        from scripts.lifecycle.generate_manifest import load_json, load_optional_registry
        package_root = repo_root
        policy = load_json(package_root / policy_rel)
        pack_registry = load_optional_registry(package_root / "template/setup/pack-registry.json")
        profile_registry = load_optional_registry(package_root / "template/setup/profile-registry.json")
        fresh_catalog = generate_catalog(policy, pack_registry, profile_registry)

        stale_catalog = dict(fresh_catalog)
        stale_catalog["schemaVersion"] = "0.0.0-stale"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            # Write policy, pack-registry, and profile-registry mirrors
            policy_path = temp_root / policy_rel
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(
                (package_root / policy_rel).read_text(encoding="utf-8"), encoding="utf-8"
            )
            for reg_path in ("template/setup/pack-registry.json", "template/setup/profile-registry.json"):
                src = package_root / reg_path
                dst = temp_root / reg_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

            catalog_path = temp_root / "template/setup/catalog.json"
            catalog_path.write_text(json.dumps(stale_catalog, indent=2) + "\n", encoding="utf-8")

            is_fresh, _current, _generated = compare_catalog_to_generated(
                temp_root,
                policy_rel,
                "template/setup/catalog.json",
            )

        self.assertFalse(is_fresh)


if __name__ == "__main__":
    unittest.main()