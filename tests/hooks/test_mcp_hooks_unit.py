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


# ---------------------------------------------------------------------------
# timeMcp.py
# ---------------------------------------------------------------------------

@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class TimeMcpImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_hyphen("timeMcp.py")

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
# sqliteMcp.py
# ---------------------------------------------------------------------------

@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class SqliteMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("sqliteMcp")
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
# mcpSequentialThinkingServer.py
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
