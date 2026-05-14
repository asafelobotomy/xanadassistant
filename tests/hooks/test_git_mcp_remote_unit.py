"""Remote-ops tests for gitMcp.py — git_fetch, git_pull, git_push.

Uses two local bare/working repos so no actual network access is required.
"""
from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks" / "scripts"

_MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


def _load(name: str):
    """Load a hook module from HOOKS_DIR by filename stem."""
    path = HOOKS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(*args: str, cwd: str) -> str:
    """Run a git command and return combined stdout/stderr."""
    result = subprocess.run(
        ["git"] + list(args), cwd=cwd, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class GitMcpRemoteTests(unittest.TestCase):
    """Tests for git_fetch, git_pull, and git_push using local repos."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("gitMcp")
        cls._tmpdir = tempfile.TemporaryDirectory()
        root = Path(cls._tmpdir.name)

        # 1. Create a bare repo that acts as the remote.
        cls.bare = str(root / "bare.git")
        _git("init", "--bare", cls.bare, cwd=cls._tmpdir.name)

        # 2. Create the primary working repo; point origin at bare.
        cls.work = str(root / "work")
        _git("init", cls.work, cwd=cls._tmpdir.name)
        _git("config", "user.email", "test@test.com", cwd=cls.work)
        _git("config", "user.name", "Test", cwd=cls.work)
        _git("remote", "add", "origin", cls.bare, cwd=cls.work)
        (Path(cls.work) / "README.md").write_text("# Remote Tests\n")
        _git("add", "README.md", cwd=cls.work)
        _git("commit", "-m", "initial commit", cwd=cls.work)
        # Push to bare so origin/HEAD exists.
        branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cls.work)
        cls.branch = branch
        _git("push", "-u", "origin", branch, cwd=cls.work)

        # 3. Create a second working repo (contributor) — clone of bare.
        cls.contrib = str(root / "contrib")
        _git("clone", cls.bare, cls.contrib, cwd=cls._tmpdir.name)
        _git("config", "user.email", "contrib@test.com", cwd=cls.contrib)
        _git("config", "user.name", "Contrib", cwd=cls.contrib)

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    # --- git_fetch ---

    def test_git_fetch_returns_string(self):
        """git_fetch with an up-to-date remote returns a string (possibly empty)."""
        result = self.mod.git_fetch(self.work, "origin")
        self.assertIsInstance(result, str)

    def test_git_fetch_with_prune_flag(self):
        """git_fetch(prune=True) completes without error."""
        result = self.mod.git_fetch(self.work, "origin", prune=True)
        self.assertIsInstance(result, str)

    def test_git_fetch_sees_new_commits(self):
        """After contributor pushes a commit, fetch makes it visible locally."""
        # Contributor adds a file and pushes.
        (Path(self.contrib) / "contrib.txt").write_text("from contrib\n")
        _git("add", "contrib.txt", cwd=self.contrib)
        _git("commit", "-m", "contrib commit", cwd=self.contrib)
        _git("push", cwd=self.contrib)

        # Fetch in work repo.
        self.mod.git_fetch(self.work, "origin")

        # The new commit should now be reachable via origin/<branch>.
        log = _git("log", f"origin/{self.branch}", "--oneline", cwd=self.work)
        self.assertIn("contrib commit", log)

    # --- git_pull ---

    def test_git_pull_integrates_upstream(self):
        """git_pull brings the contributor commit into the local working tree."""
        result = self.mod.git_pull(self.work, "origin", self.branch)
        self.assertIsInstance(result, str)
        # The contrib file should now exist locally.
        self.assertTrue((Path(self.work) / "contrib.txt").exists())

    def test_git_pull_with_rebase(self):
        """git_pull with rebase=True completes without error when up-to-date."""
        result = self.mod.git_pull(self.work, "origin", self.branch, rebase=True)
        self.assertIsInstance(result, str)

    # --- git_push ---

    def test_git_push_sends_local_commit(self):
        """A local commit pushed to bare is visible in the contributor clone."""
        (Path(self.work) / "pushed.txt").write_text("pushed by work\n")
        _git("add", "pushed.txt", cwd=self.work)
        _git("commit", "-m", "work push commit", cwd=self.work)

        result = self.mod.git_push(self.work, "origin", self.branch)
        self.assertIsInstance(result, str)

        # Verify the bare repo has the commit.
        log = _git("log", "--oneline", cwd=self.bare)
        self.assertIn("work push commit", log)

    def test_git_push_with_tags(self):
        """git_push(tags=True) includes tags in the push."""
        _git("tag", "v-remote-test-0.1", cwd=self.work)
        result = self.mod.git_push(self.work, "origin", self.branch, tags=True)
        self.assertIsInstance(result, str)

        # Verify the tag is in the bare repo.
        tags = _git("tag", cwd=self.bare)
        self.assertIn("v-remote-test-0.1", tags)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
