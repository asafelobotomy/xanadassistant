"""Convergence and network integration tests.

Convergence tests verify that update/repair from a committed stale-consumer
fixture converges to the same final state as a fresh install from a local
package root.  These tests run without network access.

Network tests verify GitHub release and ref resolution against live endpoints.
They are gated by the XANAD_NETWORK_TESTS environment variable and are skipped
unless that variable is set to a non-empty value.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "lifecycle" / "xanad_assistant.py"
STALE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "stale-consumer"
NETWORK_TESTS = bool(os.getenv("XANAD_NETWORK_TESTS"))


def _run(command: str, *extra_args: str, workspace: Path) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT), command]
    if command == "plan" and extra_args and not extra_args[0].startswith("-"):
        cmd.append(extra_args[0])
        extra_args = extra_args[1:]
    cmd += ["--workspace", str(workspace), "--package-root", str(REPO_ROOT)]
    return subprocess.run(
        cmd + list(extra_args),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _apply_fresh(workspace: Path) -> subprocess.CompletedProcess[str]:
    return _run("apply", "--json", "--non-interactive", workspace=workspace)


def _normalise_lockfile(lockfile: dict) -> dict:
    """Strip timestamp and backup fields so two lockfiles can be compared structurally."""
    result = dict(lockfile)
    result.pop("timestamps", None)
    result.pop("lastBackup", None)
    result.get("package", {}).pop("version", None)
    return result


class StaleConsumerFixtureConvergenceTests(unittest.TestCase):
    """Verify that the committed stale-consumer fixture upgrades to the same
    final state as a fresh install from the local package root."""

    def _copy_fixture_to_temp(self) -> Path:
        tmp = tempfile.mkdtemp()
        shutil.copytree(STALE_FIXTURE, tmp, dirs_exist_ok=True)
        return Path(tmp)

    def tearDown(self) -> None:
        pass  # Each test manages its own temp dir cleanup.

    def test_stale_fixture_detected_as_installed(self) -> None:
        """Stale-consumer fixture is seen as installed (has lockfile)."""
        tmp = self._copy_fixture_to_temp()
        try:
            result = _run("inspect", "--json", workspace=tmp)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("installed", payload["result"]["installState"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_stale_fixture_triggers_package_version_changed_warning(self) -> None:
        """Stale lockfile hash triggers package_version_changed warning on inspect."""
        tmp = self._copy_fixture_to_temp()
        try:
            result = _run("inspect", "--json", workspace=tmp)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            warning_codes = [w["code"] for w in payload.get("warnings", [])]
            self.assertIn("package_version_changed", warning_codes)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_update_from_stale_fixture_succeeds(self) -> None:
        """update from the stale-consumer fixture exits 0 and reports validation passed."""
        tmp = self._copy_fixture_to_temp()
        try:
            result = _run("update", "--json", "--non-interactive", workspace=tmp)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("ok", payload["status"])
            self.assertEqual("passed", payload["result"]["validation"]["status"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_update_from_stale_fixture_writes_at_least_one_file(self) -> None:
        """update must write at least the stale setup.md prompt."""
        tmp = self._copy_fixture_to_temp()
        try:
            result = _run("update", "--json", "--non-interactive", workspace=tmp)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            total_writes = sum(payload["result"]["writes"].values())
            self.assertGreater(total_writes, 0, "Expected at least one write during update")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_update_from_stale_fixture_preserves_user_owned_blocks(self) -> None:
        """User-owned markdown blocks in copilot-instructions.md survive update."""
        tmp = self._copy_fixture_to_temp()
        try:
            result = _run("update", "--json", "--non-interactive", workspace=tmp)
            self.assertEqual(0, result.returncode, result.stderr)
            updated = (tmp / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
            self.assertIn("Custom project rule", updated)
            self.assertIn("This section is user-owned", updated)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_update_then_check_reports_clean(self) -> None:
        """After update, check reports no drift."""
        tmp = self._copy_fixture_to_temp()
        try:
            _run("update", "--json", "--non-interactive", workspace=tmp)
            result = _run("check", "--json", workspace=tmp)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("clean", payload["status"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_fresh_and_updated_lockfiles_converge(self) -> None:
        """A fresh install and an update from stale produce structurally equivalent lockfiles.

        Both runs use the same non-interactive defaults, so selectedPacks, profile,
        ownership, and manifest hash should match.  Timestamps and per-run backup
        metadata are stripped before comparison.
        """
        # Fresh install into a blank workspace.
        with tempfile.TemporaryDirectory() as fresh_tmp:
            fresh_ws = Path(fresh_tmp)
            fresh_result = _apply_fresh(fresh_ws)
            self.assertEqual(0, fresh_result.returncode, fresh_result.stderr)
            fresh_lockfile = json.loads(
                (fresh_ws / ".github" / "xanad-assistant-lock.json").read_text(encoding="utf-8")
            )

        # Update from committed stale fixture.
        stale_tmp = self._copy_fixture_to_temp()
        try:
            update_result = _run("update", "--json", "--non-interactive", workspace=stale_tmp)
            self.assertEqual(0, update_result.returncode, update_result.stderr)
            updated_lockfile = json.loads(
                (stale_tmp / ".github" / "xanad-assistant-lock.json").read_text(encoding="utf-8")
            )
        finally:
            shutil.rmtree(stale_tmp, ignore_errors=True)

        # Normalise and compare structurally significant fields.
        fresh_norm = _normalise_lockfile(fresh_lockfile)
        updated_norm = _normalise_lockfile(updated_lockfile)

        self.assertEqual(
            fresh_norm.get("selectedPacks"),
            updated_norm.get("selectedPacks"),
            "selectedPacks must match between fresh install and update from stale",
        )
        self.assertEqual(
            fresh_norm.get("profile"),
            updated_norm.get("profile"),
            "profile must match between fresh install and update from stale",
        )
        self.assertEqual(
            fresh_norm.get("manifest", {}).get("hash"),
            updated_norm.get("manifest", {}).get("hash"),
            "manifest hash must match between fresh install and update from stale",
        )
        self.assertEqual(
            fresh_norm.get("ownershipBySurface"),
            updated_norm.get("ownershipBySurface"),
            "ownershipBySurface must match between fresh install and update from stale",
        )


@unittest.skipUnless(NETWORK_TESTS, "Set XANAD_NETWORK_TESTS=1 to enable network integration tests")
class GitHubSourceResolutionNetworkTests(unittest.TestCase):
    """Integration tests that exercise real GitHub API/network calls.

    These tests are skipped by default.  Run them with:

        XANAD_NETWORK_TESTS=1 python3 -m unittest tests.test_convergence_and_network

    They require outbound HTTPS access to github.com.  They download small
    tarballs or run shallow clones, so they are not destructive.
    """

    CACHE_ROOT = Path(tempfile.gettempdir()) / "xanad-test-network-cache"

    def setUp(self) -> None:
        self.CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    def test_resolve_github_ref_clones_main_branch(self) -> None:
        """resolve_github_ref clones the main branch of asafelobotomy/xanadassistant."""
        from scripts.lifecycle.xanad_assistant import resolve_github_ref

        pkg_root = resolve_github_ref("asafelobotomy", "xanadassistant", "main", self.CACHE_ROOT)
        self.assertTrue(pkg_root.exists(), "Cloned package root should exist")
        # The repo must contain the manifest generator as a sanity check.
        self.assertTrue(
            (pkg_root / "scripts" / "lifecycle" / "generate_manifest.py").exists(),
            "Cloned repo should contain generate_manifest.py",
        )

    def test_resolve_github_ref_result_is_cached(self) -> None:
        """A second call to resolve_github_ref with the same ref reuses the cache."""
        from scripts.lifecycle.xanad_assistant import resolve_github_ref

        pkg_root_1 = resolve_github_ref("asafelobotomy", "xanadassistant", "main", self.CACHE_ROOT)
        pkg_root_2 = resolve_github_ref("asafelobotomy", "xanadassistant", "main", self.CACHE_ROOT)
        self.assertEqual(pkg_root_1, pkg_root_2, "Repeated calls should return the same path")

    def test_resolve_github_ref_package_is_usable(self) -> None:
        """A resolved GitHub-ref package root can be used for inspect."""
        from scripts.lifecycle.xanad_assistant import resolve_github_ref

        pkg_root = resolve_github_ref("asafelobotomy", "xanadassistant", "main", self.CACHE_ROOT)

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            cmd = [
                sys.executable, str(SCRIPT),
                "inspect",
                "--workspace", str(workspace),
                "--package-root", str(pkg_root),
                "--json",
            ]
            result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("inspect", payload["command"])
            self.assertEqual("ok", payload["status"])

    def test_local_and_github_ref_installs_converge(self) -> None:
        """A fresh install from local --package-root and from --source github:owner/repo
        produce lockfiles with the same manifest hash and selectedPacks.

        This is the Phase 6 convergence gate: release and local path installs
        must converge on the same final state.
        """
        from scripts.lifecycle.xanad_assistant import resolve_github_ref

        # Install from local package root.
        with tempfile.TemporaryDirectory() as local_tmp:
            local_ws = Path(local_tmp)
            local_result = _apply_fresh(local_ws)
            self.assertEqual(0, local_result.returncode, local_result.stderr)
            local_lockfile = json.loads(
                (local_ws / ".github" / "xanad-assistant-lock.json").read_text(encoding="utf-8")
            )

        # Install from GitHub-ref resolved package root.
        pkg_root = resolve_github_ref("asafelobotomy", "xanadassistant", "main", self.CACHE_ROOT)
        with tempfile.TemporaryDirectory() as remote_tmp:
            remote_ws = Path(remote_tmp)
            cmd = [
                sys.executable, str(SCRIPT),
                "apply",
                "--workspace", str(remote_ws),
                "--package-root", str(pkg_root),
                "--json", "--non-interactive",
            ]
            remote_result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(0, remote_result.returncode, remote_result.stderr)
            remote_lockfile = json.loads(
                (remote_ws / ".github" / "xanad-assistant-lock.json").read_text(encoding="utf-8")
            )

        local_norm = _normalise_lockfile(local_lockfile)
        remote_norm = _normalise_lockfile(remote_lockfile)

        self.assertEqual(
            local_norm.get("selectedPacks"),
            remote_norm.get("selectedPacks"),
        )
        self.assertEqual(
            local_norm.get("manifest", {}).get("hash"),
            remote_norm.get("manifest", {}).get("hash"),
            "Manifest hash must match between local and GitHub-ref installs",
        )


if __name__ == "__main__":
    unittest.main()
