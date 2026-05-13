"""Unit tests for xanadBootstrap.py.

Tests cover argv shaping, cache-path selection, source validation, and error
messages without exercising any network calls or subprocess invocations.
"""
from __future__ import annotations

import importlib.util
import io
import sys
import tarfile as tarfile_module
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]

# Load xanadBootstrap.py as a module without importing it as a package.
_BOOTSTRAP_PATH = REPO_ROOT / "xanadBootstrap.py"
_spec = importlib.util.spec_from_file_location("xanadBootstrap", _BOOTSTRAP_PATH)
_bootstrap = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_bootstrap)  # type: ignore[union-attr]


class ValidateSourceTests(unittest.TestCase):
    def test_valid_source_returns_owner_and_repo(self) -> None:
        owner, repo = _bootstrap._validate_source("github:asafelobotomy/xanadAssistant")
        self.assertEqual("asafelobotomy", owner)
        self.assertEqual("xanadAssistant", repo)

    def test_missing_github_prefix_exits(self) -> None:
        with self.assertRaises(SystemExit):
            _bootstrap._validate_source("notgithub:owner/repo")

    def test_missing_slash_exits(self) -> None:
        with self.assertRaises(SystemExit):
            _bootstrap._validate_source("github:owneronly")

    def test_extra_slash_exits(self) -> None:
        with self.assertRaises(SystemExit):
            _bootstrap._validate_source("github:owner/repo/extra")

    def test_invalid_characters_exit(self) -> None:
        with self.assertRaises(SystemExit):
            _bootstrap._validate_source("github:owner/repo name")

    def test_empty_owner_exits(self) -> None:
        with self.assertRaises(SystemExit):
            _bootstrap._validate_source("github:/repo")

    def test_empty_repo_exits(self) -> None:
        with self.assertRaises(SystemExit):
            _bootstrap._validate_source("github:owner/")


class ArchiveUrlTests(unittest.TestCase):
    def test_version_tag_uses_tags_url(self) -> None:
        url = _bootstrap._archive_url("owner", "repo", "v1.0.0")
        self.assertIn("/tags/v1.0.0", url)
        self.assertIn("github.com/owner/repo", url)

    def test_branch_ref_uses_heads_url(self) -> None:
        url = _bootstrap._archive_url("owner", "repo", "main")
        self.assertIn("/heads/main", url)
        self.assertIn("github.com/owner/repo", url)

    def test_non_version_ref_uses_heads_url(self) -> None:
        url = _bootstrap._archive_url("owner", "repo", "feature-branch")
        self.assertIn("/heads/feature-branch", url)


class SafeSlugTests(unittest.TestCase):
    def test_safe_characters_unchanged(self) -> None:
        self.assertEqual("v1.0.0", _bootstrap._safe_slug("v1.0.0"))

    def test_unsafe_characters_replaced(self) -> None:
        result = _bootstrap._safe_slug("my branch/name!")
        self.assertNotIn("/", result)
        self.assertNotIn("!", result)
        self.assertNotIn(" ", result)

    def test_alphanumeric_unchanged(self) -> None:
        self.assertEqual("abc123", _bootstrap._safe_slug("abc123"))


class ResolvePackageRootTests(unittest.TestCase):
    def test_package_root_arg_returns_resolved_path(self) -> None:
        result = _bootstrap._resolve_package_root(
            str(REPO_ROOT), "github:a/b", None, REPO_ROOT
        )
        self.assertEqual(REPO_ROOT, result)

    def test_missing_package_root_exits(self) -> None:
        with self.assertRaises(SystemExit):
            _bootstrap._resolve_package_root(
                "/nonexistent/path/does/not/exist", "github:a/b", None, REPO_ROOT
            )

    def test_downloads_when_no_package_root_with_version(self) -> None:
        fake_path = REPO_ROOT
        with patch.object(_bootstrap, "_download_archive", return_value=fake_path) as mock_dl:
            result = _bootstrap._resolve_package_root(
                None, "github:owner/repo", "v1.0.0", REPO_ROOT
            )
        mock_dl.assert_called_once_with("owner", "repo", "v1.0.0", REPO_ROOT)
        self.assertEqual(fake_path, result)

    def test_defaults_to_main_when_no_version(self) -> None:
        fake_path = REPO_ROOT
        with patch.object(_bootstrap, "_download_archive", return_value=fake_path) as mock_dl:
            _bootstrap._resolve_package_root(None, "github:owner/repo", None, REPO_ROOT)
        mock_dl.assert_called_once_with("owner", "repo", "main", REPO_ROOT)

    def test_invalid_source_exits_before_download(self) -> None:
        with self.assertRaises(SystemExit):
            _bootstrap._resolve_package_root(None, "badscheme:owner/repo", None, REPO_ROOT)


