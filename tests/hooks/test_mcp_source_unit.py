"""Direct unit tests for hooks/scripts/_xanad_mcp_source.py."""

from __future__ import annotations

import io
import shutil
import tarfile as _tarfile_mod
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys

# The hook scripts are not on the standard module path; add the hooks dir temporarily.
_HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks" / "scripts"


def _import_mcp_source():
    """Import _xanad_mcp_source from the hooks directory."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_xanad_mcp_source",
        str(_HOOKS_DIR / "_xanad_mcp_source.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mcp_source = _import_mcp_source()


class ParseGithubSourceMcpTests(unittest.TestCase):
    def test_parses_valid_source(self) -> None:
        owner, repo = _mcp_source.parse_github_source("github:octocat/hello-world")
        self.assertEqual("octocat", owner)
        self.assertEqual("hello-world", repo)

    def test_raises_for_missing_github_prefix(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _mcp_source.parse_github_source("https://github.com/owner/repo")
        self.assertIn("Unsupported source scheme", str(ctx.exception))

    def test_raises_for_missing_slash(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _mcp_source.parse_github_source("github:ownerrepo")
        self.assertIn("Invalid GitHub source", str(ctx.exception))

    def test_raises_for_extra_slash_in_repo(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _mcp_source.parse_github_source("github:owner/repo/extra")
        self.assertIn("Invalid GitHub source", str(ctx.exception))

    def test_raises_for_invalid_characters_in_owner(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _mcp_source.parse_github_source("github:owner@bad/repo")
        self.assertIn("invalid characters", str(ctx.exception))

    def test_raises_for_empty_owner(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _mcp_source.parse_github_source("github:/repo")
        self.assertIn("Invalid GitHub source", str(ctx.exception))

    def test_raises_for_empty_repo(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _mcp_source.parse_github_source("github:owner/")
        self.assertIn("Invalid GitHub source", str(ctx.exception))

    def test_safe_github_name_pattern_accepts_valid_names(self) -> None:
        import re
        pattern = _mcp_source.SAFE_GITHUB_NAME
        self.assertIsNotNone(pattern.match("my-repo"))
        self.assertIsNotNone(pattern.match("my.repo"))
        self.assertIsNotNone(pattern.match("myRepo123"))

    def test_safe_github_name_pattern_rejects_invalid_names(self) -> None:
        pattern = _mcp_source.SAFE_GITHUB_NAME
        self.assertIsNone(pattern.match("my repo"))
        self.assertIsNone(pattern.match("my@repo"))


# ---------------------------------------------------------------------------
# resolve_github_release — tarball path-traversal safety
# ---------------------------------------------------------------------------

def _make_tarball(members: list[tuple[str, bytes | None]]) -> bytes:
    """Build an in-memory .tar.gz with the given (name, content) pairs.

    Pass ``content=None`` for a directory entry.
    """
    buf = io.BytesIO()
    with _tarfile_mod.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in members:
            if content is None:
                info = _tarfile_mod.TarInfo(name=name)
                info.type = _tarfile_mod.DIRTYPE
                info.mode = 0o755
                tar.addfile(info)
            else:
                info = _tarfile_mod.TarInfo(name=name)
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _response_mock(tarball_bytes: bytes) -> MagicMock:
    """Return a context-manager mock that yields the tarball bytes on .read()."""
    mock = MagicMock()
    mock.read.return_value = tarball_bytes
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


class ResolveGithubReleaseSafetyTests(unittest.TestCase):
    """Path-traversal safety tests for resolve_github_release."""

    def _resolve(self, tarball_bytes: bytes) -> tuple[Path, str]:
        """Invoke resolve_github_release with a mocked network response.

        Returns ``(cache_dir, tmp_root)``; caller must clean up ``tmp_root``.
        """
        tmp_root = tempfile.mkdtemp()
        cache_root = Path(tmp_root) / "cache"
        with patch("urllib.request.urlopen", return_value=_response_mock(tarball_bytes)):
            cache_dir = _mcp_source.resolve_github_release(
                "owner", "repo", "v1.0.0", cache_root
            )
        return cache_dir, tmp_root

    def test_safe_member_is_extracted(self) -> None:
        """A well-formed member is written to the cache directory."""
        tarball = _make_tarball([
            ("repo-v1.0.0/README.md", b"# hello"),
        ])
        cache_dir, tmp_root = self._resolve(tarball)
        try:
            self.assertTrue((cache_dir / "README.md").exists())
            self.assertEqual((cache_dir / "README.md").read_bytes(), b"# hello")
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_dotdot_traversal_is_skipped(self) -> None:
        """Members with '..' components are silently skipped; safe peers still extracted."""
        tarball = _make_tarball([
            ("repo-v1.0.0/safe.txt", b"safe"),
            ("repo-v1.0.0/../evil.txt", b"evil"),
        ])
        cache_dir, tmp_root = self._resolve(tarball)
        try:
            # Safe file is present.
            self.assertTrue((cache_dir / "safe.txt").exists())
            # The traversal target must not exist outside the cache dir.
            self.assertFalse((cache_dir.parent / "evil.txt").exists())
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_top_level_only_member_is_skipped(self) -> None:
        """Members with no path components after the top-level dir are skipped."""
        tarball = _make_tarball([
            ("repo-v1.0.0", None),              # directory entry, only 1 part
            ("repo-v1.0.0/real.txt", b"real"),  # normal file
        ])
        cache_dir, tmp_root = self._resolve(tarball)
        try:
            # Only the real file should exist; no junk at root.
            self.assertTrue((cache_dir / "real.txt").exists())
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_absolute_member_name_is_contained(self) -> None:
        """A tarball member whose name begins with '/' is never written to the
        filesystem root — it is either skipped (single component) or redirected
        to inside the cache dir (multi-component)."""
        tarball = _make_tarball([
            ("repo-v1.0.0/safe.txt", b"safe"),
            ("/etc/xanad_test_evil.txt", b"evil"),  # absolute top-level member
        ])
        cache_dir, tmp_root = self._resolve(tarball)
        try:
            # Safe peer is present.
            self.assertTrue((cache_dir / "safe.txt").exists())
            # The absolute-path member must never land at the real /etc.
            self.assertFalse(Path("/etc/xanad_test_evil.txt").exists())
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)


    def test_sentinel_file_written_on_success(self) -> None:
        """resolve_github_release writes a .complete sentinel after successful extraction."""
        tarball = _make_tarball([("repo-v1.0.0/f.txt", b"x")])
        cache_dir, tmp_root = self._resolve(tarball)
        try:
            self.assertTrue((cache_dir / ".complete").exists())
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_cached_result_skips_network(self) -> None:
        """A pre-existing .complete sentinel causes early return without a network call."""
        tmp_root = tempfile.mkdtemp()
        try:
            cache_root = Path(tmp_root) / "cache"
            # Pre-create the sentinel.
            safe_version = "v1.0.0"
            import re as _re
            safe_ver = _re.sub(r"[^A-Za-z0-9._-]", "-", safe_version)
            cache_dir = cache_root / "github" / "owner-repo" / f"release-{safe_ver}"
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / ".complete").write_text("ok\n", encoding="utf-8")
            # urlopen must never be called.
            with patch("urllib.request.urlopen") as mock_open:
                result = _mcp_source.resolve_github_release(
                    "owner", "repo", safe_version, cache_root
                )
                mock_open.assert_not_called()
            self.assertEqual(result, cache_dir)
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

