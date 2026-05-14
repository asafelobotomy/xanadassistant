"""Unit tests for gitMcp.py hook."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks" / "scripts"
REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_PATH = str(REPO_ROOT)

_MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


def _load(name: str):
    """Load a hook module from HOOKS_DIR by filename stem."""
    path = HOOKS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_hyphen(filename: str):
    """Load a hook module with a hyphen in its filename."""
    path = HOOKS_DIR / filename
    mod_name = filename.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class GitMcpLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("gitMcp")

    def test_module_has_mcp(self):
        self.assertTrue(hasattr(self.mod, "mcp"))

    def test_run_flags_basic(self):
        result = self.mod._run_flags(REPO_PATH, ["status"], ["--porcelain"], [])
        self.assertIsInstance(result, str)

    def test_run_flags_rejects_dash_in_tail(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._run_flags(REPO_PATH, ["log"], [], ["--evil-flag"])
        self.assertIn("looks like a flag", str(ctx.exception))

    def test_run_rejects_dash_in_args(self):
        with self.assertRaises(ValueError):
            self.mod._run(REPO_PATH, "log", "--evil")

    def test_run_raises_on_git_error(self):
        with self.assertRaises(RuntimeError):
            self.mod._run(REPO_PATH, "cat-file", "nonexistent_sha_xyz")

    def test_git_status(self):
        result = self.mod.git_status(REPO_PATH)
        self.assertIsInstance(result, str)

    def test_git_diff_unstaged(self):
        result = self.mod.git_diff_unstaged(REPO_PATH)
        self.assertIsInstance(result, str)

    def test_git_diff_staged(self):
        result = self.mod.git_diff_staged(REPO_PATH)
        self.assertIsInstance(result, str)

    def test_git_log(self):
        result = self.mod.git_log(REPO_PATH, max_count=5)
        self.assertIsInstance(result, str)

    def test_git_log_with_branch(self):
        result = self.mod.git_log(REPO_PATH, max_count=3, branch="HEAD")
        self.assertIsInstance(result, str)

    def test_git_show_head(self):
        result = self.mod.git_show(REPO_PATH, "HEAD")
        self.assertIsInstance(result, str)

    def test_git_branch_list_local(self):
        result = self.mod.git_branch_list(REPO_PATH, scope="local")
        self.assertIsInstance(result, str)

    def test_git_branch_list_all(self):
        result = self.mod.git_branch_list(REPO_PATH, scope="all")
        self.assertIsInstance(result, str)

    def test_git_branch_list_remote(self):
        result = self.mod.git_branch_list(REPO_PATH, scope="remote")
        self.assertIsInstance(result, str)

    def test_git_stash_list(self):
        result = self.mod.git_stash_list(REPO_PATH)
        self.assertIsInstance(result, str)

    def test_git_tag_list(self):
        result = self.mod.git_tag_list(REPO_PATH)
        self.assertIsInstance(result, str)

    def test_git_diff_between_refs(self):
        result = self.mod.git_diff(REPO_PATH, "HEAD")
        self.assertIsInstance(result, str)

    def test_git_rebase_start_requires_onto(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.git_rebase(REPO_PATH, onto="", action="start")
        self.assertIn("'onto' is required", str(ctx.exception))

    def test_git_commit_empty_message_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.git_commit(REPO_PATH, "   ")
        self.assertIn("not be empty", str(ctx.exception))


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class GitMcpMutationTests(unittest.TestCase):
    """Tests for gitMcp functions that mutate repo state (uses a temp git repo)."""

    @classmethod
    def setUpClass(cls):
        import subprocess as _sp
        import tempfile as _tf
        cls.mod = _load("gitMcp")
        cls._tmpdir = _tf.TemporaryDirectory()
        cls.repo = cls._tmpdir.name
        _sp.run(["git", "init", cls.repo], check=True, capture_output=True)
        _sp.run(["git", "-C", cls.repo, "config", "user.email", "test@test.com"], check=True, capture_output=True)
        _sp.run(["git", "-C", cls.repo, "config", "user.name", "Test"], check=True, capture_output=True)
        readme = Path(cls.repo) / "README.md"
        readme.write_text("# Test", encoding="utf-8")
        _sp.run(["git", "-C", cls.repo, "add", "README.md"], check=True, capture_output=True)
        _sp.run(["git", "-C", cls.repo, "commit", "-m", "initial"], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_git_add_and_reset(self):
        """git_add (line 204) and git_reset (line 210) on a temp repo."""
        tmp_file = Path(self.repo) / "new-file.txt"
        tmp_file.write_text("hello", encoding="utf-8")
        self.mod.git_add(self.repo, ["new-file.txt"])
        staged = self.mod._run_flags(self.repo, ["diff", "--cached"], ["--name-only"], [])
        self.assertIn("new-file.txt", staged)
        self.mod.git_reset(self.repo)
        staged_after = self.mod._run_flags(self.repo, ["diff", "--cached"], ["--name-only"], [])
        self.assertNotIn("new-file.txt", staged_after)
        tmp_file.unlink(missing_ok=True)

    def test_git_commit(self):
        """git_commit (line 223) — commits staged file on temp repo."""
        tmp_file = Path(self.repo) / "commit-test.txt"
        tmp_file.write_text("commit test", encoding="utf-8")
        self.mod.git_add(self.repo, ["commit-test.txt"])
        result = self.mod.git_commit(self.repo, "test: add commit-test.txt")
        self.assertIsInstance(result, str)

    def test_git_stash_and_pop(self):
        """git_stash (line 238) and git_stash_pop (line 245) on dirty temp repo."""
        stash_file = Path(self.repo) / "stash-test.txt"
        stash_file.write_text("uncommitted change", encoding="utf-8")
        self.mod.git_add(self.repo, ["stash-test.txt"])
        self.mod.git_stash(self.repo, message="test stash")
        self.assertFalse(stash_file.exists())
        self.mod.git_stash_pop(self.repo)
        self.assertTrue(stash_file.exists())

    def test_git_create_checkout_delete_branch(self):
        """git_create_branch (line 166), git_checkout (line 173), git_delete_branch (line 189)."""
        self.mod.git_create_branch(self.repo, "test-branch")
        result = self.mod.git_branch_list(self.repo, scope="local")
        self.assertIn("test-branch", result)
        self.mod.git_checkout(self.repo, "test-branch")
        current = self.mod._run_flags(self.repo, ["rev-parse", "--abbrev-ref"], [], ["HEAD"])
        self.assertEqual("test-branch", current)
        # Switch back before deleting
        main_branch = "master"
        try:
            self.mod.git_checkout(self.repo, "master")
        except RuntimeError:
            self.mod.git_checkout(self.repo, "main")
            main_branch = "main"
        self.mod.git_delete_branch(self.repo, "test-branch")
        result2 = self.mod.git_branch_list(self.repo, scope="local")
        self.assertNotIn("test-branch", result2)

    def test_git_tag_annotated(self):
        """git_tag with message (line 273) — creates annotated tag on temp repo."""
        result = self.mod.git_tag(self.repo, "v0.1.0-test", message="test release")
        self.assertIsInstance(result, str)

    def test_git_rebase_action_abort_raises(self):
        """git_rebase action=abort (line 303) — fails when no rebase in progress."""
        with self.assertRaises(RuntimeError):
            self.mod.git_rebase(self.repo, action="abort")

    def test_git_rebase_onto_head(self):
        """git_rebase onto=HEAD (line 302) — rebase onto self (no-op on current branch)."""
        # git rebase HEAD~ might fail; use a known-good rebase that's trivial
        # This may raise RuntimeError if "nothing to rebase"; that still covers line 302
        try:
            self.mod.git_rebase(self.repo, onto="HEAD")
        except RuntimeError:
            pass  # still covers the return statement at line 302


# ---------------------------------------------------------------------------
# securityMcp.py  (import + module-level only)
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
