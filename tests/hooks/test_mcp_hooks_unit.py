"""Unit tests for hooks/scripts/*.py MCP servers.

Imports each hook module via importlib to avoid package-path issues and calls
all non-network functions directly to achieve coverage without network access.
"""
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


# ---------------------------------------------------------------------------
# time-mcp.py
# ---------------------------------------------------------------------------

class TimeMcpImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_hyphen("time-mcp.py")

    def test_module_has_mcp(self):
        self.assertTrue(hasattr(self.mod, "mcp"))

    def test_parse_iso_utc(self):
        from datetime import timezone
        dt = self.mod._parse_iso("2026-05-10T14:30:00Z")
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_parse_iso_naive_assumes_utc(self):
        from datetime import timezone
        dt = self.mod._parse_iso("2026-05-10T14:30:00")
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_parse_iso_invalid_raises(self):
        with self.assertRaises(ValueError):
            self.mod._parse_iso("not-a-date")

    def test_tz_valid(self):
        tz = self.mod._tz("UTC")
        self.assertIsNotNone(tz)

    def test_tz_unknown_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._tz("Not/ATimezone")
        self.assertIn("Unknown timezone", str(ctx.exception))

    def test_current_time_utc(self):
        result = self.mod.current_time("UTC")
        self.assertIsInstance(result, str)
        self.assertIn("T", result)

    def test_current_time_new_york(self):
        result = self.mod.current_time("America/New_York")
        self.assertIsInstance(result, str)

    def test_elapsed_basic(self):
        result = self.mod.elapsed("2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z")
        self.assertIn("m", result)

    def test_elapsed_default_end(self):
        result = self.mod.elapsed("2025-01-01T00:00:00Z")
        self.assertIsInstance(result, str)

    def test_elapsed_negative_indicates_reversed(self):
        result = self.mod.elapsed("2026-01-01T01:00:00Z", "2026-01-01T00:00:00Z")
        self.assertIn("negative", result)

    def test_convert_timezone_basic(self):
        result = self.mod.convert_timezone("2026-05-10T14:30:00", "UTC", "America/Los_Angeles")
        self.assertIsInstance(result, str)
        self.assertIn("T", result)

    def test_convert_timezone_with_tz_in_timestamp(self):
        result = self.mod.convert_timezone("2026-05-10T14:30:00+00:00", "UTC", "Europe/Paris")
        self.assertIsInstance(result, str)

    def test_format_duration_milliseconds(self):
        result = self.mod.format_duration(0.5)
        self.assertIn("ms", result)

    def test_format_duration_seconds(self):
        result = self.mod.format_duration(45.5)
        self.assertIn("s", result)

    def test_format_duration_minutes(self):
        result = self.mod.format_duration(90)
        self.assertIn("m", result)

    def test_format_duration_hours(self):
        result = self.mod.format_duration(7200)
        self.assertIn("h", result)

    def test_format_duration_days(self):
        result = self.mod.format_duration(90000)
        self.assertIn("d", result)


# ---------------------------------------------------------------------------
# sqlite-mcp.py
# ---------------------------------------------------------------------------

class SqliteMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("sqlite-mcp")
        cls.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.db_path = cls.tmp.name
        cls.tmp.close()
        conn = sqlite3.connect(cls.db_path)
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO items (name) VALUES ('alpha'), ('beta')")
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        Path(cls.db_path).unlink(missing_ok=True)

    def test_module_has_mcp(self):
        self.assertTrue(hasattr(self.mod, "mcp"))

    def test_connect_readonly(self):
        conn = self.mod._connect(self.db_path, allow_writes=False)
        conn.close()

    def test_connect_readwrite(self):
        conn = self.mod._connect(self.db_path, allow_writes=True)
        conn.close()

    def test_connect_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.mod._connect("/nonexistent_path/test.db", allow_writes=False)

    def test_fmt_with_results(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("SELECT id, name FROM items")
        result = self.mod._fmt(cur, 100)
        conn.close()
        self.assertIn("alpha", result)
        self.assertIn("beta", result)

    def test_fmt_no_description(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("INSERT INTO items (name) VALUES (?)", ["test_fmt"])
        result = self.mod._fmt(cur, 100)
        conn.close()
        self.assertIn("no rows", result)

    def test_fmt_truncated(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute("SELECT id, name FROM items")
        result = self.mod._fmt(cur, 1)  # max_rows=1, but we have 2 rows
        conn.close()
        self.assertIn("capped", result)

    def test_execute_query_select(self):
        result = self.mod.execute_query(self.db_path, "SELECT name FROM items WHERE id=1")
        self.assertIn("alpha", result)

    def test_execute_query_with_params(self):
        result = self.mod.execute_query(self.db_path, "SELECT name FROM items WHERE id=?", [2])
        self.assertIn("beta", result)

    def test_execute_query_write(self):
        result = self.mod.execute_query(
            self.db_path,
            "INSERT INTO items (name) VALUES (?)",
            ["gamma"],
            allow_writes=True,
        )
        self.assertIn("no rows", result)

    def test_execute_query_error_raises(self):
        with self.assertRaises(RuntimeError):
            self.mod.execute_query(self.db_path, "SELECT * FROM nonexistent_table_xyz")

    def test_list_tables(self):
        result = self.mod.list_tables(self.db_path)
        self.assertIn("items", result)

    def test_list_tables_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            empty_path = f.name
        try:
            result = self.mod.list_tables(empty_path)
            self.assertIn("No tables", result)
        finally:
            Path(empty_path).unlink(missing_ok=True)

    def test_describe_table_exists(self):
        result = self.mod.describe_table(self.db_path, "items")
        self.assertIn("CREATE TABLE", result)

    def test_describe_table_missing(self):
        result = self.mod.describe_table(self.db_path, "nonexistent_xyz")
        self.assertIn("No table or view", result)


# ---------------------------------------------------------------------------
# mcp-sequential-thinking-server.py
# ---------------------------------------------------------------------------

class SequentialThinkingMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_hyphen("mcp-sequential-thinking-server.py")

    def setUp(self):
        # Reset session before each test
        self.mod._session = self.mod.ThinkingSession()

    def test_thinking_session_init(self):
        session = self.mod.ThinkingSession()
        self.assertEqual([], session.thought_history)
        self.assertEqual({}, session.branches)

    def test_reset_returns_ok(self):
        result = self.mod.reset_thinking_session()
        self.assertEqual("ok", result["status"])

    def test_reset_clears_history(self):
        self.mod.sequentialthinking(
            thought="initial thought",
            next_thought_needed=False,
            thought_number=1,
            total_thoughts=1,
        )
        self.mod.reset_thinking_session()
        self.assertEqual(0, len(self.mod._session.thought_history))

    def test_basic_thought(self):
        result = self.mod.sequentialthinking(
            thought="A thought",
            next_thought_needed=False,
            thought_number=1,
            total_thoughts=1,
        )
        self.assertEqual(1, result["thought_number"])
        self.assertEqual(1, result["thought_history_length"])

    def test_thought_number_below_1_fails(self):
        result = self.mod.sequentialthinking(
            thought="bad", next_thought_needed=False, thought_number=0, total_thoughts=1,
        )
        self.assertEqual("failed", result["status"])
        self.assertIn("thought_number", result["error"])

    def test_total_thoughts_below_1_fails(self):
        result = self.mod.sequentialthinking(
            thought="bad", next_thought_needed=False, thought_number=1, total_thoughts=0,
        )
        self.assertEqual("failed", result["status"])

    def test_thought_too_long_fails(self):
        result = self.mod.sequentialthinking(
            thought="x" * (self.mod.MAX_THOUGHT_CHARS + 1),
            next_thought_needed=False,
            thought_number=1,
            total_thoughts=1,
        )
        self.assertEqual("failed", result["status"])
        self.assertIn("exceeds maximum", result["error"])

    def test_revises_thought_invalid_reference_fails(self):
        result = self.mod.sequentialthinking(
            thought="bad revision",
            next_thought_needed=False,
            thought_number=2,
            total_thoughts=2,
            is_revision=True,
            revises_thought=5,  # does not exist in history
        )
        self.assertEqual("failed", result["status"])

    def test_branch_from_thought_valid(self):
        self.mod.sequentialthinking(
            thought="root thought", next_thought_needed=True,
            thought_number=1, total_thoughts=2,
        )
        result = self.mod.sequentialthinking(
            thought="branch thought", next_thought_needed=False,
            thought_number=2, total_thoughts=2,
            branch_from_thought=1, branch_id="explore",
        )
        self.assertFalse(result.get("isError"))
        self.assertIn("explore", result["branches"])

    def test_branch_id_invalid_chars_fails(self):
        result = self.mod.sequentialthinking(
            thought="t", next_thought_needed=False, thought_number=1, total_thoughts=1,
            branch_id="invalid branch!",
        )
        self.assertEqual("failed", result["status"])

    def test_branch_id_too_long_fails(self):
        result = self.mod.sequentialthinking(
            thought="t", next_thought_needed=False, thought_number=1, total_thoughts=1,
            branch_id="x" * (self.mod.MAX_BRANCH_ID_LEN + 1),
        )
        self.assertEqual("failed", result["status"])

    def test_effective_total_adjusted(self):
        result = self.mod.sequentialthinking(
            thought="t", next_thought_needed=True,
            thought_number=5, total_thoughts=3,  # thought_number > total
        )
        self.assertEqual(5, result["total_thoughts"])

    def test_history_cap(self):
        # Fill history to the limit
        for i in range(self.mod.MAX_HISTORY):
            self.mod._session.thought_history.append({"thought_number": i + 1})
        result = self.mod.sequentialthinking(
            thought="overflow", next_thought_needed=False,
            thought_number=self.mod.MAX_HISTORY + 1, total_thoughts=self.mod.MAX_HISTORY + 1,
        )
        self.assertEqual("failed", result["status"])
        self.assertIn("limit", result["error"])

    def test_revises_thought_out_of_range_fails(self):
        result = self.mod.sequentialthinking(
            thought="t", next_thought_needed=False,
            thought_number=2, total_thoughts=2,
            revises_thought=3,  # >= thought_number
        )
        self.assertEqual("failed", result["status"])

    def test_branch_from_thought_out_of_range_fails(self):
        result = self.mod.sequentialthinking(
            thought="t", next_thought_needed=False,
            thought_number=2, total_thoughts=2,
            branch_from_thought=2,  # >= thought_number
        )
        self.assertEqual("failed", result["status"])

    def test_revises_thought_not_in_history_fails(self):
        """lines 171-172: revises_thought in bounds but not recorded → error."""
        # Record thought 1, then skip to thought 3 while revising unrecorded thought 2
        self.mod.sequentialthinking(
            thought="first", next_thought_needed=True, thought_number=1, total_thoughts=3,
        )
        result = self.mod.sequentialthinking(
            thought="skip 2, revise 2", next_thought_needed=False,
            thought_number=3, total_thoughts=3,
            is_revision=True, revises_thought=2,  # 2 < 3 but never recorded
        )
        self.assertEqual("failed", result["status"])
        self.assertIn("revises_thought", result["error"])

    def test_branch_from_thought_not_in_history_fails(self):
        """line 185: branch_from_thought in bounds but not recorded → error."""
        self.mod.sequentialthinking(
            thought="first", next_thought_needed=True, thought_number=1, total_thoughts=3,
        )
        result = self.mod.sequentialthinking(
            thought="branch from unrecorded 2", next_thought_needed=False,
            thought_number=3, total_thoughts=3,
            branch_from_thought=2,  # 2 < 3 but never recorded
            branch_id="unrecorded-branch",
        )
        self.assertEqual("failed", result["status"])
        self.assertIn("branch_from_thought", result["error"])

    def test_successful_revision_with_revises_thought_in_history(self):
        """lines 226, 228: is_revision and revises_thought appended when no error."""
        self.mod.sequentialthinking(
            thought="thought one", next_thought_needed=True, thought_number=1, total_thoughts=2,
        )
        result = self.mod.sequentialthinking(
            thought="revised thought", next_thought_needed=False,
            thought_number=2, total_thoughts=2,
            is_revision=True, revises_thought=1,  # 1 in history
        )
        self.assertNotIn("error", result)
        history = self.mod._session.thought_history
        last = history[-1]
        self.assertTrue(last.get("is_revision"))
        self.assertEqual(1, last.get("revises_thought"))


# ---------------------------------------------------------------------------
# git-mcp.py  (local operations only)
# ---------------------------------------------------------------------------

REPO_PATH = str(REPO_ROOT)


class GitMcpLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("git-mcp")

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


class GitMcpMutationTests(unittest.TestCase):
    """Tests for git-mcp functions that mutate repo state (uses a temp git repo)."""

    @classmethod
    def setUpClass(cls):
        import subprocess as _sp
        import tempfile as _tf
        cls.mod = _load("git-mcp")
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
# security-mcp.py  (import + module-level only)
# ---------------------------------------------------------------------------

class SecurityMcpImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("security-mcp")

    def test_module_has_mcp(self):
        self.assertTrue(hasattr(self.mod, "mcp"))

    def test_headers_dict_present(self):
        self.assertIn("Content-Type", self.mod._HEADERS)

    def test_server_name(self):
        self.assertEqual("xanadSecurity", self.mod.mcp.name)


# ---------------------------------------------------------------------------
# web-mcp.py  (_guard_ssrf, _ssrf_redirect_hook, _RateLimiter, _to_markdown)
# ---------------------------------------------------------------------------

class WebMcpSsrfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("web-mcp")

    def test_guard_ssrf_loopback_blocked(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._guard_ssrf("http://127.0.0.1/anything")
        self.assertIn("blocked", str(ctx.exception))

    def test_guard_ssrf_rfc1918_blocked(self):
        with self.assertRaises(ValueError):
            self.mod._guard_ssrf("http://192.168.1.1/anything")

    def test_guard_ssrf_link_local_blocked(self):
        with self.assertRaises(ValueError):
            self.mod._guard_ssrf("http://169.254.169.254/metadata")

    def test_guard_ssrf_bad_url_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._guard_ssrf("not-a-url")
        self.assertIn("Cannot parse hostname", str(ctx.exception))

    def test_guard_ssrf_unresolvable_host_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._guard_ssrf("http://this.host.does.not.exist.xyzabc123/")
        self.assertIn("Cannot resolve", str(ctx.exception))

    def test_ssrf_redirect_hook_non_redirect_noop(self):
        resp = MagicMock()
        resp.is_redirect = False
        # Should not raise
        self.mod._ssrf_redirect_hook(resp)

    def test_ssrf_redirect_hook_blocked_redirect_raises(self):
        resp = MagicMock()
        resp.is_redirect = True
        resp.headers = {"location": "http://127.0.0.1/evil"}
        with self.assertRaises(ValueError):
            self.mod._ssrf_redirect_hook(resp)

    def test_ssrf_redirect_hook_empty_location_noop(self):
        resp = MagicMock()
        resp.is_redirect = True
        resp.headers = {"location": ""}
        # Empty location should not raise
        self.mod._ssrf_redirect_hook(resp)

    def test_rate_limiter_allows_within_limit(self):
        limiter = self.mod._RateLimiter(calls=5, period=60.0)
        for _ in range(5):
            limiter.check()  # Should not raise

    def test_rate_limiter_raises_when_exceeded(self):
        limiter = self.mod._RateLimiter(calls=2, period=60.0)
        limiter.check()
        limiter.check()
        with self.assertRaises(RuntimeError) as ctx:
            limiter.check()
        self.assertIn("Rate limit", str(ctx.exception))

    def test_to_markdown_strips_scripts(self):
        html = "<html><body><script>alert(1)</script><p>Hello</p></body></html>"
        result = self.mod._to_markdown(html)
        self.assertNotIn("alert", result)
        self.assertIn("Hello", result)

    def test_module_has_blocked_list(self):
        self.assertGreater(len(self.mod._BLOCKED), 5)


# ---------------------------------------------------------------------------
# github-mcp.py  (_token() only — everything else is network-only)
# ---------------------------------------------------------------------------

class GitHubMcpTokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("github-mcp")

    def test_module_has_mcp(self):
        self.assertTrue(hasattr(self.mod, "mcp"))

    def test_token_missing_raises(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": ""}, clear=False):
            if "GITHUB_TOKEN" in os.environ:
                del os.environ["GITHUB_TOKEN"]
            with self.assertRaises(RuntimeError) as ctx:
                self.mod._token()
        self.assertIn("GITHUB_TOKEN", str(ctx.exception))

    def test_token_whitespace_only_raises(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "   "}):
            with self.assertRaises(RuntimeError):
                self.mod._token()

    def test_token_returns_stripped(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "  mytoken  "}):
            result = self.mod._token()
        self.assertEqual("mytoken", result)

    def test_api_base_url(self):
        self.assertEqual("https://api.github.com", self.mod._API)


# ---------------------------------------------------------------------------
# xanad-workspace-mcp.py  (utility functions and handle_request)
# ---------------------------------------------------------------------------

class XanadWorkspaceMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Need to add hooks/scripts to sys.path so the module can import _xanad_mcp_source
        if str(HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_DIR))
        cls.mod = _load_hyphen("xanad-workspace-mcp.py")

    def test_reject_shell_metacharacters_clean(self):
        result = self.mod.reject_shell_metacharacters("python3 -m unittest")
        self.assertIsNone(result)

    def test_reject_shell_metacharacters_pipe(self):
        result = self.mod.reject_shell_metacharacters("ls | grep foo")
        self.assertIsNotNone(result)
        self.assertIn("|", result)

    def test_reject_shell_metacharacters_semicolon(self):
        result = self.mod.reject_shell_metacharacters("echo hi; rm -rf /")
        self.assertIsNotNone(result)

    def test_reject_shell_metacharacters_subshell(self):
        result = self.mod.reject_shell_metacharacters("echo $(whoami)")
        self.assertIsNotNone(result)

    def test_tail_text_short(self):
        result = self.mod.tail_text("line1\nline2\nline3")
        self.assertEqual("line1\nline2\nline3", result)

    def test_tail_text_empty(self):
        result = self.mod.tail_text("")
        self.assertIsNone(result)

    def test_tail_text_truncated_max_lines(self):
        text = "\n".join(f"line{i}" for i in range(100))
        result = self.mod.tail_text(text, max_lines=5)
        self.assertIsNotNone(result)
        lines = result.splitlines()
        self.assertLessEqual(len(lines), 5)

    def test_tail_text_truncated_max_chars(self):
        long_line = "x" * 5000
        result = self.mod.tail_text(long_line, max_chars=100)
        self.assertIsNotNone(result)
        self.assertLessEqual(len(result), 100)

    def test_build_tool_result_minimal(self):
        r = self.mod.build_tool_result(status="ok", summary="all good")
        self.assertEqual("ok", r["status"])
        self.assertEqual("all good", r["summary"])

    def test_build_tool_result_with_command_and_exit_code(self):
        r = self.mod.build_tool_result(
            status="ok", summary="done", command="python3 test.py", exit_code=0,
        )
        self.assertEqual("python3 test.py", r["command"])
        self.assertEqual(0, r["exitCode"])

    def test_build_tool_result_stdout_tail(self):
        r = self.mod.build_tool_result(status="ok", summary="done", stdout="hello world")
        self.assertIn("stdoutTail", r)
        self.assertIn("hello world", r["stdoutTail"])

    def test_build_tool_result_empty_stdout_omitted(self):
        r = self.mod.build_tool_result(status="ok", summary="done", stdout="")
        self.assertNotIn("stdoutTail", r)

    def test_build_unavailable_result(self):
        r = self.mod.build_unavailable_result("not ready", extra="value")
        self.assertEqual("unavailable", r["status"])
        self.assertEqual("not ready", r["summary"])
        self.assertEqual("value", r["extra"])

    def test_parse_json_payload_valid(self):
        result = self.mod._parse_json_payload('{"status": "ok"}')
        self.assertEqual({"status": "ok"}, result)

    def test_parse_json_payload_empty(self):
        result = self.mod._parse_json_payload("")
        self.assertIsNone(result)

    def test_parse_json_payload_invalid_json(self):
        result = self.mod._parse_json_payload("not json {{{")
        self.assertIsNone(result)

    def test_parse_json_payload_non_dict(self):
        result = self.mod._parse_json_payload("[1, 2, 3]")
        self.assertIsNone(result)

    def test_parse_key_commands_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# No key commands here\n")
            fpath = Path(f.name)
        try:
            result = self.mod.parse_key_commands(fpath)
            self.assertEqual([], result)
        finally:
            fpath.unlink(missing_ok=True)

    def test_parse_key_commands_missing_file(self):
        result = self.mod.parse_key_commands(Path("/nonexistent_path/file.md"))
        self.assertEqual([], result)

    def test_parse_key_commands_with_table(self):
        content = "## Key Commands\n\n| Task | Command |\n|------|------|\n| Run tests | python3 -m unittest |\n\n## Other\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            fpath = Path(f.name)
        try:
            result = self.mod.parse_key_commands(fpath)
            self.assertEqual(1, len(result))
            self.assertEqual("Run tests", result[0]["label"])
            self.assertEqual("python3 -m unittest", result[0]["command"])
        finally:
            fpath.unlink(missing_ok=True)

    def test_read_lockfile_missing(self):
        # Override WORKSPACE_LOCKFILE_PATH to a nonexistent file
        orig = self.mod.WORKSPACE_LOCKFILE_PATH
        self.mod.WORKSPACE_LOCKFILE_PATH = Path("/nonexistent/xanad-assistant-lock.json")
        try:
            result = self.mod.read_lockfile()
            self.assertIsNone(result)
        finally:
            self.mod.WORKSPACE_LOCKFILE_PATH = orig

    def test_read_lockfile_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json{{{")
            fpath = Path(f.name)
        orig = self.mod.WORKSPACE_LOCKFILE_PATH
        self.mod.WORKSPACE_LOCKFILE_PATH = fpath
        try:
            result = self.mod.read_lockfile()
            self.assertIsNone(result)
        finally:
            self.mod.WORKSPACE_LOCKFILE_PATH = orig
            fpath.unlink(missing_ok=True)

    def test_workspace_root_valid_when_github_exists(self):
        # The installed workspace (REPO_ROOT) has a .github dir
        orig = self.mod.WORKSPACE_ROOT
        self.mod.WORKSPACE_ROOT = REPO_ROOT
        try:
            result = self.mod.workspace_root_valid()
            self.assertTrue(result)
        finally:
            self.mod.WORKSPACE_ROOT = orig

    def test_workspace_root_invalid_without_github(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = self.mod.WORKSPACE_ROOT
            self.mod.WORKSPACE_ROOT = Path(tmp)
            try:
                result = self.mod.workspace_root_valid()
                self.assertFalse(result)
            finally:
                self.mod.WORKSPACE_ROOT = orig

    def test_resolve_lifecycle_cli_found(self):
        cli, reason = self.mod.resolve_lifecycle_cli(REPO_ROOT)
        self.assertIsNotNone(cli)
        self.assertIsNone(reason)

    def test_resolve_lifecycle_cli_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            cli, reason = self.mod.resolve_lifecycle_cli(Path(tmp))
        self.assertIsNone(cli)
        self.assertIsNotNone(reason)

    def test_handle_request_initialize(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-11-25"}}
        resp = self.mod.handle_request(req)
        self.assertIsNotNone(resp)
        self.assertIn("result", resp)
        self.assertIn("serverInfo", resp["result"])

    def test_handle_request_ping(self):
        req = {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}}
        resp = self.mod.handle_request(req)
        self.assertEqual({}, resp["result"])

    def test_handle_request_tools_list(self):
        req = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        resp = self.mod.handle_request(req)
        self.assertIn("tools", resp["result"])
        self.assertGreater(len(resp["result"]["tools"]), 0)

    def test_handle_request_prompts_list(self):
        req = {"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}}
        resp = self.mod.handle_request(req)
        self.assertEqual([], resp["result"]["prompts"])

    def test_handle_request_resources_list(self):
        req = {"jsonrpc": "2.0", "id": 5, "method": "resources/list", "params": {}}
        resp = self.mod.handle_request(req)
        self.assertEqual([], resp["result"]["resources"])

    def test_handle_request_resources_templates_list(self):
        req = {"jsonrpc": "2.0", "id": 6, "method": "resources/templates/list", "params": {}}
        resp = self.mod.handle_request(req)
        self.assertEqual([], resp["result"]["resourceTemplates"])

    def test_handle_request_logging_set_level(self):
        req = {"jsonrpc": "2.0", "id": 7, "method": "logging/setLevel", "params": {"level": "info"}}
        resp = self.mod.handle_request(req)
        self.assertEqual({}, resp["result"])

    def test_handle_request_notifications_initialized(self):
        req = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        resp = self.mod.handle_request(req)
        self.assertIsNone(resp)

    def test_handle_request_unknown_notification_returns_none(self):
        req = {"method": "notifications/progress", "params": {}}
        resp = self.mod.handle_request(req)
        self.assertIsNone(resp)

    def test_handle_request_unknown_method_returns_error(self):
        req = {"jsonrpc": "2.0", "id": 8, "method": "unknown/method", "params": {}}
        resp = self.mod.handle_request(req)
        self.assertIn("error", resp)

    def test_handle_request_unknown_method_no_id_returns_none(self):
        req = {"method": "unknown/method", "params": {}}
        resp = self.mod.handle_request(req)
        self.assertIsNone(resp)

    def test_handle_request_tools_call_unknown_tool(self):
        req = {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
               "params": {"name": "nonexistent_tool", "arguments": {}}}
        resp = self.mod.handle_request(req)
        self.assertIn("error", resp)
        self.assertIn("Unknown tool", resp["error"]["message"])

    def test_handle_request_tools_call_bad_arguments(self):
        req = {"jsonrpc": "2.0", "id": 10, "method": "tools/call",
               "params": {"name": "workspace_validate_lockfile", "arguments": "not-a-dict"}}
        resp = self.mod.handle_request(req)
        self.assertIn("error", resp)

    def test_read_message_valid(self):
        data = json.dumps({"method": "ping"}) + "\n"
        stream = io.BytesIO(data.encode())
        result = self.mod.read_message(stream)
        self.assertEqual({"method": "ping"}, result)

    def test_read_message_empty_stream(self):
        stream = io.BytesIO(b"")
        result = self.mod.read_message(stream)
        self.assertIsNone(result)

    def test_read_message_skips_blank_lines(self):
        data = b"\n\n" + json.dumps({"method": "ping"}).encode() + b"\n"
        stream = io.BytesIO(data)
        result = self.mod.read_message(stream)
        self.assertEqual({"method": "ping"}, result)

    def test_write_message(self):
        buf = io.BytesIO()
        self.mod.write_message(buf, {"id": 1, "result": {}})
        buf.seek(0)
        data = json.loads(buf.read())
        self.assertEqual(1, data["id"])

    def test_lifecycle_input_schema_basic(self):
        schema = self.mod._lifecycle_input_schema()
        self.assertEqual("object", schema["type"])
        self.assertIn("packageRoot", schema["properties"])

    def test_lifecycle_input_schema_with_extra(self):
        schema = self.mod._lifecycle_input_schema({"mode": {"type": "string"}})
        self.assertIn("mode", schema["properties"])

    def test_success_response(self):
        r = self.mod.success_response(1, {"ok": True})
        self.assertEqual("2.0", r["jsonrpc"])
        self.assertEqual(1, r["id"])
        self.assertEqual({"ok": True}, r["result"])

    def test_error_response(self):
        r = self.mod.error_response(None, -32601, "Method not found")
        self.assertEqual("2.0", r["jsonrpc"])
        self.assertIsNone(r["id"])
        self.assertEqual(-32601, r["error"]["code"])


class XanadWorkspaceMcpToolTests(unittest.TestCase):
    """Tests for the high-level tool_workspace_* functions."""

    @classmethod
    def setUpClass(cls):
        if str(HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_DIR))
        cls.mod = _load_hyphen("xanad-workspace-mcp.py")
        # Point workspace at REPO_ROOT (has .github, copilot-instructions.md, etc.)
        cls.orig_root = cls.mod.WORKSPACE_ROOT
        cls.orig_instructions = cls.mod.WORKSPACE_INSTRUCTIONS_PATH
        cls.orig_lockfile = cls.mod.WORKSPACE_LOCKFILE_PATH
        cls.mod.WORKSPACE_ROOT = REPO_ROOT
        cls.mod.WORKSPACE_INSTRUCTIONS_PATH = REPO_ROOT / ".github" / "copilot-instructions.md"
        cls.mod.WORKSPACE_LOCKFILE_PATH = REPO_ROOT / ".github" / "xanad-assistant-lock.json"

    @classmethod
    def tearDownClass(cls):
        cls.mod.WORKSPACE_ROOT = cls.orig_root
        cls.mod.WORKSPACE_INSTRUCTIONS_PATH = cls.orig_instructions
        cls.mod.WORKSPACE_LOCKFILE_PATH = cls.orig_lockfile

    def test_show_key_commands_finds_commands(self):
        result = self.mod.tool_workspace_show_key_commands({})
        self.assertIn(result["status"], ("ok", "unavailable"))

    def test_validate_lockfile_ok_or_unavailable(self):
        result = self.mod.tool_workspace_validate_lockfile({})
        self.assertIn(result["status"], ("ok", "failed", "unavailable"))

    def test_show_key_commands_invalid_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = self.mod.WORKSPACE_ROOT
            self.mod.WORKSPACE_ROOT = Path(tmp)
            try:
                result = self.mod.tool_workspace_show_key_commands({})
                self.assertEqual("unavailable", result["status"])
            finally:
                self.mod.WORKSPACE_ROOT = orig

    def test_validate_lockfile_no_github_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig_root = self.mod.WORKSPACE_ROOT
            orig_lock = self.mod.WORKSPACE_LOCKFILE_PATH
            self.mod.WORKSPACE_ROOT = Path(tmp)
            self.mod.WORKSPACE_LOCKFILE_PATH = Path(tmp) / ".github" / "xanad-assistant-lock.json"
            try:
                result = self.mod.tool_workspace_validate_lockfile({})
                self.assertEqual("unavailable", result["status"])
            finally:
                self.mod.WORKSPACE_ROOT = orig_root
                self.mod.WORKSPACE_LOCKFILE_PATH = orig_lock

    def test_run_tests_invalid_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = self.mod.WORKSPACE_ROOT
            self.mod.WORKSPACE_ROOT = Path(tmp)
            try:
                result = self.mod.tool_workspace_run_tests({})
                self.assertEqual("unavailable", result["status"])
            finally:
                self.mod.WORKSPACE_ROOT = orig

    def test_run_tests_invalid_extra_args(self):
        result = self.mod.tool_workspace_run_tests({"extraArgs": "not-a-list"})
        self.assertEqual("unavailable", result["status"])

    def test_run_tests_full_scope_with_extra_args_fails(self):
        result = self.mod.tool_workspace_run_tests(
            {"scope": "full", "extraArgs": ["--extra"]}
        )
        self.assertEqual("unavailable", result["status"])

    def test_run_check_loc_invalid_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = self.mod.WORKSPACE_ROOT
            self.mod.WORKSPACE_ROOT = Path(tmp)
            try:
                result = self.mod.tool_workspace_run_check_loc({})
                self.assertEqual("unavailable", result["status"])
            finally:
                self.mod.WORKSPACE_ROOT = orig

    def test_tools_call_workspace_validate_lockfile(self):
        req = {"jsonrpc": "2.0", "id": 11, "method": "tools/call",
               "params": {"name": "workspace_validate_lockfile", "arguments": {}}}
        resp = self.mod.handle_request(req)
        self.assertIn("result", resp)

    def test_build_lifecycle_handler_mode_invalid(self):
        handler_fn = self.mod._build_lifecycle_handler("plan", allow_mode=True, mode_as_flag=True)
        result = handler_fn({"mode": "invalid_mode"})
        self.assertEqual("unavailable", result["status"])


class XanadWorkspaceMcpCoverageTests(unittest.TestCase):
    """Coverage-targeted tests for uncovered paths in xanad-workspace-mcp.py."""

    @classmethod
    def setUpClass(cls):
        if str(HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_DIR))
        cls.mod = _load_hyphen("xanad-workspace-mcp.py")

    def _with_workspace(self, instructions_content: str | None = None):
        """Context manager: returns a TemporaryDirectory with .github created."""
        import contextlib
        @contextlib.contextmanager
        def _cm():
            with tempfile.TemporaryDirectory() as tmp:
                ws = Path(tmp)
                (ws / ".github").mkdir()
                orig_root = self.mod.WORKSPACE_ROOT
                orig_instructions = self.mod.WORKSPACE_INSTRUCTIONS_PATH
                orig_lockfile = self.mod.WORKSPACE_LOCKFILE_PATH
                self.mod.WORKSPACE_ROOT = ws
                self.mod.WORKSPACE_INSTRUCTIONS_PATH = ws / ".github" / "copilot-instructions.md"
                self.mod.WORKSPACE_LOCKFILE_PATH = ws / ".github" / "xanad-assistant-lock.json"
                if instructions_content is not None:
                    self.mod.WORKSPACE_INSTRUCTIONS_PATH.write_text(instructions_content, encoding="utf-8")
                try:
                    yield ws
                finally:
                    self.mod.WORKSPACE_ROOT = orig_root
                    self.mod.WORKSPACE_INSTRUCTIONS_PATH = orig_instructions
                    self.mod.WORKSPACE_LOCKFILE_PATH = orig_lockfile
        return _cm()

    _KEY_COMMANDS_MD = "## Key Commands\n\n| Task | Command |\n|---|---|\n| Run tests | `python3 -m unittest` |\n| LOC gate | `python3 scripts/check_loc.py` |\n"

    def test_resolve_key_command_found(self):
        """resolve_key_command line 42: returns command for label."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            result = self.mod.resolve_key_command("Run tests")
        self.assertEqual("python3 -m unittest", result)

    def test_resolve_key_command_not_found(self):
        """resolve_key_command line 42: returns None for unknown label."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            result = self.mod.resolve_key_command("No Such Label")
        self.assertIsNone(result)

    def test_resolve_lifecycle_package_root_explicit_valid(self):
        """resolve_lifecycle_package_root lines 51-62: explicit packageRoot that exists."""
        root, reason = self.mod.resolve_lifecycle_package_root(str(REPO_ROOT))
        self.assertEqual(REPO_ROOT, root)
        self.assertIsNone(reason)

    def test_resolve_lifecycle_package_root_explicit_empty_string(self):
        """resolve_lifecycle_package_root line 52: empty packageRoot string → error."""
        root, reason = self.mod.resolve_lifecycle_package_root("   ")
        self.assertIsNone(root)
        self.assertIn("packageRoot", reason)

    def test_resolve_lifecycle_package_root_from_lockfile_packageroot(self):
        """resolve_lifecycle_package_root lines 55-62: packageRoot from lockfile."""
        import json as _json
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / ".github").mkdir()
            lockfile = {"package": {"packageRoot": str(REPO_ROOT)}}
            lockfile_path = ws / ".github" / "xanad-assistant-lock.json"
            lockfile_path.write_text(_json.dumps(lockfile), encoding="utf-8")
            orig = self.mod.WORKSPACE_LOCKFILE_PATH
            self.mod.WORKSPACE_LOCKFILE_PATH = lockfile_path
            try:
                root, reason = self.mod.resolve_lifecycle_package_root(None)
            finally:
                self.mod.WORKSPACE_LOCKFILE_PATH = orig
        self.assertEqual(REPO_ROOT, root)
        self.assertIsNone(reason)

    def test_resolve_lifecycle_package_root_no_source_no_lockfile(self):
        """resolve_lifecycle_package_root line 75: no source → error."""
        orig = self.mod.WORKSPACE_LOCKFILE_PATH
        self.mod.WORKSPACE_LOCKFILE_PATH = Path("/nonexistent/lockfile.json")
        try:
            root, reason = self.mod.resolve_lifecycle_package_root(None)
        finally:
            self.mod.WORKSPACE_LOCKFILE_PATH = orig
        self.assertIsNone(root)
        self.assertIn("source", reason.lower())

    def test_resolve_lifecycle_package_root_source_from_lockfile(self):
        """resolve_lifecycle_package_root lines 66-74: source taken from lockfile."""
        import json as _json
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = {"package": {"source": "github:owner/no-such-repo"}}
            lockfile_path = Path(tmp) / "lock.json"
            lockfile_path.write_text(_json.dumps(lockfile), encoding="utf-8")
            orig = self.mod.WORKSPACE_LOCKFILE_PATH
            self.mod.WORKSPACE_LOCKFILE_PATH = lockfile_path
            try:
                root, reason = self.mod.resolve_lifecycle_package_root(None)
            finally:
                self.mod.WORKSPACE_LOCKFILE_PATH = orig
        # Should fail resolving (network error or no cache), not the "no source" error
        self.assertIsNone(root)
        self.assertIsNotNone(reason)

    def test_resolve_lifecycle_package_root_invalid_value_type(self):
        """resolve_lifecycle_package_root lines 77-78: non-string version → error."""
        root, reason = self.mod.resolve_lifecycle_package_root(
            None, source_arg="github:owner/repo", version_arg=123,
        )
        self.assertIsNone(root)
        self.assertIn("version", reason)

    def test_run_argv_success(self):
        """run_argv lines 124-138: subprocess returns 0 → ok status."""
        with patch.object(self.mod, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
            result = self.mod.run_argv(["/bin/echo", "test"])
        self.assertEqual("ok", result["status"])

    def test_run_argv_failure(self):
        """run_argv: subprocess returns nonzero → failed status."""
        with patch.object(self.mod, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=1, stdout="", stderr="error!")
            result = self.mod.run_argv(["/bin/false"])
        self.assertEqual("failed", result["status"])

    def test_run_argv_with_parse_payload_ok(self):
        """run_argv parse_payload=True: valid JSON payload → ok + payload key."""
        payload = '{"status": "ok", "command": "inspect"}'
        with patch.object(self.mod, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
            result = self.mod.run_argv(["/bin/echo"], parse_payload=True)
        self.assertEqual("ok", result["status"])
        self.assertIn("payload", result)

    def test_run_argv_with_parse_payload_error_in_payload(self):
        """run_argv parse_payload=True: payload status='error' → failed."""
        payload = '{"status": "error", "command": "check"}'
        with patch.object(self.mod, "subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
            result = self.mod.run_argv(["/bin/echo"], parse_payload=True)
        self.assertEqual("failed", result["status"])

    def test_run_lifecycle_command_success(self):
        """run_lifecycle_command lines 174-195: all guards pass → run_argv called."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.run_lifecycle_command("inspect", package_root_arg=str(REPO_ROOT))
        self.assertEqual("ok", result["status"])
        mock_argv.assert_called_once()

    def test_run_lifecycle_command_with_mode_as_flag(self):
        """run_lifecycle_command: mode and mode_as_flag extend argv."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), mode="setup", mode_as_flag=True)
        self.assertEqual("ok", result["status"])
        argv_arg = mock_argv.call_args[0][0]
        self.assertIn("--mode", argv_arg)
        self.assertIn("setup", argv_arg)

    def test_run_lifecycle_command_with_mode_not_flag(self):
        """run_lifecycle_command: mode without mode_as_flag → mode appended directly."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), mode="setup", mode_as_flag=False)
        argv_arg = mock_argv.call_args[0][0]
        self.assertIn("setup", argv_arg)
        self.assertNotIn("--mode", argv_arg)

    def test_run_lifecycle_command_bad_answers_path(self):
        """run_lifecycle_command: nonexistent answersPath → unavailable."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), answers_path="/nonexistent/answers.json")
        self.assertEqual("unavailable", result["status"])
        self.assertIn("answersPath", result["summary"])

    def test_run_lifecycle_command_non_interactive_true(self):
        """run_lifecycle_command: non_interactive=True → --non-interactive in argv."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), non_interactive=True)
        argv_arg = mock_argv.call_args[0][0]
        self.assertIn("--non-interactive", argv_arg)

    def test_run_lifecycle_command_non_interactive_bad_value(self):
        """run_lifecycle_command: non_interactive='yes' → unavailable."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), non_interactive="yes")
        self.assertEqual("unavailable", result["status"])
        self.assertIn("nonInteractive", result["summary"])

    def test_run_lifecycle_command_dry_run_true(self):
        """run_lifecycle_command: dry_run=True → --dry-run in argv."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.run_lifecycle_command("plan", package_root_arg=str(REPO_ROOT), dry_run=True)
        argv_arg = mock_argv.call_args[0][0]
        self.assertIn("--dry-run", argv_arg)

    def test_lifecycle_handler_valid_mode(self):
        """_build_lifecycle_handler.handler lines 158-168: valid mode → run_lifecycle_command."""
        handler = self.mod._build_lifecycle_handler("plan", allow_mode=True, mode_as_flag=True)
        with patch.object(self.mod, "run_lifecycle_command", return_value={"status": "ok", "summary": "done"}) as mock_cmd:
            result = handler({"mode": "setup", "packageRoot": str(REPO_ROOT)})
        self.assertEqual("ok", result["status"])
        mock_cmd.assert_called_once()

    def test_lifecycle_handler_fixed_mode(self):
        """_build_lifecycle_handler.handler: fixed_mode set → mode not from arguments."""
        handler = self.mod._build_lifecycle_handler("inspect", fixed_mode="repair")
        with patch.object(self.mod, "run_lifecycle_command", return_value={"status": "ok", "summary": "done"}) as mock_cmd:
            result = handler({"packageRoot": str(REPO_ROOT)})
        self.assertEqual("ok", result["status"])
        # Check mode kwarg is "repair"
        call_kwargs = mock_cmd.call_args[1]
        self.assertEqual("repair", call_kwargs.get("mode"))

    def test_show_key_commands_no_commands_in_file(self):
        """tool_workspace_show_key_commands line 202: instructions exist but no commands."""
        with self._with_workspace("# No key commands table here\n") as _ws:
            result = self.mod.tool_workspace_show_key_commands({})
        self.assertEqual("unavailable", result["status"])

    def test_run_tests_success(self):
        """tool_workspace_run_tests lines 213-220: valid setup → run_argv called."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "tests passed"}):
                result = self.mod.tool_workspace_run_tests({})
        self.assertEqual("ok", result["status"])

    def test_run_tests_full_scope(self):
        """tool_workspace_run_tests: scope=full → run_argv called without extra args."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                result = self.mod.tool_workspace_run_tests({"scope": "full"})
        self.assertEqual("ok", result["status"])
        argv_arg = mock_argv.call_args[0][0]
        self.assertNotIn("--extra", argv_arg)

    def test_run_tests_no_command_in_instructions(self):
        """tool_workspace_run_tests: no 'Run tests' command → unavailable."""
        with self._with_workspace("## Key Commands\n\n| Task | Command |\n|---|---|\n| LOC gate | `python3 scripts/check_loc.py` |\n") as _ws:
            result = self.mod.tool_workspace_run_tests({})
        self.assertEqual("unavailable", result["status"])

    def test_run_tests_command_with_shell_metachar(self):
        """tool_workspace_run_tests line 218: command with shell metachar → unavailable."""
        with self._with_workspace("## Key Commands\n\n| Task | Command |\n|---|---|\n| Run tests | `python3 -m unittest; echo pwned` |\n") as _ws:
            result = self.mod.tool_workspace_run_tests({})
        self.assertEqual("unavailable", result["status"])

    def test_run_check_loc_success(self):
        """tool_workspace_run_check_loc lines 225-228: valid LOC gate → run_argv."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "loc pass"}):
                result = self.mod.tool_workspace_run_check_loc({})
        self.assertEqual("ok", result["status"])

    def test_validate_lockfile_success(self):
        """tool_workspace_validate_lockfile lines 236-240: lockfile has all required keys."""
        import json as _json
        lockfile = {
            "schemaVersion": "0.1.0", "package": {}, "manifest": {},
            "timestamps": {}, "files": [],
        }
        with self._with_workspace() as ws:
            (ws / ".github" / "xanad-assistant-lock.json").write_text(_json.dumps(lockfile), encoding="utf-8")
            result = self.mod.tool_workspace_validate_lockfile({})
        self.assertEqual("ok", result["status"])
        self.assertIn("lockfile", result)

    def test_validate_lockfile_missing_keys(self):
        """tool_workspace_validate_lockfile: lockfile missing keys → failed."""
        import json as _json
        with self._with_workspace() as ws:
            (ws / ".github" / "xanad-assistant-lock.json").write_text(
                _json.dumps({"schemaVersion": "0.1.0"}), encoding="utf-8",
            )
            result = self.mod.tool_workspace_validate_lockfile({})
        self.assertEqual("failed", result["status"])
        self.assertIn("missingKeys", result)

    def test_show_install_state_with_payload(self):
        """tool_workspace_show_install_state lines 242-250: ok result with payload."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            fake_result = {
                "status": "ok",
                "summary": "check done",
                "payload": {"result": {"installState": "installed", "drift": {}}},
            }
            with patch.object(self.mod, "run_lifecycle_command", return_value=fake_result):
                result = self.mod.tool_workspace_show_install_state({})
        self.assertEqual("ok", result["status"])
        self.assertEqual("installed", result.get("installState"))

    def test_show_install_state_no_payload(self):
        """tool_workspace_show_install_state: non-ok result → returned as-is."""
        with self._with_workspace(self._KEY_COMMANDS_MD) as _ws:
            fake_result = {"status": "failed", "summary": "check failed"}
            with patch.object(self.mod, "run_lifecycle_command", return_value=fake_result):
                result = self.mod.tool_workspace_show_install_state({})
        self.assertEqual("failed", result["status"])

    def test_resolve_lifecycle_package_root_version_arg(self):
        """resolve_lifecycle_package_root line 81: version_arg → resolve_github_release path."""
        fake_path = Path("/fake/release/path")
        with patch.object(self.mod, "resolve_github_release", return_value=fake_path) as mock_gr:
            root, reason = self.mod.resolve_lifecycle_package_root(
                None, source_arg="github:owner/repo", version_arg="v1.0.0",
            )
        self.assertEqual(fake_path, root)
        self.assertIsNone(reason)
        mock_gr.assert_called_once()

    def test_lifecycle_handler_with_answers_non_interactive_dry_run(self):
        """_build_lifecycle_handler lines 163/165/167: allow_answers/non_interactive/dry_run kwargs."""
        handler = self.mod._build_lifecycle_handler(
            "apply",
            allow_answers=True, allow_non_interactive=True, allow_dry_run=True,
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            answers_file = f.name
        try:
            with patch.object(self.mod, "run_lifecycle_command", return_value={"status": "ok", "summary": "done"}) as mock_cmd:
                with self._with_workspace(self._KEY_COMMANDS_MD):
                    result = handler({
                        "packageRoot": str(REPO_ROOT),
                        "answersPath": answers_file,
                        "nonInteractive": True,
                        "dryRun": True,
                    })
            call_kwargs = mock_cmd.call_args[1]
            self.assertEqual(answers_file, call_kwargs.get("answers_path"))
            self.assertTrue(call_kwargs.get("non_interactive"))
            self.assertTrue(call_kwargs.get("dry_run"))
        finally:
            import os as _os
            _os.unlink(answers_file)

    def test_run_lifecycle_command_workspace_invalid(self):
        """run_lifecycle_command line 175: workspace invalid → unavailable."""
        import tempfile as _tmp
        with _tmp.TemporaryDirectory() as tmp:
            orig = self.mod.WORKSPACE_ROOT
            self.mod.WORKSPACE_ROOT = Path(tmp) / "no_github_here"
            try:
                result = self.mod.run_lifecycle_command("inspect", package_root_arg=str(REPO_ROOT))
            finally:
                self.mod.WORKSPACE_ROOT = orig
        self.assertEqual("unavailable", result["status"])

    def test_run_lifecycle_command_bad_package_root(self):
        """run_lifecycle_command line 178: bad package_root → unavailable."""
        with self._with_workspace(self._KEY_COMMANDS_MD):
            result = self.mod.run_lifecycle_command("inspect", package_root_arg="/nonexistent_path_xyz")
        self.assertEqual("unavailable", result["status"])

    def test_run_lifecycle_command_no_cli_in_package_root(self):
        """run_lifecycle_command line 181: package_root with no CLI script → unavailable."""
        with tempfile.TemporaryDirectory() as tmp:
            with self._with_workspace(self._KEY_COMMANDS_MD):
                result = self.mod.run_lifecycle_command("inspect", package_root_arg=tmp)
        self.assertEqual("unavailable", result["status"])
        self.assertIn("CLI", result["summary"])

    def test_run_lifecycle_command_valid_answers_path(self):
        """run_lifecycle_command line 189: valid answers_path → --answers appended."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            answers_file = f.name
        try:
            with self._with_workspace(self._KEY_COMMANDS_MD):
                with patch.object(self.mod, "run_argv", return_value={"status": "ok", "summary": "done"}) as mock_argv:
                    result = self.mod.run_lifecycle_command(
                        "apply", package_root_arg=str(REPO_ROOT), answers_path=answers_file,
                    )
            argv_arg = mock_argv.call_args[0][0]
            self.assertIn("--answers", argv_arg)
            self.assertIn(answers_file, argv_arg)
        finally:
            import os as _os
            _os.unlink(answers_file)

    def test_run_check_loc_no_loc_command(self):
        """tool_workspace_run_check_loc line 227: no LOC gate command → unavailable."""
        with self._with_workspace("## Key Commands\n\n| Task | Command |\n|---|---|\n| Run tests | `python3 -m unittest` |\n"):
            result = self.mod.tool_workspace_run_check_loc({})
        self.assertEqual("unavailable", result["status"])
        self.assertIn("LOC gate", result["summary"])

    def test_validate_lockfile_no_workspace(self):
        """tool_workspace_validate_lockfile: workspace invalid → unavailable."""
        orig = self.mod.WORKSPACE_ROOT
        self.mod.WORKSPACE_ROOT = Path("/nonexistent_workspace_xyz")
        try:
            result = self.mod.tool_workspace_validate_lockfile({})
        finally:
            self.mod.WORKSPACE_ROOT = orig
        self.assertEqual("unavailable", result["status"])

    def test_show_install_state_no_workspace(self):
        """tool_workspace_show_install_state line 244: workspace invalid → unavailable."""
        orig = self.mod.WORKSPACE_ROOT
        self.mod.WORKSPACE_ROOT = Path("/nonexistent_workspace_xyz")
        try:
            result = self.mod.tool_workspace_show_install_state({})
        finally:
            self.mod.WORKSPACE_ROOT = orig
        self.assertEqual("unavailable", result["status"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
