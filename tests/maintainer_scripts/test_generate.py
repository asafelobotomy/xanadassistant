from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import generate


class GenerateScriptTests(unittest.TestCase):
    def test_main_returns_error_for_missing_or_malformed_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            stderr = io.StringIO()
            fake_file = repo_root / "scripts" / "generate.py"
            fake_file.parent.mkdir(parents=True)
            fake_file.write_text("# stub\n", encoding="utf-8")

            with mock.patch("scripts.generate.__file__", str(fake_file)), redirect_stderr(stderr):
                missing_exit = generate.main()

            policy_path = repo_root / "template" / "setup" / "install-policy.json"
            policy_path.parent.mkdir(parents=True)
            policy_path.write_text("{bad", encoding="utf-8")
            stderr = io.StringIO()
            with mock.patch("scripts.generate.__file__", str(fake_file)), redirect_stderr(stderr):
                malformed_exit = generate.main()

        self.assertEqual(missing_exit, 1)
        self.assertEqual(malformed_exit, 1)

    def test_main_generates_manifest_and_optional_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            fake_file = repo_root / "scripts" / "generate.py"
            fake_file.parent.mkdir(parents=True)
            fake_file.write_text("# stub\n", encoding="utf-8")
            policy_path = repo_root / "template" / "setup" / "install-policy.json"
            policy_path.parent.mkdir(parents=True)
            policy_path.write_text(
                json.dumps({
                    "generationSettings": {
                        "manifestOutput": "template/setup/install-manifest.json",
                        "derivedArtifactStrategy": {"catalog": "generated-from-policy-and-registries"},
                    }
                }),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with mock.patch("scripts.generate.__file__", str(fake_file)), mock.patch(
                "scripts.generate.generate_manifest",
                return_value={"managedFiles": []},
            ) as generate_manifest, mock.patch(
                "scripts.generate.write_manifest"
            ) as write_manifest, mock.patch(
                "scripts.generate.load_optional_registry",
                side_effect=[{"packs": []}, {"profiles": []}],
            ), mock.patch(
                "scripts.generate.generate_catalog",
                return_value={"entries": []},
            ) as generate_catalog, redirect_stdout(stdout):
                exit_code = generate.main()

        self.assertEqual(exit_code, 0)
        self.assertTrue(generate_manifest.called)
        self.assertTrue(generate_catalog.called)
        self.assertEqual(write_manifest.call_count, 2)
        self.assertIn("manifest", stdout.getvalue())
        self.assertIn("catalog", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()