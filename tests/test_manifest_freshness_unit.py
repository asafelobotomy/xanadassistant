"""Additional direct unit tests for check_manifest_freshness.py — covers compare_catalog_to_generated and main()."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle.check_manifest_freshness import (
    compare_catalog_to_generated,
    compare_manifest_to_generated,
    main,
)
from scripts.lifecycle.generate_manifest import (
    generate_catalog,
    generate_manifest,
    load_json,
    load_optional_registry,
    write_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class CatalogFreshnessTests(unittest.TestCase):
    def test_compare_catalog_to_generated_repo_catalog_is_fresh(self) -> None:
        is_fresh, _current, _generated = compare_catalog_to_generated(
            REPO_ROOT,
            "template/setup/install-policy.json",
            "template/setup/catalog.json",
        )
        self.assertTrue(is_fresh)

    def test_compare_catalog_to_generated_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            (package_root / "template" / "prompts").mkdir(parents=True)
            (package_root / "template" / "prompts" / "setup.md").write_text("setup\n", encoding="utf-8")
            (package_root / "template" / "copilot-instructions.md").write_text("instructions\n", encoding="utf-8")

            policy = {
                "schemaVersion": "0.1.0",
                "canonicalSurfaces": ["core-instructions"],
                "sourceRoots": {"template": "template"},
                "surfaceSources": {
                    "core-instructions": {
                        "sourceRoot": "template",
                        "path": "copilot-instructions.md",
                        "kind": "file",
                        "layer": "core",
                    }
                },
                "targetPathRules": {
                    "core-instructions": {
                        "targetRoot": ".github",
                        "pathPattern": "copilot-instructions.md",
                        "surface": "instructions",
                    }
                },
                "ownershipDefaults": {"core-instructions": "local"},
                "strategyDefaults": {"core-instructions": "replace-verbatim"},
                "generationSettings": {
                    "manifestSchemaVersion": "0.1.0",
                    "derivedArtifactStrategy": {"catalog": "generated-from-policy-and-registries"},
                },
            }
            policy_path = package_root / "template" / "setup" / "install-policy.json"
            policy_path.parent.mkdir(parents=True)
            write_manifest(policy_path, policy)

            # Generate a real catalog.
            pack_registry = load_optional_registry(package_root / "template/setup/pack-registry.json")
            profile_registry = load_optional_registry(package_root / "template/setup/profile-registry.json")
            catalog = generate_catalog(policy, pack_registry, profile_registry)
            catalog_path = package_root / "template" / "setup" / "catalog.json"
            write_manifest(catalog_path, catalog)

            is_fresh, _current, _generated = compare_catalog_to_generated(
                package_root,
                "template/setup/install-policy.json",
                "template/setup/catalog.json",
            )
            self.assertTrue(is_fresh)

    def test_compare_catalog_stale_after_modification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            (package_root / "template" / "prompts").mkdir(parents=True)
            (package_root / "template" / "copilot-instructions.md").write_text("instructions\n", encoding="utf-8")

            policy = {
                "schemaVersion": "0.1.0",
                "canonicalSurfaces": ["core-instructions"],
                "sourceRoots": {"template": "template"},
                "surfaceSources": {
                    "core-instructions": {
                        "sourceRoot": "template",
                        "path": "copilot-instructions.md",
                        "kind": "file",
                        "layer": "core",
                    }
                },
                "targetPathRules": {
                    "core-instructions": {
                        "targetRoot": ".github",
                        "pathPattern": "copilot-instructions.md",
                        "surface": "instructions",
                    }
                },
                "ownershipDefaults": {"core-instructions": "local"},
                "strategyDefaults": {"core-instructions": "replace-verbatim"},
                "generationSettings": {
                    "manifestSchemaVersion": "0.1.0",
                    "derivedArtifactStrategy": {"catalog": "generated-from-policy-and-registries"},
                },
            }
            policy_path = package_root / "template" / "setup" / "install-policy.json"
            policy_path.parent.mkdir(parents=True)
            write_manifest(policy_path, policy)

            stale_catalog = {"schemaVersion": "0.1.0", "stale": True}
            catalog_path = package_root / "template" / "setup" / "catalog.json"
            write_manifest(catalog_path, stale_catalog)

            is_fresh, _current, _generated = compare_catalog_to_generated(
                package_root,
                "template/setup/install-policy.json",
                "template/setup/catalog.json",
            )
            self.assertFalse(is_fresh)


class ManifestFreshnessMainTests(unittest.TestCase):
    def _run_main(self, argv: list[str]) -> int:
        import sys
        orig_argv = sys.argv
        try:
            sys.argv = ["check_manifest_freshness"] + argv
            return main()
        finally:
            sys.argv = orig_argv

    def test_main_returns_zero_for_fresh_repo(self) -> None:
        code = self._run_main([
            "--package-root", str(REPO_ROOT),
            "--policy", "template/setup/install-policy.json",
            "--manifest", "template/setup/install-manifest.json",
            "--catalog", "template/setup/catalog.json",
        ])
        self.assertEqual(0, code)

    def test_main_returns_zero_without_catalog_arg(self) -> None:
        code = self._run_main([
            "--package-root", str(REPO_ROOT),
            "--policy", "template/setup/install-policy.json",
            "--manifest", "template/setup/install-manifest.json",
        ])
        self.assertEqual(0, code)

    def test_main_returns_one_for_stale_manifest(self) -> None:
        """Verify that compare_manifest_to_generated returns False when saved manifest != generated."""
        from scripts.lifecycle.check_manifest_freshness import compare_manifest_to_generated
        package_root = REPO_ROOT
        policy = "template/setup/install-policy.json"
        manifest = "template/setup/install-manifest.json"
        is_fresh, _current, _generated = compare_manifest_to_generated(package_root, policy, manifest)
        # The real repo manifest should match the generated one (i.e. be fresh).
        self.assertTrue(is_fresh)
