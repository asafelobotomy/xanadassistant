from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from tests.mcp_servers._mcp_module_loader import load_mcp_script_pair

SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE = load_mcp_script_pair("memoryMcp.py", "test_memoryMcp")


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

    def test_branch_scope_raises_when_git_fails(self) -> None:
        """branch-scope operations must fail closed, not collapse to the empty-string branch."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with mock.patch.object(module, "_current_branch", return_value=None):
                            with self.assertRaisesRegex(ValueError, "Cannot resolve current git branch"):
                                module.memory_set("tester", "repo.status", "active", scope="branch")

    def test_branch_scope_git_failure_does_not_pollute_empty_branch(self) -> None:
        """A fact must NOT be stored under the empty-string branch when git resolution fails."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        # First write a workspace-scoped fact (stored under branch="")
                        with mock.patch.object(module, "_current_branch", return_value="main"):
                            module.memory_set("tester", "ws.key", "value", scope="workspace")
                        # Now attempt a branch-scoped write with git unavailable — must raise
                        with mock.patch.object(module, "_current_branch", return_value=None):
                            with self.assertRaisesRegex(ValueError, "Cannot resolve"):
                                module.memory_set("tester", "br.key", "leaked", scope="branch")
                        # workspace-scoped fact under branch="" must still be there, branch-scoped must not
                        with mock.patch.object(module, "_current_branch", return_value="main"):
                            ws_result = module.memory_get("tester", "ws.key", scope="workspace")
                            br_result = module.memory_get("tester", "br.key", scope="branch")
                self.assertIn("value", ws_result)
                self.assertIn("No active fact", br_result)

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


    def test_diary_search_fts_special_chars_do_not_raise(self) -> None:
        """FTS-reserved characters (hyphens, colons, OR) in user queries must not raise."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        module.diary_add("tester", "branch-specific: NOT a bug OR feature")
                        result = module.diary_search("tester", "branch-specific: NOT a bug OR feature")
                # FTS-special query must not raise; result is either a match or the no-entries string
                self.assertIsInstance(result, str)

    def test_prune_fractional_days_preserves_fresh_fact(self) -> None:
        """memory_prune(max_age_days=0.4) must not delete a fact written seconds ago."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        module.memory_set("tester", "fresh.key", "keep-me")
                        module.memory_prune(agent="tester", scope="workspace", max_age_days=0.4)
                        result = module.memory_get("tester", "fresh.key")
                self.assertNotIn("No active fact", result, "Fresh fact must survive a 0.4-day prune")

    def test_valid_from_rejects_malformed_timestamp(self) -> None:
        """memory_set must raise ValueError for a malformed valid_from timestamp."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with self.assertRaisesRegex(ValueError, "valid_from"):
                            module.memory_set("tester", "key", "val", valid_from="not-a-date")

    def test_valid_until_rejects_malformed_timestamp(self) -> None:
        """memory_set must raise ValueError for a malformed valid_until timestamp."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with self.assertRaisesRegex(ValueError, "valid_until"):
                            module.memory_set("tester", "key", "val", valid_until="2026/01/15")

    def test_diary_branch_scope_isolation(self) -> None:
        """Branch-scoped diary entries must not be visible from a different branch."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with mock.patch.object(module, "_current_branch", return_value="feature/a"):
                            module.diary_add("tester", "entry on feature/a", scope="branch")
                        with mock.patch.object(module, "_current_branch", return_value="feature/b"):
                            get_result = module.diary_get("tester", scope="branch")
                            search_result = module.diary_search("tester", "feature", scope="branch")
                self.assertIn("No diary entries", get_result)
                self.assertIn("No diary entries", search_result)

    def test_memory_dump_collapses_same_key_across_scopes(self) -> None:
        """memory_dump must return one fact per key; higher scope wins (branch > workspace)."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with mock.patch.object(module, "_current_branch", return_value="main"):
                            module.memory_set("tester", "shared.key", "workspace-value", scope="workspace")
                            module.memory_set("tester", "shared.key", "branch-value", scope="branch")
                            dump = json.loads(module.memory_dump("tester"))
                key_facts = [f for f in dump["facts"] if f["key"] == "shared.key"]
                self.assertEqual(len(key_facts), 1, "Expected exactly one fact per key in dump")
                self.assertEqual(key_facts[0]["value"], "branch-value",
                                 "Branch scope must win over workspace")

    def test_session_scope_isolated_across_session_ids(self) -> None:
        """Session-scoped facts must be invisible to a different session."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with mock.patch.object(module, "_SESSION_ID", "session-a"):
                            module.memory_set("tester", "task.progress", "50%", scope="session")
                        with mock.patch.object(module, "_SESSION_ID", "session-b"):
                            get_result = module.memory_get("tester", "task.progress", scope="session")
                            dump = json.loads(module.memory_dump("tester"))
                self.assertIn("No active fact", get_result)
                session_facts = [f for f in dump["facts"] if f["scope"] == "session"]
                self.assertEqual(session_facts, [], "Other session's facts must not appear in dump")

    def test_source_description_stored_and_returned(self) -> None:
        """source_description passed to memory_set must appear in memory_get and memory_dump."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        module.memory_set(
                            "tester", "annotated.key", "value",
                            source_description="Inferred from CI error in turn 3",
                        )
                        get_result = json.loads(module.memory_get("tester", "annotated.key"))
                        dump = json.loads(module.memory_dump("tester"))
                self.assertEqual(get_result.get("source_description"),
                                 "Inferred from CI error in turn 3")
                dump_fact = next(f for f in dump["facts"] if f["key"] == "annotated.key")
                self.assertEqual(dump_fact.get("source_description"),
                                 "Inferred from CI error in turn 3")

    def test_session_same_key_both_readable(self) -> None:
        """Two different sessions writing the same key must each retain their own value."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with mock.patch.object(module, "_SESSION_ID", "session-a"):
                            module.memory_set("tester", "task.key", "value-a", scope="session")
                        with mock.patch.object(module, "_SESSION_ID", "session-b"):
                            module.memory_set("tester", "task.key", "value-b", scope="session")
                        with mock.patch.object(module, "_SESSION_ID", "session-a"):
                            result_a = json.loads(module.memory_get("tester", "task.key", scope="session"))
                        with mock.patch.object(module, "_SESSION_ID", "session-b"):
                            result_b = json.loads(module.memory_get("tester", "task.key", scope="session"))
                self.assertEqual(result_a["value"], "value-a")
                self.assertEqual(result_b["value"], "value-b")

    def test_diary_session_scope_isolated(self) -> None:
        """Session-scoped diary entries must not be visible to a different session."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with mock.patch.object(module, "_SESSION_ID", "session-a"):
                            module.diary_add("tester", "session-a entry", scope="session")
                        with mock.patch.object(module, "_SESSION_ID", "session-b"):
                            get_result = module.diary_get("tester", scope="session")
                            search_result = module.diary_search("tester", "session-a", scope="session")
                self.assertIn("No diary entries", get_result)
                self.assertIn("No diary entries", search_result)

    def test_diary_add_branch_fails_closed(self) -> None:
        """diary_add with scope='branch' must raise when git branch cannot be resolved."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with mock.patch.object(module, "_current_branch", return_value=None):
                            with self.assertRaisesRegex(ValueError, "Cannot resolve current git branch"):
                                module.diary_add("tester", "orphan entry", scope="branch")

    def test_rule_add_rejects_branch_on_non_branch_scope(self) -> None:
        """rule_add must reject a non-empty branch for non-branch scopes."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with self.assertRaisesRegex(ValueError, "branch must be None or empty"):
                            module.rule_add("Stay within scope", "always", agent="tester",
                                            scope="workspace", branch="feature/x")

    def test_rule_list_branch_filtered(self) -> None:
        """rule_list for scope='branch' must return only rules for the current branch."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        with mock.patch.object(module, "_current_branch", return_value="feature/a"):
                            module.rule_add("Rule on feature/a", "always", scope="branch")
                        with mock.patch.object(module, "_current_branch", return_value="feature/b"):
                            module.rule_add("Rule on feature/b", "always", scope="branch")
                            result = module.rule_list(scope="branch")
                    self.assertIn("Rule on feature/b", result)
                    self.assertNotIn("Rule on feature/a", result)

    def test_memory_dump_summary_field_shape(self) -> None:
        """memory_dump must include a summary with has_data, total_facts, total_rules, counts."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        empty_dump = json.loads(module.memory_dump("tester"))
                        module.memory_set("tester", "ci.cmd", "pytest")
                        module.rule_add("Prefer pytest", "prefer", agent="tester")
                        full_dump = json.loads(module.memory_dump("tester"))

                # Empty DB: has_data must be False
                empty_summary = empty_dump["summary"]
                self.assertFalse(empty_summary["has_data"])
                self.assertEqual(empty_summary["total_facts"], 0)
                self.assertEqual(empty_summary["total_rules"], 0)

                # Non-empty DB: has_data True, counts correct
                full_summary = full_dump["summary"]
                self.assertTrue(full_summary["has_data"])
                self.assertEqual(full_summary["total_facts"], 1)
                self.assertEqual(full_summary["total_rules"], 1)
                self.assertIn("fresh_count", full_summary)
                self.assertIn("stale_count", full_summary)

    def test_memory_dump_facts_include_age_metadata(self) -> None:
        """Each fact in memory_dump must include age_hours, is_fresh, and is_stale."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        module.memory_set("tester", "build.tool", "make")
                        dump = json.loads(module.memory_dump("tester"))

                fact = dump["facts"][0]
                self.assertIn("age_hours", fact)
                self.assertIn("is_fresh", fact)
                self.assertIn("is_stale", fact)
                # A fact written seconds ago must be fresh and not stale
                self.assertIsInstance(fact["age_hours"], float)
                self.assertGreaterEqual(fact["age_hours"], 0.0)
                self.assertTrue(fact["is_fresh"], "A just-written fact must be fresh")
                self.assertFalse(fact["is_stale"], "A just-written fact must not be stale")

    def test_memory_dump_task_hint_adds_relevance_score(self) -> None:
        """task_hint must add a relevance_score field and sort higher-scoring facts first."""
        for module in (SOURCE_MEMORY_MODULE, MANAGED_MEMORY_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with mock.patch.dict(os.environ, {"WORKSPACE_ROOT": tmpdir}, clear=False):
                        module.memory_set("tester", "ci.commands", "pytest tests/")
                        module.memory_set("tester", "repo.language", "python")
                        dump_hint = json.loads(module.memory_dump("tester", task_hint="run ci tests"))
                        dump_no_hint = json.loads(module.memory_dump("tester"))

                # With hint: every fact must have a relevance_score
                for fact in dump_hint["facts"]:
                    self.assertIn("relevance_score", fact)
                # "ci.commands" shares tokens with "ci" and "tests" in the hint; must rank first
                self.assertEqual(dump_hint["facts"][0]["key"], "ci.commands",
                                 "ci.commands must rank highest for hint='run ci tests'")
                # Without hint: no relevance_score field
                for fact in dump_no_hint["facts"]:
                    self.assertNotIn("relevance_score", fact)

