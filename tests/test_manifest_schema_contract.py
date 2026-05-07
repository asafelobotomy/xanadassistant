from __future__ import annotations

import unittest
from pathlib import Path

from scripts.lifecycle.generate_manifest import generate_manifest, load_json
from tests.schema_validation import validate_instance


class GeneratedManifestSchemaTests(unittest.TestCase):
    def test_generated_manifest_matches_schema_and_repo_output(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        policy = load_json(repo_root / "template/setup/install-policy.json")
        generated = generate_manifest(repo_root, policy)
        schema = load_json(repo_root / "template/setup/install-manifest.schema.json")
        written = load_json(repo_root / "template/setup/install-manifest.json")

        validate_instance(generated, schema, schema)
        self.assertEqual(written, generated)
        self.assertGreater(len(generated["managedFiles"]), 0)


if __name__ == "__main__":
    unittest.main()