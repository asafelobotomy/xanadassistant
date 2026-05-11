from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class XanadAssistantPhase6Tests(XanadTestBase):
    """Phase 6: source resolution, integrity, stale-version, incomplete-install, dry-run."""

    def _apply(self, workspace: Path) -> dict:
        """Run a full apply in workspace and return the parsed payload."""
        result = self._run("apply", "--json", "--non-interactive", workspace=workspace)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    # ------------------------------------------------------------------
    # Source parsing – unit tests
    # ------------------------------------------------------------------

    def test_parse_github_source_valid(self) -> None:
        from scripts.lifecycle.xanadAssistant import parse_github_source, LifecycleCommandError

        owner, repo = parse_github_source("github:myorg/myrepo")
        self.assertEqual("myorg", owner)
        self.assertEqual("myrepo", repo)

    def test_parse_github_source_invalid_scheme(self) -> None:
        from scripts.lifecycle.xanadAssistant import parse_github_source, LifecycleCommandError

        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("bitbucket:owner/repo")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_parse_github_source_missing_repo(self) -> None:
        from scripts.lifecycle.xanadAssistant import parse_github_source, LifecycleCommandError

        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:owneronly")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_parse_github_source_too_many_slashes(self) -> None:
        from scripts.lifecycle.xanadAssistant import parse_github_source, LifecycleCommandError

        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:owner/repo/extra")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_parse_github_source_rejects_special_chars(self) -> None:
        from scripts.lifecycle.xanadAssistant import parse_github_source, LifecycleCommandError

        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:own!er/rep$o")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    # ------------------------------------------------------------------
    # Cache root – unit tests
    # ------------------------------------------------------------------

    def test_get_cache_root_default(self) -> None:
        import os
        from scripts.lifecycle.xanadAssistant import get_cache_root, DEFAULT_CACHE_ROOT

        env = os.environ.copy()
        env.pop("XANAD_PKG_CACHE", None)
        original = os.environ.get("XANAD_PKG_CACHE")
        try:
            if "XANAD_PKG_CACHE" in os.environ:
                del os.environ["XANAD_PKG_CACHE"]
            self.assertEqual(DEFAULT_CACHE_ROOT, get_cache_root())
        finally:
            if original is not None:
                os.environ["XANAD_PKG_CACHE"] = original

    def test_get_cache_root_env_override(self) -> None:
        import os
        from scripts.lifecycle.xanadAssistant import get_cache_root
        from pathlib import Path

        original = os.environ.get("XANAD_PKG_CACHE")
        try:
            os.environ["XANAD_PKG_CACHE"] = "/custom/cache"
            result = get_cache_root()
            self.assertEqual(Path("/custom/cache").resolve(), result)
        finally:
            if original is not None:
                os.environ["XANAD_PKG_CACHE"] = original
            else:
                os.environ.pop("XANAD_PKG_CACHE", None)

    # ------------------------------------------------------------------
    # resolve_effective_package_root – unit tests
    # ------------------------------------------------------------------

    def test_resolve_effective_no_args_raises(self) -> None:
        from scripts.lifecycle.xanadAssistant import resolve_effective_package_root, LifecycleCommandError

        with self.assertRaises(LifecycleCommandError) as ctx:
            resolve_effective_package_root(None, None, None, None)
        self.assertEqual("source_resolution_failure", ctx.exception.code)
        self.assertEqual(2, ctx.exception.exit_code)

    def test_resolve_effective_with_package_root(self) -> None:
        from scripts.lifecycle.xanadAssistant import resolve_effective_package_root

        pkg_root, source_info = resolve_effective_package_root(str(self.REPO_ROOT), None, None, None)
        self.assertEqual(self.REPO_ROOT, pkg_root)
        self.assertEqual("package-root", source_info["kind"])

    # ------------------------------------------------------------------
    # _build_lockfile_package_info – unit tests
    # ------------------------------------------------------------------

    def test_build_lockfile_package_info_default(self) -> None:
        from scripts.lifecycle.xanadAssistant import _State, _build_lockfile_package_info

        original = _State.session_source_info
        try:
            _State.session_source_info = None
            info = _build_lockfile_package_info()
        finally:
            _State.session_source_info = original
        self.assertEqual({"name": "xanadAssistant"}, info)

    def test_build_lockfile_package_info_with_release(self) -> None:
        from scripts.lifecycle.xanadAssistant import _State, _build_lockfile_package_info

        original = _State.session_source_info
        try:
            _State.session_source_info = {
                "kind": "github-release",
                "source": "github:myorg/myrepo",
                "version": "v1.2.3",
                "packageRoot": "/fake/path",
            }
            info = _build_lockfile_package_info()
        finally:
            _State.session_source_info = original
        self.assertEqual("xanadAssistant", info["name"])
        self.assertEqual("v1.2.3", info["version"])
        self.assertEqual("github:myorg/myrepo", info["source"])
        self.assertEqual("/fake/path", info["packageRoot"])
        self.assertNotIn("ref", info)

    def test_build_lockfile_package_info_with_package_root(self) -> None:
        from scripts.lifecycle.xanadAssistant import _State, _build_lockfile_package_info

        original = _State.session_source_info
        try:
            _State.session_source_info = {
                "kind": "package-root",
                "packageRoot": "/fake/local/xanadassistant",
            }
            info = _build_lockfile_package_info()
        finally:
            _State.session_source_info = original

        self.assertEqual("xanadAssistant", info["name"])
        self.assertEqual("/fake/local/xanadassistant", info["packageRoot"])

    # ------------------------------------------------------------------
    # verify_manifest_integrity – unit tests
    # ------------------------------------------------------------------

    def test_verify_manifest_integrity_no_lockfile(self) -> None:
        from scripts.lifecycle.xanadAssistant import verify_manifest_integrity

        ok, reason = verify_manifest_integrity(self.REPO_ROOT, {"present": False})
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_malformed_lockfile(self) -> None:
        from scripts.lifecycle.xanadAssistant import verify_manifest_integrity

        ok, reason = verify_manifest_integrity(
            self.REPO_ROOT, {"present": True, "malformed": True}
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_no_recorded_hash(self) -> None:
        from scripts.lifecycle.xanadAssistant import verify_manifest_integrity

        ok, reason = verify_manifest_integrity(
            self.REPO_ROOT,
            {"present": True, "malformed": False, "data": {"manifest": {}}},
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_hash_mismatch(self) -> None:
        from scripts.lifecycle.xanadAssistant import verify_manifest_integrity

        ok, reason = verify_manifest_integrity(
            self.REPO_ROOT,
            {
                "present": True,
                "malformed": False,
                "data": {"manifest": {"hash": "sha256:deadbeef0000000000000000000000000000000000000000000000000000dead"}},
            },
        )
        self.assertFalse(ok)
        self.assertIn("Manifest hash mismatch", reason)

    def test_classify_manifest_entries_requires_annotated_status(self) -> None:
        from scripts.lifecycle.xanadAssistant import classify_manifest_entries

        manifest = {
            "managedFiles": [
                {
                    "id": "prompts.setup.md",
                    "target": ".github/prompts/setup.md",
                    "hash": "sha256:test",
                }
            ],
            "retiredFiles": [],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            with self.assertRaisesRegex(ValueError, "must be annotated with status"):
                classify_manifest_entries(workspace, manifest)

    # ------------------------------------------------------------------
    # Stale-version warning – subprocess test
    # ------------------------------------------------------------------



if __name__ == "__main__":
    unittest.main()
