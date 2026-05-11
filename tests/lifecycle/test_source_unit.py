"""Direct unit tests for scripts/lifecycle/_xanad/_source.py — non-network paths."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts.lifecycle._xanad._errors import LifecycleCommandError, _State
from scripts.lifecycle._xanad._source import (
    build_source_summary,
    get_cache_root,
    parse_github_source,
    resolve_effective_package_root,
    resolve_package_root,
    resolve_workspace,
)


class ResolveWorkspaceTests(unittest.TestCase):
    def test_returns_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = resolve_workspace(tmp)
            self.assertEqual(Path(tmp).resolve(), result)

    def test_creates_directory_when_create_is_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            new_dir = Path(tmp) / "new" / "workspace"
            self.assertFalse(new_dir.exists())
            result = resolve_workspace(str(new_dir), create=True)
            self.assertTrue(result.exists())


class ResolvePackageRootTests(unittest.TestCase):
    def test_returns_resolved_path_for_existing_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = resolve_package_root(tmp)
            self.assertEqual(Path(tmp).resolve(), result)

    def test_raises_for_nonexistent_path(self) -> None:
        with self.assertRaises(FileNotFoundError):
            resolve_package_root("/nonexistent/path/that/does/not/exist")


class ParseGithubSourceTests(unittest.TestCase):
    def test_parses_valid_source(self) -> None:
        owner, repo = parse_github_source("github:octocat/hello-world")
        self.assertEqual("octocat", owner)
        self.assertEqual("hello-world", repo)

    def test_raises_for_missing_github_scheme(self) -> None:
        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("https://github.com/owner/repo")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_raises_for_missing_slash(self) -> None:
        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:ownerrepo")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_raises_for_extra_slash_in_repo(self) -> None:
        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:owner/repo/extra")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_raises_for_invalid_characters_in_owner(self) -> None:
        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:owner@invalid/repo")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_raises_for_empty_owner(self) -> None:
        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:/repo")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_raises_for_empty_repo(self) -> None:
        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:owner/")
        self.assertEqual("source_resolution_failure", ctx.exception.code)


class GetCacheRootTests(unittest.TestCase):
    def setUp(self) -> None:
        import os
        self._orig_env = os.environ.copy()

    def tearDown(self) -> None:
        import os
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_returns_default_cache_root_when_env_not_set(self) -> None:
        import os
        os.environ.pop("XANAD_PKG_CACHE", None)
        result = get_cache_root()
        self.assertIn(".xanadAssistant", str(result))

    def test_honours_xanad_pkg_cache_env_var(self) -> None:
        import os
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["XANAD_PKG_CACHE"] = tmp
            result = get_cache_root()
            self.assertEqual(Path(tmp).resolve(), result)


class BuildSourceSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        _State.session_source_info = None

    def tearDown(self) -> None:
        _State.session_source_info = None

    def test_returns_package_root_kind_when_no_session_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = build_source_summary(Path(tmp))
            self.assertEqual("package-root", result["kind"])
            self.assertIn("packageRoot", result)

    def test_returns_session_source_info_when_set(self) -> None:
        _State.session_source_info = {"kind": "github-release", "source": "github:a/b"}
        with tempfile.TemporaryDirectory() as tmp:
            result = build_source_summary(Path(tmp))
            self.assertEqual("github-release", result["kind"])


class ResolveEffectivePackageRootTests(unittest.TestCase):
    def setUp(self) -> None:
        _State.session_source_info = None

    def tearDown(self) -> None:
        _State.session_source_info = None

    def test_resolves_local_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root, source_info = resolve_effective_package_root(tmp, None, None, None)
            self.assertEqual(Path(tmp).resolve(), pkg_root)
            self.assertEqual("package-root", source_info["kind"])

    @mock.patch("scripts.lifecycle._xanad._source.subprocess.run")
    def test_resolves_local_package_root_infers_github_source_and_ref(self, mock_run) -> None:
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=["git", "remote", "get-url", "origin"],
                returncode=0,
                stdout="https://github.com/asafelobotomy/xanadassistant.git\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
                returncode=0,
                stdout="main\n",
                stderr="",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            pkg_root, source_info = resolve_effective_package_root(tmp, None, None, None)

        self.assertEqual(Path(tmp).resolve(), pkg_root)
        self.assertEqual("package-root", source_info["kind"])
        self.assertEqual("github:asafelobotomy/xanadassistant", source_info["source"])
        self.assertEqual("main", source_info["ref"])

    def test_raises_when_no_package_root_and_no_source(self) -> None:
        with self.assertRaises(LifecycleCommandError) as ctx:
            resolve_effective_package_root(None, None, None, None)
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_raises_for_invalid_github_source_format(self) -> None:
        with self.assertRaises(LifecycleCommandError) as ctx:
            resolve_effective_package_root(None, "not-github:bad", None, None)
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_raises_for_nonexistent_local_package_root(self) -> None:
        with self.assertRaises(FileNotFoundError):
            resolve_effective_package_root("/nonexistent/path", None, None, None)
