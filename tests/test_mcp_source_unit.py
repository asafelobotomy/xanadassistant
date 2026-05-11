"""Direct unit tests for hooks/scripts/_xanad_mcp_source.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

# The hook scripts are not on the standard module path; add the hooks dir temporarily.
_HOOKS_DIR = Path(__file__).resolve().parents[1] / "hooks" / "scripts"


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
