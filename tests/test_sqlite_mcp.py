from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


def load_sqlite_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[1]
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


SOURCE_SQLITE_MODULE = load_sqlite_module("hooks/scripts/sqliteMcp.py", "test_sqliteMcp_source")
MANAGED_SQLITE_MODULE = load_sqlite_module(
    ".github/hooks/scripts/sqliteMcp.py", "test_sqliteMcp_managed"
)


class SqliteMcpTests(unittest.TestCase):
    def test_execute_query_reads_workspace_local_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_root = Path(tmpdir)
            db_path = workspace_root / "sample.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE items (name TEXT)")
                conn.execute("INSERT INTO items (name) VALUES ('alpha')")
                conn.commit()

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
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE items (name TEXT)")
                conn.commit()

            for module in (SOURCE_SQLITE_MODULE, MANAGED_SQLITE_MODULE):
                with self.subTest(module=module.__name__):
                    module.WORKSPACE_ROOT = workspace_root
                    with self.assertRaisesRegex(ValueError, "within the workspace root"):
                        module.execute_query(str(db_path), "SELECT name FROM sqlite_master")

    def test_execute_query_rejects_write_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_root = Path(tmpdir)
            db_path = workspace_root / "sample.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute("CREATE TABLE items (name TEXT)")
                conn.commit()

            for module in (SOURCE_SQLITE_MODULE, MANAGED_SQLITE_MODULE):
                with self.subTest(module=module.__name__):
                    module.WORKSPACE_ROOT = workspace_root
                    with self.assertRaisesRegex(ValueError, "read-only workspace-local inspection"):
                        module.execute_query(
                            str(db_path),
                            "INSERT INTO items (name) VALUES ('beta')",
                            allow_writes=True,
                        )


if __name__ == "__main__":
    unittest.main()