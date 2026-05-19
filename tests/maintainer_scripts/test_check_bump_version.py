from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts import check_bump_version


def _write_generate_stub(repo_root: Path) -> None:
    script = repo_root / "scripts" / "generate.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            from pathlib import Path

            repo_root = Path(__file__).resolve().parents[1]
            version = (repo_root / "VERSION").read_text(encoding="utf-8").strip()
            manifest_path = repo_root / "template" / "setup" / "install-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["packageVersion"] = version
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\\n", encoding="utf-8")
            print("manifest refreshed")
            """
        ),
        encoding="utf-8",
    )


def _write_repo_fixture(repo_root: Path, *, version: str, manifest_version: str, summary_version: str) -> None:
    (repo_root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    _write_generate_stub(repo_root)

    manifest_path = repo_root / "template" / "setup" / "install-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({"schemaVersion": "0.1.0", "packageVersion": manifest_version}, indent=2) + "\n",
        encoding="utf-8",
    )

    summary_path = repo_root / ".github" / "copilot-version.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        textwrap.dedent(
            f"""\
            # xanadAssistant Installed Summary

            Version: {summary_version}
            Profile: balanced

            ```json
            {{
              "version": "{summary_version}"
            }}
            ```
            """
        ),
        encoding="utf-8",
    )


class CheckBumpVersionTests(unittest.TestCase):
    def test_check_mode_reports_stale_references_without_updating(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_fixture(repo_root, version="1.2.3", manifest_version="0.9.0", summary_version="0.9.0")

            exit_code = check_bump_version.main(["--repo-root", str(repo_root), "--check"])

            manifest = json.loads((repo_root / "template" / "setup" / "install-manifest.json").read_text(encoding="utf-8"))
            summary = (repo_root / ".github" / "copilot-version.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 1)
        self.assertEqual(manifest["packageVersion"], "0.9.0")
        self.assertIn("Version: 0.9.0", summary)
        self.assertIn('"version": "0.9.0"', summary)

    def test_main_updates_manifest_and_summary_to_match_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_fixture(repo_root, version="1.2.3", manifest_version="0.9.0", summary_version="0.9.0")

            exit_code = check_bump_version.main(["--repo-root", str(repo_root)])

            manifest = json.loads((repo_root / "template" / "setup" / "install-manifest.json").read_text(encoding="utf-8"))
            summary = (repo_root / ".github" / "copilot-version.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(manifest["packageVersion"], "1.2.3")
        self.assertIn("Version: 1.2.3", summary)
        self.assertIn('"version": "1.2.3"', summary)

    def test_main_returns_zero_when_references_are_already_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_fixture(repo_root, version="1.2.3", manifest_version="1.2.3", summary_version="1.2.3")

            exit_code = check_bump_version.main(["--repo-root", str(repo_root), "--check"])

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()