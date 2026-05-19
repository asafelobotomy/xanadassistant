from __future__ import annotations

import io
import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from scripts import check_bump_version
from scripts.lifecycle._xanad._apply import build_copilot_version_summary
from scripts.lifecycle._xanad._merge import sha256_json


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


def _write_repo_fixture(
    repo_root: Path,
    *,
    version: str,
    manifest_version: str,
    summary_version: str,
    lockfile_manifest_hash: str | None = None,
    summary_manifest_hash: str | None = None,
) -> None:
    (repo_root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    _write_generate_stub(repo_root)

    manifest_path = repo_root / "template" / "setup" / "install-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_payload = {"schemaVersion": "0.1.0", "packageVersion": manifest_version}
    manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")

    lockfile_path = repo_root / ".github" / "xanadAssistant-lock.json"
    lockfile_path.parent.mkdir(parents=True, exist_ok=True)
    lockfile_payload = {
        "schemaVersion": "0.1.0",
        "package": {"name": "xanadAssistant"},
        "manifest": {"hash": lockfile_manifest_hash or sha256_json(manifest_payload)},
        "timestamps": {
            "appliedAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
        },
        "selectedPacks": [],
        "profile": "balanced",
    }
    lockfile_path.write_text(json.dumps(lockfile_payload, indent=2) + "\n", encoding="utf-8")

    summary_path = repo_root / ".github" / "copilot-version.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_lockfile = dict(lockfile_payload)
    summary_lockfile["manifest"] = {"hash": summary_manifest_hash or lockfile_payload["manifest"]["hash"]}
    summary_manifest = {"schemaVersion": "0.1.0", "packageVersion": summary_version}
    summary_path.write_text(build_copilot_version_summary(summary_lockfile, summary_manifest), encoding="utf-8")


class CheckBumpVersionTests(unittest.TestCase):
    def test_check_mode_reports_stale_references_without_updating(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_fixture(
                repo_root,
                version="1.2.3",
                manifest_version="0.9.0",
                summary_version="0.9.0",
                lockfile_manifest_hash="sha256:stale",
                summary_manifest_hash="sha256:stale",
            )

            exit_code = check_bump_version.main(
                ["--repo-root", str(repo_root), "--check"],
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                quiet=True,
            )

            manifest = json.loads((repo_root / "template" / "setup" / "install-manifest.json").read_text(encoding="utf-8"))
            lockfile = json.loads((repo_root / ".github" / "xanadAssistant-lock.json").read_text(encoding="utf-8"))
            summary = (repo_root / ".github" / "copilot-version.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 1)
        self.assertEqual(manifest["packageVersion"], "0.9.0")
        self.assertEqual(lockfile["manifest"]["hash"], "sha256:stale")
        self.assertIn("Version: 0.9.0", summary)
        self.assertIn('"manifestHash": "sha256:stale"', summary)

    def test_main_updates_manifest_lockfile_and_summary_to_match_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_fixture(
                repo_root,
                version="1.2.3",
                manifest_version="0.9.0",
                summary_version="0.9.0",
                lockfile_manifest_hash="sha256:stale",
                summary_manifest_hash="sha256:stale",
            )

            exit_code = check_bump_version.main(
                ["--repo-root", str(repo_root)],
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                quiet=True,
            )

            manifest = json.loads((repo_root / "template" / "setup" / "install-manifest.json").read_text(encoding="utf-8"))
            lockfile = json.loads((repo_root / ".github" / "xanadAssistant-lock.json").read_text(encoding="utf-8"))
            summary = (repo_root / ".github" / "copilot-version.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertEqual(manifest["packageVersion"], "1.2.3")
        self.assertEqual(lockfile["manifest"]["hash"], sha256_json(manifest))
        self.assertIn("Version: 1.2.3", summary)
        self.assertIn('"version": "1.2.3"', summary)
        self.assertIn(f'"manifestHash": "{sha256_json(manifest)}"', summary)

    def test_main_returns_zero_when_references_are_already_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_fixture(repo_root, version="1.2.3", manifest_version="1.2.3", summary_version="1.2.3")

            exit_code = check_bump_version.main(
                ["--repo-root", str(repo_root), "--check"],
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                quiet=True,
            )

        self.assertEqual(exit_code, 0)

    def test_check_mode_reports_stale_lockfile_even_when_versions_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_fixture(
                repo_root,
                version="1.2.3",
                manifest_version="1.2.3",
                summary_version="1.2.3",
                lockfile_manifest_hash="sha256:stale",
                summary_manifest_hash="sha256:stale",
            )

            exit_code = check_bump_version.main(
                ["--repo-root", str(repo_root), "--check"],
                stdout=io.StringIO(),
                stderr=io.StringIO(),
                quiet=True,
            )

        self.assertEqual(exit_code, 1)

    def test_main_restores_artifacts_when_later_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            _write_repo_fixture(
                repo_root,
                version="1.2.3",
                manifest_version="0.9.0",
                summary_version="0.9.0",
                lockfile_manifest_hash="sha256:stale",
                summary_manifest_hash="sha256:stale",
            )
            manifest_before = (repo_root / "template" / "setup" / "install-manifest.json").read_text(encoding="utf-8")
            lockfile_before = (repo_root / ".github" / "xanadAssistant-lock.json").read_text(encoding="utf-8")
            summary_before = (repo_root / ".github" / "copilot-version.md").read_text(encoding="utf-8")

            real_write = check_bump_version._write_text_atomic

            summary_write_attempts = 0

            def fail_on_summary(path: Path, text: str) -> None:
                nonlocal summary_write_attempts
                if path.name == "copilot-version.md" and summary_write_attempts == 0:
                    summary_write_attempts += 1
                    raise RuntimeError("summary write failed")
                real_write(path, text)

            with mock.patch("scripts.check_bump_version._write_text_atomic", side_effect=fail_on_summary):
                exit_code = check_bump_version.main(
                    ["--repo-root", str(repo_root)],
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                    quiet=True,
                )

            manifest_after = (repo_root / "template" / "setup" / "install-manifest.json").read_text(encoding="utf-8")
            lockfile_after = (repo_root / ".github" / "xanadAssistant-lock.json").read_text(encoding="utf-8")
            summary_after = (repo_root / ".github" / "copilot-version.md").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 2)
        self.assertEqual(manifest_after, manifest_before)
        self.assertEqual(lockfile_after, lockfile_before)
        self.assertEqual(summary_after, summary_before)


if __name__ == "__main__":
    unittest.main()