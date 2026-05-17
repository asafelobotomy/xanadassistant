from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


def load_sqlite_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load sqliteMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SOURCE_SQLITE_MODULE = load_sqlite_module("mcp/scripts/sqliteMcp.py", "test_sqliteMcp_source")
MANAGED_SQLITE_MODULE = load_sqlite_module(
    ".github/mcp/scripts/sqliteMcp.py", "test_sqliteMcp_managed"
)


class SqliteMcpTests(unittest.TestCase):
    def test_discover_workspace_root_and_helpers(self) -> None:
        for module in (SOURCE_SQLITE_MODULE, MANAGED_SQLITE_MODULE):
            with self.subTest(module=module.__name__):
                fake_script = Path("/tmp/a/b/c/sqliteMcp.py")
                with tempfile.TemporaryDirectory() as tmpdir:
                    workspace = Path(tmpdir)
                    (workspace / ".github").mkdir()
                    nested = workspace / "hooks" / "scripts" / "sqliteMcp.py"
                    nested.parent.mkdir(parents=True)
                    nested.write_text("# stub\n", encoding="utf-8")
                    self.assertEqual(module.discover_workspace_root(nested), workspace)
                self.assertEqual(module.discover_workspace_root(fake_script), fake_script.resolve().parents[min(3, len(fake_script.resolve().parents) - 1)])

    def test_execute_query_reads_workspace_local_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_root = Path(tmpdir)
            db_path = workspace_root / "sample.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE items (name TEXT)")
                conn.execute("INSERT INTO items (name) VALUES ('alpha')")
                conn.commit()
            finally:
                conn.close()

            for module in (SOURCE_SQLITE_MODULE, MANAGED_SQLITE_MODULE):
                with self.subTest(module=module.__name__):
                    module.WORKSPACE_ROOT = workspace_root
                    result = module.execute_query(str(db_path), "SELECT name FROM items")
                    self.assertIn("alpha", result)

    def test_execute_query_rejects_out_of_workspace_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_root = Path(tmpdir) / "workspace"
            external_root = Path(tmpdir) / "external"
            workspace_root.mkdir()
            external_root.mkdir()
            db_path = external_root / "sample.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE items (name TEXT)")
                conn.commit()
            finally:
                conn.close()

            for module in (SOURCE_SQLITE_MODULE, MANAGED_SQLITE_MODULE):
                with self.subTest(module=module.__name__):
                    module.WORKSPACE_ROOT = workspace_root
                    with self.assertRaisesRegex(ValueError, "within the workspace root"):
                        module.execute_query(str(db_path), "SELECT name FROM sqlite_master")

    def test_execute_query_rejects_write_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_root = Path(tmpdir)
            db_path = workspace_root / "sample.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE items (name TEXT)")
                conn.commit()
            finally:
                conn.close()

            for module in (SOURCE_SQLITE_MODULE, MANAGED_SQLITE_MODULE):
                with self.subTest(module=module.__name__):
                    module.WORKSPACE_ROOT = workspace_root
                    with self.assertRaisesRegex(ValueError, "read-only workspace-local inspection"):
                        module.execute_query(
                            str(db_path),
                            "INSERT INTO items (name) VALUES ('beta')",
                            allow_writes=True,
                        )

    def test_list_describe_and_formatting_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_root = Path(tmpdir)
            db_path = workspace_root / "sample.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE items (name TEXT, qty INTEGER)")
                conn.execute("CREATE VIEW item_names AS SELECT name FROM items")
                conn.executemany("INSERT INTO items (name, qty) VALUES (?, ?)", [("alpha", 1), ("beta", 2), ("gamma", 3)])
                conn.commit()
            finally:
                conn.close()

            for module in (SOURCE_SQLITE_MODULE, MANAGED_SQLITE_MODULE):
                with self.subTest(module=module.__name__):
                    module.WORKSPACE_ROOT = workspace_root
                    tables = module.list_tables(str(db_path))
                    described = module.describe_table(str(db_path), "items")
                    missing = module.describe_table(str(db_path), "missing")
                    capped = module.execute_query(str(db_path), "SELECT name, qty FROM items ORDER BY name", max_rows=2)
                    bad_query = None
                    try:
                        module.execute_query(str(db_path), "SELECT * FROM missing_table")
                    except RuntimeError as exc:
                        bad_query = str(exc)

                self.assertIn("[table] items", tables)
                self.assertIn("[view] item_names", tables)
                self.assertIn("CREATE TABLE items", described)
                self.assertIn("No table or view named 'missing'", missing)
                self.assertIn("output capped at 2 rows", capped)
                self.assertIn("no such table", bad_query)


if __name__ == "__main__":
    unittest.main()