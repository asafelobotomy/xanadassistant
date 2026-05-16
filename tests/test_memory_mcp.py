from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_memory_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "hooks" / "scripts" / "memoryMcp.py"
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("test_memoryMcp", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load memoryMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


MEMORY_MODULE = load_memory_module()


class MemoryMcpTests(unittest.TestCase):
    def test_workspace_scope_persists_across_branch_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                with mock.patch.object(MEMORY_MODULE, "_current_branch", return_value="feature/a"):
                    MEMORY_MODULE.memory_set("tester", "repo.language", "python", scope="workspace")

                with mock.patch.object(MEMORY_MODULE, "_current_branch", return_value="feature/b"):
                    result = MEMORY_MODULE.memory_get("tester", "repo.language", scope="workspace")

        payload = json.loads(result)
        self.assertEqual(payload["branch"], "")
        self.assertEqual(payload["value"], "python")

    def test_branch_scope_remains_branch_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                with mock.patch.object(MEMORY_MODULE, "_current_branch", return_value="feature/a"):
                    MEMORY_MODULE.memory_set("tester", "repo.status", "active", scope="branch")

                with mock.patch.object(MEMORY_MODULE, "_current_branch", return_value="feature/b"):
                    result = MEMORY_MODULE.memory_get("tester", "repo.status", scope="branch")

        self.assertIn("No active fact", result)

    def test_rejects_out_of_range_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                with self.assertRaisesRegex(ValueError, "confidence must be between 0.0 and 1.0"):
                    MEMORY_MODULE.memory_set("tester", "repo.confidence", "high", confidence=1.5)

    def test_future_valid_from_hides_fact_from_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                MEMORY_MODULE.memory_set(
                    "tester",
                    "repo.phase",
                    "future",
                    valid_from="2999-01-01T00:00:00Z",
                )

                get_result = MEMORY_MODULE.memory_get("tester", "repo.phase")
                list_result = MEMORY_MODULE.memory_list("tester")
                dump_result = json.loads(MEMORY_MODULE.memory_dump("tester"))

        self.assertIn("No active fact", get_result)
        self.assertIn("No active facts", list_result)
        self.assertEqual(dump_result["facts"], [])

    def test_expired_valid_until_hides_fact_from_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                MEMORY_MODULE.memory_set(
                    "tester",
                    "repo.phase",
                    "past",
                    valid_until="2000-01-01T00:00:00Z",
                )

                get_result = MEMORY_MODULE.memory_get("tester", "repo.phase")
                list_result = MEMORY_MODULE.memory_list("tester")
                dump_result = json.loads(MEMORY_MODULE.memory_dump("tester"))

        self.assertIn("No active fact", get_result)
        self.assertIn("No active facts", list_result)
        self.assertEqual(dump_result["facts"], [])


if __name__ == "__main__":
    unittest.main()