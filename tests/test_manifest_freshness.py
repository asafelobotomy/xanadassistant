from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle.check_manifest_freshness import compare_manifest_to_generated
from scripts.lifecycle.generate_manifest import generate_manifest, write_manifest


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


if __name__ == "__main__":
    unittest.main()