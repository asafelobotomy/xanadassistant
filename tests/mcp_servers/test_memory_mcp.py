from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_memory_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load memoryMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SOURCE_MEMORY_MODULE = load_memory_module("mcp/scripts/memoryMcp.py", "test_memoryMcp_source")
MANAGED_MEMORY_MODULE = load_memory_module(".github/mcp/scripts/memoryMcp.py", "test_memoryMcp_managed")


class MemoryMcpTests(unittest.TestCase):
    def test_workspace_scope_persists_across_branch_changes(self) -> None:
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with mock.patch.object(module, "_current_branch", return_value="feature/a"):
                            module.memory_set("tester", "repo.language", "python", scope="workspace")

                        with mock.patch.object(module, "_current_branch", return_value="feature/b"):
                            result = module.memory_get("tester", "repo.language", scope="workspace")

                payload = json.loads(result)
                self.assertEqual(payload["branch"], "")
                self.assertEqual(payload["value"], "python")

    def test_branch_scope_remains_branch_local(self) -> None:
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with mock.patch.object(module, "_current_branch", return_value="feature/a"):
                            module.memory_set("tester", "repo.status", "active", scope="branch")

                        with mock.patch.object(module, "_current_branch", return_value="feature/b"):
                            result = module.memory_get("tester", "repo.status", scope="branch")

                self.assertIn("No active fact", result)

    def test_rejects_out_of_range_confidence(self) -> None:
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with self.assertRaisesRegex(ValueError, "confidence must be between 0.0 and 1.0"):
                            module.memory_set("tester", "repo.confidence", "high", confidence=1.5)

    def test_future_valid_from_hides_fact_from_retrieval(self) -> None:
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        module.memory_set(
                            "tester",
                            "repo.phase",
                            "future",
                            valid_from="2999-01-01T00:00:00Z",
                        )

                        get_result = module.memory_get("tester", "repo.phase")
                        list_result = module.memory_list("tester")
                        dump_result = json.loads(module.memory_dump("tester"))

                self.assertIn("No active fact", get_result)
                self.assertIn("No active facts", list_result)
                self.assertEqual(dump_result["facts"], [])

    def test_expired_valid_until_hides_fact_from_retrieval(self) -> None:
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        module.memory_set(
                            "tester",
                            "repo.phase",
                            "past",
                            valid_until="2000-01-01T00:00:00Z",
                        )

                        get_result = module.memory_get("tester", "repo.phase")
                        list_result = module.memory_list("tester")
                        dump_result = json.loads(module.memory_dump("tester"))

                self.assertIn("No active fact", get_result)
                self.assertIn("No active facts", list_result)
                self.assertEqual(dump_result["facts"], [])

    def test_memory_dump_exposes_rules_and_scope_metadata(self) -> None:
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        module.memory_set("tester", "repo.rule", "active", scope="workspace")
                        dump_result = json.loads(module.memory_dump("tester"))

                self.assertEqual(dump_result["rules"], [])
                self.assertEqual(dump_result["facts"][0]["scope"], "workspace")

    def test_remove_invalidate_rules_and_diary_flow(self) -> None:
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        module.memory_set("tester", "repo.status", "active")
                        invalidated = module.memory_invalidate("tester", "repo.status")
                        missing = module.memory_remove("tester", "repo.status")
                        rule_added = module.rule_add("Prefer narrow tests", "prefer", agent="tester")
                        rules = module.rule_list("tester")
                        module.diary_add("tester", "Implemented hook tests", tags="tests,coverage")
                        diary = module.diary_get("tester", tag="coverage")
                        search = module.diary_search("tester", "hook")
                        removed_rule = module.rule_remove(1)

                self.assertIn("Invalidated 'repo.status'", invalidated)
                self.assertIn("Removed 'repo.status'", missing)
                self.assertIn("Rule #", rule_added)
                self.assertIn("Prefer narrow tests", rules)
                self.assertIn("Implemented hook tests", diary)
                self.assertIn("Implemented hook tests", search)
                self.assertIn("Rule #1 deleted.", removed_rule)

    def test_helper_validation_and_prune_contracts(self) -> None:
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "WORKSPACE_ROOT"):
                    with mock.patch.dict(os.environ, {}, clear=True):
                        module._workspace_root()
                with self.assertRaisesRegex(ValueError, "scope must be one of"):
                    module._chk_scope("invalid")
                with self.assertRaisesRegex(ValueError, "rule_type must be one of"):
                    module._chk_rule_type("sometimes")
                with self.assertRaisesRegex(ValueError, "agent must be"):
                    module._chk_agent("bad agent")

                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        module.memory_set("tester", "repo.temp", "x", ttl_days=-1)
                        pruned = module.memory_prune(agent="tester", scope="workspace", max_age_days=0.4)

                self.assertIn("Pruned", pruned)


if __name__ == "__main__":
    unittest.main()