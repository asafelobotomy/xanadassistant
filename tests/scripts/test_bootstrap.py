from __future__ import annotations

import importlib.util
import tempfile
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_bootstrap():
    spec = importlib.util.spec_from_file_location("xanadBootstrap", _REPO_ROOT / "xanadBootstrap.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load xanadBootstrap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_bootstrap = _load_bootstrap()


class CacheKeyTests(unittest.TestCase):
    def test_cache_key_avoids_collision_between_slash_and_hyphen_ref(self) -> None:
        key_slash = _bootstrap._cache_key("feature/x")
        key_hyphen = _bootstrap._cache_key("feature-x")
        self.assertNotEqual(key_slash, key_hyphen)

    def test_cache_key_produces_readable_slug_prefix(self) -> None:
        key = _bootstrap._cache_key("feature/my-branch")
        # Slug must not start with a digest-only string; human-readable prefix expected
        self.assertTrue(key.startswith("feature-my-branch-"))

    def test_cache_key_appends_twelve_char_hex_digest(self) -> None:
        key = _bootstrap._cache_key("main")
        parts = key.rsplit("-", 1)
        self.assertEqual(len(parts), 2)
        digest = parts[1]
        self.assertEqual(len(digest), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in digest))

    def test_cache_key_is_deterministic(self) -> None:
        self.assertEqual(_bootstrap._cache_key("v1.0.0"), _bootstrap._cache_key("v1.0.0"))

    def test_cache_key_sanitises_special_characters(self) -> None:
        key = _bootstrap._cache_key("refs/heads/feat@2024")
        # No raw slashes or @ characters in the key
        self.assertNotIn("/", key)
        self.assertNotIn("@", key)


class BootstrapCommandTests(unittest.TestCase):
    def test_build_cli_command_accepts_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            entry = package_root / "xanadAssistant.py"
            entry.write_text("# stub\n", encoding="utf-8")
            args = type("Args", (), {"command": "setup", "mode": None, "workspace": tmpdir})()

            command = _bootstrap._build_cli_command(package_root, args, ["--plan", "plan.json"])

        self.assertEqual(command[:3], [sys.executable, str(entry), "setup"])
        self.assertIn("--plan", command)
        self.assertIn("plan.json", command)

    def test_main_accepts_setup_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()

            with mock.patch(
                "sys.argv",
                [
                    "xanadBootstrap.py",
                    "setup",
                    "--workspace",
                    tmpdir,
                    "--plan",
                    "plan.json",
                ],
            ), mock.patch.object(_bootstrap, "_resolve_package_root", return_value=package_root), mock.patch.object(
                _bootstrap,
                "_build_cli_command",
                return_value=["python3", "xanadAssistant.py", "setup", "--plan", "plan.json"],
            ) as build_command, mock.patch.object(
                _bootstrap.subprocess,
                "run",
                return_value=mock.Mock(returncode=0),
            ), self.assertRaises(SystemExit) as excinfo:
                _bootstrap.main()

        self.assertEqual(excinfo.exception.code, 0)
        self.assertEqual(build_command.call_args.args[0], package_root)
        self.assertEqual(build_command.call_args.args[1].command, "setup")

    def test_main_rejects_retired_apply_command_at_parse_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "sys.argv",
            [
                "xanadBootstrap.py",
                "apply",
                "--workspace",
                tmpdir,
            ],
        ), self.assertRaises(SystemExit) as excinfo:
            _bootstrap.main()

        self.assertEqual(excinfo.exception.code, 2)


