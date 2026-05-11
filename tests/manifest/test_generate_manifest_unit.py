"""Direct unit tests for generate_manifest.py — covers validate_policy, validate_surface_sources,
validate_unmanaged_sources, resolve_supported_ownership, and main() branches missed by subprocess tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle.generate_manifest import (
    generate_manifest,
    main,
    resolve_supported_ownership,
    validate_policy,
    validate_surface_sources,
    validate_unmanaged_sources,
    write_manifest,
)
from scripts.lifecycle._manifest_utils import OWNERSHIP_MODES


REPO_ROOT = Path(__file__).resolve().parents[2]


def _minimal_policy(package_root: Path) -> dict:
    """Build a minimal valid policy pointing at files in package_root/template/content/."""
    content_dir = package_root / "template" / "content"
    content_dir.mkdir(parents=True, exist_ok=True)
    (content_dir / "copilot-instructions.md").write_text("instructions\n", encoding="utf-8")
    return {
        "schemaVersion": "0.1.0",
        "canonicalSurfaces": ["core-instructions"],
        "sourceRoots": {"content": "template/content"},
        "surfaceSources": {
            "core-instructions": {
                "sourceRoot": "content",
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
        "generationSettings": {"manifestSchemaVersion": "0.1.0"},
    }


class ValidatePolicyTests(unittest.TestCase):
    def test_validate_policy_raises_when_surface_missing_from_surface_sources(self) -> None:
        policy = {
            "schemaVersion": "0.1.0",
            "canonicalSurfaces": ["missing-surface"],
            "sourceRoots": {},
            "surfaceSources": {},
            "targetPathRules": {},
            "ownershipDefaults": {},
            "strategyDefaults": {},
        }
        with self.assertRaises(ValueError) as ctx:
            validate_policy(policy)
        self.assertIn("missing-surface", str(ctx.exception))

    def test_validate_policy_raises_when_surface_missing_from_target_rules(self) -> None:
        policy = {
            "schemaVersion": "0.1.0",
            "canonicalSurfaces": ["surf"],
            "sourceRoots": {},
            "surfaceSources": {"surf": {}},
            "targetPathRules": {},
            "ownershipDefaults": {"surf": "local"},
            "strategyDefaults": {"surf": "replace-verbatim"},
        }
        with self.assertRaises(ValueError) as ctx:
            validate_policy(policy)
        self.assertIn("surf", str(ctx.exception))

    def test_validate_policy_passes_for_valid_policy(self) -> None:
        policy = {
            "schemaVersion": "0.1.0",
            "canonicalSurfaces": ["surf"],
            "sourceRoots": {},
            "surfaceSources": {"surf": {}},
            "targetPathRules": {"surf": {}},
            "ownershipDefaults": {"surf": "local"},
            "strategyDefaults": {"surf": "replace-verbatim"},
        }
        validate_policy(policy)  # should not raise


class ResolveSupportedOwnershipTests(unittest.TestCase):
    def test_returns_default_when_no_delivery_rule(self) -> None:
        result = resolve_supported_ownership("surf", "local", {})
        self.assertEqual(["local"], result)

    def test_returns_supported_ownership_from_delivery_rule(self) -> None:
        delivery_rules = {
            "surf": {"supportedOwnership": ["local", "plugin-backed-copilot-format"]}
        }
        result = resolve_supported_ownership("surf", "local", delivery_rules)
        self.assertEqual(["local", "plugin-backed-copilot-format"], result)

    def test_raises_when_default_not_in_supported_ownership(self) -> None:
        delivery_rules = {"surf": {"supportedOwnership": ["plugin-backed-copilot-format"]}}
        with self.assertRaises(ValueError):
            resolve_supported_ownership("surf", "local", delivery_rules)

    def test_raises_when_unsupported_mode_in_list(self) -> None:
        delivery_rules = {"surf": {"supportedOwnership": ["local", "unknown-mode"]}}
        with self.assertRaises(ValueError):
            resolve_supported_ownership("surf", "local", delivery_rules)


class ValidateSurfaceSourcesTests(unittest.TestCase):
    def test_raises_when_file_surface_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            (package_root / "template").mkdir()
            policy = {
                "schemaVersion": "0.1.0",
                "canonicalSurfaces": ["surf"],
                "sourceRoots": {"template": "template"},
                "surfaceSources": {
                    "surf": {
                        "sourceRoot": "template",
                        "path": "missing.md",
                        "kind": "file",
                        "layer": "core",
                    }
                },
                "targetPathRules": {"surf": {}},
                "ownershipDefaults": {"surf": "local"},
                "strategyDefaults": {"surf": "replace-verbatim"},
            }
            with self.assertRaises(ValueError):
                validate_surface_sources(package_root, policy)

    def test_raises_when_directory_surface_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            (package_root / "template").mkdir()
            policy = {
                "schemaVersion": "0.1.0",
                "canonicalSurfaces": ["surf"],
                "sourceRoots": {"template": "template"},
                "surfaceSources": {
                    "surf": {
                        "sourceRoot": "template",
                        "path": "missing-dir",
                        "kind": "directory",
                        "layer": "core",
                    }
                },
                "targetPathRules": {"surf": {}},
                "ownershipDefaults": {"surf": "local"},
                "strategyDefaults": {"surf": "replace-verbatim"},
            }
            with self.assertRaises(ValueError):
                validate_surface_sources(package_root, policy)

    def test_raises_for_unknown_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            policy = {
                "schemaVersion": "0.1.0",
                "canonicalSurfaces": ["surf"],
                "sourceRoots": {},
                "surfaceSources": {
                    "surf": {
                        "sourceRoot": "nonexistent-root",
                        "path": "file.md",
                        "kind": "file",
                        "layer": "core",
                    }
                },
                "targetPathRules": {"surf": {}},
                "ownershipDefaults": {"surf": "local"},
                "strategyDefaults": {"surf": "replace-verbatim"},
            }
            with self.assertRaises(ValueError):
                validate_surface_sources(package_root, policy)


class ValidateUnmanagedSourcesTests(unittest.TestCase):
    def test_raises_when_unmanaged_files_exist_in_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            template_dir = package_root / "template"
            template_dir.mkdir()
            (template_dir / "managed.md").write_text("managed\n", encoding="utf-8")
            (template_dir / "unmanaged.md").write_text("not in policy\n", encoding="utf-8")

            policy = {
                "schemaVersion": "0.1.0",
                "canonicalSurfaces": ["surf"],
                "sourceRoots": {"template": "template"},
                "surfaceSources": {
                    "surf": {
                        "sourceRoot": "template",
                        "path": "managed.md",
                        "kind": "file",
                        "layer": "core",
                    }
                },
                "targetPathRules": {"surf": {}},
                "ownershipDefaults": {"surf": "local"},
                "strategyDefaults": {"surf": "replace-verbatim"},
            }
            with self.assertRaises(ValueError) as ctx:
                validate_unmanaged_sources(package_root, policy)
            self.assertIn("unmanaged", str(ctx.exception).lower())


class GenerateManifestMainTests(unittest.TestCase):
    def _run_main(self, argv: list[str]) -> int:
        import sys
        orig_argv = sys.argv
        try:
            sys.argv = ["generate_manifest"] + argv
            return main()
        finally:
            sys.argv = orig_argv

    def test_main_generates_manifest_to_temp_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            policy = _minimal_policy(package_root)
            policy_path = package_root / "template" / "setup" / "install-policy.json"
            policy_path.parent.mkdir(parents=True)
            write_manifest(policy_path, policy)
            manifest_out = package_root / "template" / "setup" / "install-manifest.json"

            code = self._run_main([
                "--package-root", str(package_root),
                "--policy", "template/setup/install-policy.json",
                "--manifest-out", "template/setup/install-manifest.json",
            ])
            self.assertEqual(0, code)
            self.assertTrue(manifest_out.exists())
            data = json.loads(manifest_out.read_text(encoding="utf-8"))
            self.assertIn("managedFiles", data)

    def test_main_uses_default_manifest_output_path_from_policy(self) -> None:
        """When --manifest-out is absent, main() falls back to generationSettings.manifestOutput."""
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            policy = _minimal_policy(package_root)
            policy["generationSettings"]["manifestOutput"] = "template/setup/install-manifest.json"
            policy_path = package_root / "template" / "setup" / "install-policy.json"
            policy_path.parent.mkdir(parents=True)
            write_manifest(policy_path, policy)

            code = self._run_main([
                "--package-root", str(package_root),
                "--policy", "template/setup/install-policy.json",
            ])
            self.assertEqual(0, code)
            expected_path = package_root / "template" / "setup" / "install-manifest.json"
            self.assertTrue(expected_path.exists())

    def test_main_generates_catalog_when_strategy_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package_root = Path(tmp)
            policy = _minimal_policy(package_root)
            policy["generationSettings"]["derivedArtifactStrategy"] = {
                "catalog": "generated-from-policy-and-registries"
            }
            policy_path = package_root / "template" / "setup" / "install-policy.json"
            policy_path.parent.mkdir(parents=True)
            write_manifest(policy_path, policy)

            code = self._run_main([
                "--package-root", str(package_root),
                "--policy", "template/setup/install-policy.json",
                "--manifest-out", "template/setup/install-manifest.json",
            ])
            self.assertEqual(0, code)
            catalog_path = package_root / "template" / "setup" / "catalog.json"
            self.assertTrue(catalog_path.exists())