class BuildCliCommandTests(unittest.TestCase):
    def _make_args(
        self,
        command: str,
        mode: str | None = None,
        workspace: str = ".",
    ) -> MagicMock:
        args = MagicMock()
        args.command = command
        args.mode = mode
        args.workspace = workspace
        return args

    def test_inspect_command_shape(self) -> None:
        args = self._make_args("inspect")
        cmd = _bootstrap._build_cli_command(REPO_ROOT, args, ["--json"])
        self.assertIn("xanadAssistant.py", cmd[1])
        self.assertEqual("inspect", cmd[2])
        self.assertIn("--json", cmd)
        self.assertIn("--package-root", cmd)
        self.assertIn(str(REPO_ROOT), cmd)

    def test_apply_command_shape(self) -> None:
        args = self._make_args("apply")
        cmd = _bootstrap._build_cli_command(REPO_ROOT, args, ["--non-interactive", "--json"])
        self.assertEqual("apply", cmd[2])
        self.assertIn("--non-interactive", cmd)

    def test_plan_setup_includes_mode(self) -> None:
        args = self._make_args("plan", mode="setup")
        cmd = _bootstrap._build_cli_command(REPO_ROOT, args, ["--non-interactive"])
        self.assertEqual("plan", cmd[2])
        self.assertEqual("setup", cmd[3])
        self.assertIn("--non-interactive", cmd)

    def test_plan_without_mode_exits(self) -> None:
        args = self._make_args("plan", mode=None)
        with self.assertRaises(SystemExit):
            _bootstrap._build_cli_command(REPO_ROOT, args, [])

    def test_missing_entry_point_exits(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            args = self._make_args("inspect")
            with self.assertRaises(SystemExit):
                _bootstrap._build_cli_command(Path(d), args, [])

    def test_remaining_args_forwarded(self) -> None:
        args = self._make_args("apply")
        remaining = ["--answers", "answers.json", "--non-interactive", "--json"]
        cmd = _bootstrap._build_cli_command(REPO_ROOT, args, remaining)
        self.assertIn("--answers", cmd)
        self.assertIn("answers.json", cmd)
        self.assertIn("--non-interactive", cmd)

    def test_workspace_is_resolved_to_absolute(self) -> None:
        args = self._make_args("inspect", workspace=".")
        cmd = _bootstrap._build_cli_command(REPO_ROOT, args, [])
        workspace_idx = cmd.index("--workspace")
        workspace_value = cmd[workspace_idx + 1]
        self.assertTrue(Path(workspace_value).is_absolute())


class DefaultConstantsTests(unittest.TestCase):
    def test_default_source_is_xanadassistant(self) -> None:
        self.assertEqual("github:asafelobotomy/xanadassistant", _bootstrap._DEFAULT_SOURCE)

    def test_default_cache_root_is_under_home(self) -> None:
        self.assertIn(".xanadAssistant", str(_bootstrap._DEFAULT_CACHE_ROOT))

    def test_supported_commands_includes_core_set(self) -> None:
        for cmd in ("inspect", "interview", "plan", "apply"):
            self.assertIn(cmd, _bootstrap._SUPPORTED_COMMANDS)


class DownloadArchiveTests(unittest.TestCase):
    """Tests for _download_archive error and security paths (no real network calls)."""

    def _make_tarball(self, members: list[tuple[str, bytes]]) -> bytes:
        """Build an in-memory .tar.gz with the given (name, data) members."""
        buf = io.BytesIO()
        with tarfile_module.open(fileobj=buf, mode="w:gz") as tar:
            for name, data in members:
                info = tarfile_module.TarInfo(name=name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    def test_download_failure_exits(self) -> None:
        with patch("urllib.request.urlopen", side_effect=OSError("network timeout")):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(SystemExit) as cm:
                    _bootstrap._download_archive("owner", "repo", "main", Path(d) / "cache")
                self.assertIn("Download failed", str(cm.exception))

    def test_path_traversal_member_is_skipped(self) -> None:
        members = [
            ("repo-main/safe.txt", b"safe content"),
            ("repo-main/../../etc/passwd", b"evil"),
        ]
        tarball_bytes = self._make_tarball(members)
        mock_response = MagicMock()
        mock_response.read.return_value = tarball_bytes
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with tempfile.TemporaryDirectory() as d:
            cache_root = Path(d) / "cache"
            with patch("urllib.request.urlopen", return_value=mock_response):
                cache_dir = _bootstrap._download_archive("owner", "repo", "main", cache_root)
            self.assertFalse((Path(d) / "etc" / "passwd").exists())
            self.assertTrue((cache_dir / "safe.txt").exists())
