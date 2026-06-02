from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

from scripts.lifecycle import check_manifest_freshness as check_manifest_freshness_module
from scripts.lifecycle import generate_manifest as generate_manifest_module
from scripts.lifecycle.generate_manifest import main, validate_pack_registry
from scripts.lifecycle._manifest_utils import load_json, load_optional_registry


class GenerateManifestPackValidationTests(unittest.TestCase):
    def test_active_pack_registry_matches_policy_and_pack_directories(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        policy = load_json(repo_root / "template/setup/install-policy.json")
        pack_registry = load_optional_registry(repo_root / "template/setup/pack-registry.json")

        validate_pack_registry(repo_root, policy, pack_registry)

    def test_detects_registry_surface_mismatch_for_active_pack(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        policy = load_json(repo_root / "template/setup/install-policy.json")
        pack_registry = load_optional_registry(repo_root / "template/setup/pack-registry.json")
        broken_registry = copy.deepcopy(pack_registry)

        tdd_pack = next(pack for pack in broken_registry["packs"] if pack["id"] == "tdd")
        tdd_pack["surfaces"] = [surface for surface in tdd_pack["surfaces"] if surface != "tdd-hooks"]

        with self.assertRaisesRegex(ValueError, "Pack registry surfaces are inconsistent: tdd"):
            validate_pack_registry(repo_root, policy, broken_registry)

    def test_main_writes_manifest_and_catalog_for_valid_package_root(self) -> None:
        with self._copied_package_root() as package_root:
            manifest_path = package_root / "template/setup/install-manifest.json"
            catalog_path = package_root / "template/setup/catalog.json"

            manifest_before = manifest_path.read_text(encoding="utf-8")
            catalog_before = catalog_path.read_text(encoding="utf-8")

            with mock.patch.object(
                generate_manifest_module,
                "parse_args",
                return_value=Namespace(
                    package_root=str(package_root),
                    policy="template/setup/install-policy.json",
                    manifest_out=None,
                ),
            ):
                result = main()

            self.assertEqual(result, 0)
            manifest_after = manifest_path.read_text(encoding="utf-8")
            catalog_after = catalog_path.read_text(encoding="utf-8")
            repo_root = Path(__file__).resolve().parents[2]
            expected_version = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
            self.assertNotEqual(manifest_before, "")
            self.assertNotEqual(catalog_before, "")
            self.assertEqual(json.loads(manifest_after)["packageVersion"], expected_version)
            self.assertIn("tdd-hooks", json.loads(catalog_after)["surfaceLayers"])

    def test_main_fails_before_write_when_pack_registry_mismatches(self) -> None:
        with self._copied_package_root() as package_root:
            registry_path = package_root / "template/setup/pack-registry.json"
            manifest_path = package_root / "template/setup/install-manifest.json"
            catalog_path = package_root / "template/setup/catalog.json"

            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            tdd_pack = next(pack for pack in registry["packs"] if pack["id"] == "tdd")
            tdd_pack["surfaces"] = [surface for surface in tdd_pack["surfaces"] if surface != "tdd-hooks"]
            registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

            manifest_before = manifest_path.read_text(encoding="utf-8")
            catalog_before = catalog_path.read_text(encoding="utf-8")

            with mock.patch.object(
                generate_manifest_module,
                "parse_args",
                return_value=Namespace(
                    package_root=str(package_root),
                    policy="template/setup/install-policy.json",
                    manifest_out=None,
                ),
            ):
                with self.assertRaisesRegex(ValueError, "Pack registry surfaces are inconsistent: tdd"):
                    main()

            self.assertEqual(manifest_before, manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(catalog_before, catalog_path.read_text(encoding="utf-8"))

    def test_freshness_check_fails_when_pack_registry_mismatches(self) -> None:
        with self._copied_package_root() as package_root:
            registry_path = package_root / "template/setup/pack-registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            tdd_pack = next(pack for pack in registry["packs"] if pack["id"] == "tdd")
            tdd_pack["surfaces"] = [surface for surface in tdd_pack["surfaces"] if surface != "tdd-hooks"]
            registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

            with mock.patch.object(
                check_manifest_freshness_module,
                "parse_args",
                return_value=Namespace(
                    package_root=str(package_root),
                    policy="template/setup/install-policy.json",
                    manifest="template/setup/install-manifest.json",
                    catalog="template/setup/catalog.json",
                ),
            ):
                with self.assertRaisesRegex(ValueError, "Pack registry surfaces are inconsistent: tdd"):
                    check_manifest_freshness_module.main()

    def _copied_package_root(self):
        return _CopiedPackageRoot()


class ExcludeGlobsTests(unittest.TestCase):
    """generate_manifest respects excludeGlobs in surface specs."""

    def _make_package_root(self, tmp_path: Path) -> Path:
        """Build a minimal package root with a tools surface containing two files."""
        repo_root = Path(__file__).resolve().parents[2]

        for name in ("agents", "mcp", "packs", "skills", "template"):
            shutil.copytree(repo_root / name, tmp_path / name)
        shutil.copy2(repo_root / "VERSION", tmp_path / "VERSION")

        # Create a tools surface with two directories: kept/ and excluded/
        (tmp_path / "tools" / "kept").mkdir(parents=True)
        (tmp_path / "tools" / "kept" / "helper.py").write_text("# kept\n")
        (tmp_path / "tools" / "excluded").mkdir(parents=True)
        (tmp_path / "tools" / "excluded" / "tool.py").write_text("# excluded\n")

        return tmp_path

    def test_excluded_globs_are_omitted_from_managed_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            pkg = self._make_package_root(Path(raw_tmp))

            policy_path = pkg / "template/setup/install-policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["surfaceSources"]["tools"]["excludeGlobs"] = ["excluded/**"]
            policy["generationSettings"]["unmanagedSourceExcludes"].append("tools/excluded/**")
            policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

            with mock.patch.object(
                generate_manifest_module,
                "parse_args",
                return_value=Namespace(
                    package_root=str(pkg),
                    policy="template/setup/install-policy.json",
                    manifest_out=None,
                ),
            ):
                result = main()

            self.assertEqual(result, 0)
            manifest = json.loads((pkg / "template/setup/install-manifest.json").read_text())
            targets = [e["target"] for e in manifest["managedFiles"]]
            self.assertFalse(
                any("excluded" in t for t in targets),
                f"excluded/ files should not appear in managedFiles; got: {[t for t in targets if 'excluded' in t]}",
            )
            self.assertTrue(
                any("kept" in t for t in targets),
                "kept/ files should still appear in managedFiles",
            )

    def test_no_exclude_globs_includes_all_surface_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            pkg = self._make_package_root(Path(raw_tmp))

            policy_path = pkg / "template/setup/install-policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            # Remove excludeGlobs (if any) so both dirs are included
            policy["surfaceSources"]["tools"].pop("excludeGlobs", None)
            policy["generationSettings"]["unmanagedSourceExcludes"] = [
                p for p in policy["generationSettings"]["unmanagedSourceExcludes"]
                if "xanadEval" not in p
            ]
            policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")

            with mock.patch.object(
                generate_manifest_module,
                "parse_args",
                return_value=Namespace(
                    package_root=str(pkg),
                    policy="template/setup/install-policy.json",
                    manifest_out=None,
                ),
            ):
                result = main()

            self.assertEqual(result, 0)
            manifest = json.loads((pkg / "template/setup/install-manifest.json").read_text())
            targets = [e["target"] for e in manifest["managedFiles"]]
            self.assertTrue(
                any("excluded" in t for t in targets),
                "Without excludeGlobs, excluded/ files should appear in managedFiles",
            )
            self.assertTrue(
                any("kept" in t for t in targets),
                "Without excludeGlobs, kept/ files should also appear in managedFiles",
            )

    def test_xanadeeval_absent_from_real_manifest(self) -> None:
        """xanadEval must not appear in the committed install-manifest.json."""
        repo_root = Path(__file__).resolve().parents[2]
        manifest = json.loads(
            (repo_root / "template/setup/install-manifest.json").read_text(encoding="utf-8")
        )
        targets = [e["target"] for e in manifest["managedFiles"]]
        self.assertFalse(
            any("xanadEval" in t for t in targets),
            f"xanadEval should be excluded from the install manifest; found: {[t for t in targets if 'xanadEval' in t]}",
        )

    def test_retired_mcp_servers_present_in_real_manifest(self) -> None:
        """install-manifest.json must contain the retiredMcpServers key (may be empty list)."""
        repo_root = Path(__file__).resolve().parents[2]
        manifest = json.loads(
            (repo_root / "template/setup/install-manifest.json").read_text(encoding="utf-8")
        )
        self.assertIn("retiredMcpServers", manifest)
        self.assertIsInstance(manifest["retiredMcpServers"], list)


class _CopiedPackageRoot:
    def __enter__(self) -> Path:
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp_root = Path(self._tmpdir.name)
        repo_root = Path(__file__).resolve().parents[2]

        for name in ("agents", "mcp", "packs", "skills", "template", "tools"):
            shutil.copytree(repo_root / name, tmp_root / name)
        shutil.copy2(repo_root / "VERSION", tmp_root / "VERSION")
        return tmp_root

    def __exit__(self, exc_type, exc, tb) -> None:
        self._tmpdir.cleanup()


if __name__ == "__main__":
    unittest.main()
