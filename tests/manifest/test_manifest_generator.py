from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle.generate_manifest import generate_manifest, write_manifest


class ManifestGeneratorTests(unittest.TestCase):
    def make_policy(self) -> dict:
        return {
            "schemaVersion": "0.1.0",
            "canonicalSurfaces": ["prompts"],
            "sourceRoots": {
                "template": "template"
            },
            "surfaceSources": {
                "prompts": {
                    "sourceRoot": "template",
                    "path": "prompts",
                    "kind": "directory",
                    "layer": "core"
                }
            },
            "targetPathRules": {
                "prompts": {
                    "targetRoot": ".github/prompts",
                    "surface": "prompts"
                }
            },
            "ownershipDefaults": {
                "prompts": "local"
            },
            "strategyDefaults": {
                "prompts": "replace-verbatim"
            },
            "retiredFilePolicy": {
                "defaultAction": "report-retired",
                "entries": []
            },
            "generationSettings": {
                "manifestSchemaVersion": "0.1.0",
                "includeRetiredFiles": True,
                "unmanagedSourceExcludes": []
            }
        }

    def test_generate_manifest_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            prompts_dir = package_root / "template" / "prompts"
            prompts_dir.mkdir(parents=True)
            (prompts_dir / "review.md").write_text("hello\n", encoding="utf-8")
            (prompts_dir / "setup.md").write_text("world\n", encoding="utf-8")

            policy = self.make_policy()

            first = generate_manifest(package_root, policy)
            second = generate_manifest(package_root, policy)

            self.assertEqual(first, second)
            self.assertEqual(2, len(first["managedFiles"]))

    def test_generate_manifest_shapes_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            prompts_dir = package_root / "template" / "prompts"
            prompts_dir.mkdir(parents=True)
            (prompts_dir / "review.md").write_text("hello {{WORKSPACE_NAME}}\n", encoding="utf-8")

            policy = self.make_policy()
            policy["strategyDefaults"]["prompts"] = "token-replace"
            policy["tokenRules"] = [{"token": "{{WORKSPACE_NAME}}", "required": False}]

            manifest = generate_manifest(package_root, policy)
            entry = manifest["managedFiles"][0]

            self.assertEqual("prompts", entry["surface"])
            self.assertEqual("core", entry["layer"])
            self.assertEqual(["local"], entry["ownership"])
            self.assertEqual("token-replace", entry["strategy"])
            self.assertEqual("template/prompts/review.md", entry["source"])
            self.assertEqual(".github/prompts/review.md", entry["target"])
            self.assertEqual(["{{WORKSPACE_NAME}}"], entry["tokens"])
            self.assertTrue(entry["hash"].startswith("sha256:"))

    def test_generate_manifest_fails_when_source_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)

            with self.assertRaisesRegex(ValueError, "Managed source directory is missing"):
                generate_manifest(package_root, self.make_policy())

    def test_generate_manifest_fails_on_unmanaged_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            prompts_dir = package_root / "template" / "prompts"
            prompts_dir.mkdir(parents=True)
            (prompts_dir / "setup.md").write_text("world\n", encoding="utf-8")
            (package_root / "template" / "extra.md").write_text("extra\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Managed source files lack policy coverage"):
                generate_manifest(package_root, self.make_policy())

    def test_generate_manifest_includes_retired_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir)
            prompts_dir = package_root / "template" / "prompts"
            prompts_dir.mkdir(parents=True)
            (prompts_dir / "setup.md").write_text("world\n", encoding="utf-8")

            policy = self.make_policy()
            policy["retiredFilePolicy"]["entries"] = [
                {
                    "id": "retired.prompt.old",
                    "target": ".github/prompts/old.md",
                    "defaultAction": "report-retired"
                }
            ]

            manifest = generate_manifest(package_root, policy)
            self.assertEqual(1, len(manifest["retiredFiles"]))
            self.assertEqual("retired.prompt.old", manifest["retiredFiles"][0]["id"])

    def test_write_manifest_writes_stable_json_with_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "manifest.json"
            manifest = {
                "schemaVersion": "0.1.0",
                "managedFiles": [],
                "retiredFiles": []
            }

            write_manifest(output_path, manifest)

            written = output_path.read_text(encoding="utf-8")
            self.assertTrue(written.endswith("\n"))
            self.assertEqual(manifest, json.loads(written))


if __name__ == "__main__":
    unittest.main()