class DownloadArchiveTests(unittest.TestCase):
    def test_sentinel_prevents_redownload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)
            cache_dir = cache_root / "github" / "owner-repo" / f"ref-{_bootstrap._cache_key('main')}"
            cache_dir.mkdir(parents=True)
            (cache_dir / ".complete").write_text("ok\n", encoding="utf-8")
            result = _bootstrap._download_archive("owner", "repo", "main", cache_root)
            self.assertEqual(result, cache_dir)

    def test_download_failure_exits_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)
            with mock.patch(
                "urllib.request.urlopen",
                side_effect=OSError("connection refused"),
            ), self.assertRaises(SystemExit) as excinfo:
                _bootstrap._download_archive("owner", "repo", "main", cache_root)
            self.assertNotEqual(excinfo.exception.code, 0)

    def test_tar_extraction_skips_dotdot_members(self) -> None:
        import io
        import tarfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)
            key = _bootstrap._cache_key("v1.0.0")
            cache_dir = cache_root / "github" / "owner-repo" / f"ref-{key}"
            cache_dir.mkdir(parents=True)
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w:gz") as tar:
                info = tarfile.TarInfo(name="repo-1.0.0/../../../etc/evil.txt")
                info.size = 4
                tar.addfile(info, io.BytesIO(b"evil"))
                info2 = tarfile.TarInfo(name="repo-1.0.0/safe.txt")
                info2.size = 4
                info2.type = tarfile.REGTYPE
                tar.addfile(info2, io.BytesIO(b"safe"))
            buf.seek(0)
            tmp_file = cache_dir / "archive.tar.gz"
            tmp_file.write_bytes(buf.read())
            with mock.patch("urllib.request.urlopen") as mock_open:
                mock_resp = mock.MagicMock()
                mock_resp.read.return_value = tmp_file.read_bytes()
                mock_open.return_value.__enter__ = lambda s: mock_resp
                mock_open.return_value.__exit__ = mock.Mock(return_value=False)
                _bootstrap._download_archive("owner", "repo", "v1.0.0", cache_root)
            evil_path = cache_dir / ".." / ".." / ".." / "etc" / "evil.txt"
            self.assertFalse(evil_path.exists())

    def test_validate_source_rejects_invalid_formats(self) -> None:
        for bad in ("notgithub:owner/repo", "github:owner", "github:", "github:owner/repo/extra"):
            with self.assertRaises(SystemExit):
                _bootstrap._validate_source(bad)

    def test_validate_source_accepts_valid_format(self) -> None:
        owner, repo = _bootstrap._validate_source("github:myorg/myrepo")
        self.assertEqual(owner, "myorg")
        self.assertEqual(repo, "myrepo")

    def test_mutable_ref_without_checksum_emits_warning(self) -> None:
        """Downloading from a branch without --expected-sha256 must print a warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)
            import io
            import tarfile as _tarfile
            buf = io.BytesIO()
            with _tarfile.open(fileobj=buf, mode="w:gz") as tar:
                info = _tarfile.TarInfo(name="repo-main/placeholder.txt")
                info.size = 2
                info.type = _tarfile.REGTYPE
                tar.addfile(info, io.BytesIO(b"ok"))
            buf.seek(0)
            archive_bytes = buf.read()
            with mock.patch("urllib.request.urlopen") as mock_open, \
                    mock.patch("sys.stderr") as mock_stderr:
                mock_resp = mock.MagicMock()
                mock_resp.read.return_value = archive_bytes
                mock_open.return_value.__enter__ = lambda s: mock_resp
                mock_open.return_value.__exit__ = mock.Mock(return_value=False)
                _bootstrap._download_archive("owner", "repo", "main", cache_root)
            # Warning about mutable ref must have been printed.
            written = "".join(str(c) for c in mock_stderr.write.call_args_list)
            self.assertIn("mutable", written.lower())

    def test_correct_sha256_passes_verification(self) -> None:
        """When --expected-sha256 matches the download, extraction proceeds normally."""
        import hashlib as _hashlib
        import io
        import tarfile as _tarfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)
            buf = io.BytesIO()
            with _tarfile.open(fileobj=buf, mode="w:gz") as tar:
                info = _tarfile.TarInfo(name="repo-v1.0.0/file.txt")
                info.size = 2
                info.type = _tarfile.REGTYPE
                tar.addfile(info, io.BytesIO(b"ok"))
            buf.seek(0)
            archive_bytes = buf.read()
            sha = _hashlib.sha256(archive_bytes).hexdigest()
            with mock.patch("urllib.request.urlopen") as mock_open:
                mock_resp = mock.MagicMock()
                mock_resp.read.return_value = archive_bytes
                mock_open.return_value.__enter__ = lambda s: mock_resp
                mock_open.return_value.__exit__ = mock.Mock(return_value=False)
                # Must not raise — checksum matches.
                _bootstrap._download_archive("owner", "repo", "v1.0.0", cache_root,
                                             expected_sha256=sha)

    def test_wrong_sha256_aborts_with_exit(self) -> None:
        """When --expected-sha256 does not match the download, sys.exit must be called."""
        import io
        import tarfile as _tarfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)
            buf = io.BytesIO()
            with _tarfile.open(fileobj=buf, mode="w:gz") as tar:
                info = _tarfile.TarInfo(name="repo-v1.0.0/file.txt")
                info.size = 2
                info.type = _tarfile.REGTYPE
                tar.addfile(info, io.BytesIO(b"ok"))
            buf.seek(0)
            archive_bytes = buf.read()
            with mock.patch("urllib.request.urlopen") as mock_open, \
                    self.assertRaises(SystemExit) as excinfo:
                mock_resp = mock.MagicMock()
                mock_resp.read.return_value = archive_bytes
                mock_open.return_value.__enter__ = lambda s: mock_resp
                mock_open.return_value.__exit__ = mock.Mock(return_value=False)
                _bootstrap._download_archive("owner", "repo", "v1.0.0", cache_root,
                                             expected_sha256="0" * 64)
            self.assertIn("checksum mismatch", str(excinfo.exception.code).lower())


if __name__ == "__main__":
    unittest.main()
