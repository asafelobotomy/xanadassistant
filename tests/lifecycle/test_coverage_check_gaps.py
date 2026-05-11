"""Tests for check, check-loc, and manifest-freshness coverage gaps."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]


class CheckGapTests(unittest.TestCase):
    def _make_ws_with_lockfile(self, tmp: Path, lockfile: dict) -> Path:
        ws = tmp / "ws"
        (ws / ".github").mkdir(parents=True)
        (ws / ".github" / "xanadAssistant-lock.json").write_text(
            json.dumps(lockfile), encoding="utf-8"
        )
        return ws

    def test_build_check_result_malformed_lockfile(self):
        """Line 20: counts['malformed'] += 1 when lockfile is malformed."""
        from scripts.lifecycle._xanad._check import build_check_result
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            (ws / ".github").mkdir(parents=True)
            (ws / ".github" / "xanadAssistant-lock.json").write_text(
                "this is not valid JSON {{{", encoding="utf-8"
            )
            result = build_check_result(ws, REPO_ROOT)
        self.assertGreater(result["result"]["summary"]["malformed"], 0)

    def test_build_check_result_malformed_legacy_version_file(self):
        """_check.py line 22: counts['malformed'] += 1 when legacyVersionState is malformed."""
        from scripts.lifecycle._xanad._check import build_check_result
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            (ws / ".github").mkdir(parents=True)
            # A copilot-version.md with no json block and no version: line is malformed
            (ws / ".github" / "copilot-version.md").write_text(
                "# No version info here\nJust some text without a version field.",
                encoding="utf-8",
            )
            result = build_check_result(ws, REPO_ROOT)
        self.assertGreater(result["result"]["summary"]["malformed"], 0)

    def test_build_check_result_skipped_files_not_in_targets(self):
        """Lines 29-30: skippedManagedFiles entries not in recorded_targets get appended."""
        from scripts.lifecycle._xanad._check import build_check_result
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanadAssistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:fake"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [], "profile": "balanced",
                "ownershipBySurface": {}, "files": [],
                # This file is skipped and definitely NOT a managed target → new skipped entry added
                "skippedManagedFiles": [".github/custom-completely-unique-file-xyz.md"],
            }
            ws = self._make_ws_with_lockfile(Path(tmp), lockfile)
            result = build_check_result(ws, REPO_ROOT)
        skipped_entries = [e for e in result["result"]["entries"] if e["status"] == "skipped"]
        targets = [e["target"] for e in skipped_entries]
        self.assertIn(".github/custom-completely-unique-file-xyz.md", targets)

    def test_build_check_result_unknown_file_status(self):
        """Lines 36-37: files with status 'unknown' in lockfile get counted."""
        from scripts.lifecycle._xanad._check import build_check_result
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanadAssistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:fake"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [], "profile": "balanced",
                "ownershipBySurface": {}, "files": [
                    {"id": "test.unknown", "target": ".github/some-unknown-file.md", "status": "unknown"},
                ],
            }
            ws = self._make_ws_with_lockfile(Path(tmp), lockfile)
            result = build_check_result(ws, REPO_ROOT)
        unknown_entries = [e for e in result["result"]["entries"] if e.get("status") == "unknown"]
        self.assertGreater(len(unknown_entries), 0)


# ---------------------------------------------------------------------------
# _main.py lines 142-148
# ---------------------------------------------------------------------------

class MainPlanFactoryRestoreTests(unittest.TestCase):
    def test_plan_factory_restore_on_not_installed_workspace_triggers_error(self):
        """Lines 142-148: LifecycleCommandError handler in plan command."""
        from scripts.lifecycle._xanad._main import main
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            # workspace has no .github dir → install_state == "not-installed"
            exit_code = main([
                "plan", "factory-restore",
                "--workspace", str(workspace),
                "--package-root", str(REPO_ROOT),
                "--json",
                "--non-interactive",
            ])
        # Should return a nonzero exit code (not crash)
        self.assertNotEqual(0, exit_code)


# ---------------------------------------------------------------------------
# check_loc.py lines 54-57
# ---------------------------------------------------------------------------

class CheckLocFallbackTests(unittest.TestCase):
    def test_collect_files_falls_back_when_subprocess_fails(self):
        """Lines 54-57: fallback os.walk when git ls-files raises CalledProcessError."""
        import scripts.check_loc as check_loc_mod
        error = subprocess.CalledProcessError(1, ["git", "ls-files"])
        with patch("subprocess.run", side_effect=error):
            files = check_loc_mod.collect_files([])
        # Should return a list of paths (from os.walk fallback), not raise
        self.assertIsInstance(files, list)


# ---------------------------------------------------------------------------
# check_manifest_freshness.py lines 59-61, 70-72
# ---------------------------------------------------------------------------

class CheckManifestFreshnessTests(unittest.TestCase):
    def test_main_stale_manifest_returns_exit_code_1(self):
        """Lines 59-61: stale manifest prints error message and returns 1."""
        from scripts.lifecycle.check_manifest_freshness import main as fresh_main
        import io
        with tempfile.TemporaryDirectory() as tmp:
            # Write a stale manifest (empty dict) to a temp file
            stale_manifest = Path(tmp) / "stale-manifest.json"
            stale_manifest.write_text('{"schemaVersion":"0.1.0","managedFiles":[],"retiredFiles":[]}',
                                     encoding="utf-8")
            policy_path = str(REPO_ROOT / "template" / "setup" / "install-policy.json")
            argv = [
                "check_manifest_freshness",
                "--package-root", str(REPO_ROOT),
                "--policy", policy_path,
                "--manifest", str(stale_manifest),
            ]
            with patch("sys.argv", argv), patch("sys.stderr", new_callable=io.StringIO):
                exit_code = fresh_main()
        self.assertEqual(1, exit_code)

    def test_main_stale_catalog_returns_exit_code_1(self):
        """Lines 70-72: stale catalog prints error message and returns 1."""
        from scripts.lifecycle.check_manifest_freshness import main as fresh_main
        import io
        with tempfile.TemporaryDirectory() as tmp:
            stale_catalog = Path(tmp) / "stale-catalog.json"
            stale_catalog.write_text('{"commands":[]}', encoding="utf-8")
            policy_path = str(REPO_ROOT / "template" / "setup" / "install-policy.json")
            real_manifest = str(REPO_ROOT / "template" / "setup" / "install-manifest.json")
            argv = [
                "check_manifest_freshness",
                "--package-root", str(REPO_ROOT),
                "--policy", policy_path,
                "--manifest", real_manifest,
                "--catalog", str(stale_catalog),
            ]
            with patch("sys.argv", argv), patch("sys.stderr", new_callable=io.StringIO):
                exit_code = fresh_main()
        self.assertEqual(1, exit_code)


# ---------------------------------------------------------------------------
# generate_manifest.py lines 100, 103, 151, 153
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
