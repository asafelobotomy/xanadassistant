"""Unit tests for hooks/scripts/memoryMcp.py.

Covers advisory memory, rules, agent diary (add/get/search), prune, and dump.
All tests use a temporary directory for the DB; WORKSPACE_ROOT is patched per class.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks" / "scripts"
_MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


def _load():
    path = HOOKS_DIR / "memoryMcp.py"
    spec = importlib.util.spec_from_file_location("memoryMcp", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _MemBase(unittest.TestCase):
    """Base: fresh temp DB per subclass; WORKSPACE_ROOT set in env."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load()
        cls._tmpdir = tempfile.mkdtemp()
        os.environ["WORKSPACE_ROOT"] = cls._tmpdir

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("WORKSPACE_ROOT", None)
        shutil.rmtree(cls._tmpdir, ignore_errors=True)


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class MemorySetGetTests(_MemBase):
    def test_set_returns_confirmation(self):
        r = self.mod.memory_set("test-agent", "repo.lang", "Python")
        self.assertIn("repo.lang", r)
        self.assertIn("test-agent", r)

    def test_get_returns_fact_as_json(self):
        self.mod.memory_set("test-agent", "ci.tool", "pytest")
        data = json.loads(self.mod.memory_get("test-agent", "ci.tool"))
        self.assertEqual(data["value"], "pytest")
        self.assertEqual(data["agent"], "test-agent")

    def test_get_falls_back_to_shared(self):
        self.mod.memory_set("shared", "shared.key", "shared-value")
        data = json.loads(self.mod.memory_get("other-agent", "shared.key"))
        self.assertEqual(data["agent"], "shared")

    def test_get_returns_not_found_message(self):
        r = self.mod.memory_get("test-agent", "nonexistent.key.xyz")
        self.assertIn("No active fact", r)

    def test_set_upserts_value(self):
        self.mod.memory_set("test-agent", "upsert.key", "v1")
        self.mod.memory_set("test-agent", "upsert.key", "v2")
        data = json.loads(self.mod.memory_get("test-agent", "upsert.key"))
        self.assertEqual(data["value"], "v2")

    def test_remove_hard_deletes_entry(self):
        self.mod.memory_set("test-agent", "del.key", "del-val")
        r = self.mod.memory_remove("test-agent", "del.key")
        self.assertIn("Removed", r)
        self.assertIn("No active fact", self.mod.memory_get("test-agent", "del.key"))

    def test_invalidate_soft_deletes_entry(self):
        self.mod.memory_set("test-agent", "soft.key", "soft-val")
        r = self.mod.memory_invalidate("test-agent", "soft.key")
        self.assertIn("Invalidated", r)
        self.assertIn("No active fact", self.mod.memory_get("test-agent", "soft.key"))


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class MemoryBranchScopeTests(_MemBase):
    def test_set_stores_detected_branch(self):
        with patch.object(self.mod, "_current_branch", return_value="feature-x"):
            self.mod.memory_set("branch-agent", "b.key", "b.val")
            data = json.loads(self.mod.memory_get("branch-agent", "b.key"))
        self.assertEqual(data["branch"], "feature-x")

    def test_get_isolated_by_branch(self):
        with patch.object(self.mod, "_current_branch", return_value="branch-a"):
            self.mod.memory_set("branch-agent", "iso.key", "on-a")
        with patch.object(self.mod, "_current_branch", return_value="branch-b"):
            r = self.mod.memory_get("branch-agent", "iso.key")
        self.assertIn("No active fact", r)

    def test_git_failure_falls_back_to_empty_branch(self):
        with patch.object(self.mod, "_current_branch", return_value=""):
            self.mod.memory_set("branch-agent", "nogit.key", "val")
            data = json.loads(self.mod.memory_get("branch-agent", "nogit.key"))
        self.assertEqual(data["branch"], "")


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class MemoryRulesTests(_MemBase):
    def test_rule_add_returns_id(self):
        r = self.mod.rule_add("Never modify generated files", "never")
        self.assertIn("Rule #", r)
        self.assertIn("never", r)

    def test_rule_list_returns_added_rule(self):
        self.mod.rule_add("Always run tests before commit", "always")
        r = self.mod.rule_list()
        self.assertIn("always", r)
        self.assertIn("Always run tests", r)

    def test_rule_remove_deletes_by_id(self):
        result = self.mod.rule_add("Temporary rule", "prefer")
        rule_id = int(result.split("#")[1].split(" ")[0])
        self.assertIn(f"Rule #{rule_id} deleted", self.mod.rule_remove(rule_id))

    def test_rule_list_empty_scope_returns_message(self):
        self.assertIn("No rules", self.mod.rule_list(scope="session"))

    def test_rule_list_filters_by_agent(self):
        self.mod.rule_add("Agent-specific rule", "avoid", agent="my-agent")
        self.assertIn("Agent-specific rule", self.mod.rule_list(agent="my-agent"))


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class MemoryDumpTests(_MemBase):
    def test_dump_returns_rules_and_facts_keys(self):
        self.mod.memory_set("dump-agent", "d.key", "d.val")
        self.mod.rule_add("Dump rule", "always")
        data = json.loads(self.mod.memory_dump("dump-agent"))
        self.assertIn("rules", data)
        self.assertIn("facts", data)

    def test_dump_includes_shared_facts(self):
        self.mod.memory_set("shared", "shared.dump.key", "s-val")
        data = json.loads(self.mod.memory_dump("dump-agent"))
        self.assertIn("shared", [f["agent"] for f in data["facts"]])

    def test_dump_facts_include_metadata_fields(self):
        self.mod.memory_set("dump-agent", "ts.key", "ts.val")
        data = json.loads(self.mod.memory_dump("dump-agent"))
        facts = [f for f in data["facts"] if f["key"] == "ts.key"]
        self.assertTrue(facts)
        self.assertIn("updated_at", facts[0])
        self.assertIn("expires_at", facts[0])
        self.assertIn("valid_from", facts[0])
        self.assertIn("valid_until", facts[0])

    def test_dump_agent_facts_ordered_before_shared(self):
        self.mod.memory_set("dump-agent", "agent.fact", "agent-val")
        self.mod.memory_set("shared", "shared.order.key", "s-val")
        data = json.loads(self.mod.memory_dump("dump-agent"))
        agents = [f["agent"] for f in data["facts"]]
        agent_indices = [i for i, a in enumerate(agents) if a == "dump-agent"]
        shared_indices = [i for i, a in enumerate(agents) if a == "shared"]
        if agent_indices and shared_indices:
            self.assertLess(max(agent_indices), min(shared_indices))


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class MemoryPruneTests(_MemBase):
    def test_prune_removes_expired_rows(self):
        # ttl_days=0 sets expires_at=now; prune runs after, so it's past
        self.mod.memory_set("prune-agent", "exp.key", "exp.val", ttl_days=0)
        r = self.mod.memory_prune(agent="prune-agent")
        self.assertIn("expired", r)

    def test_prune_by_age_syncs_fts_index(self):
        self.mod.diary_add("prune-agent", "old entry synced", tags="prune")
        # max_age_days=0 deletes all entries recorded at or before now
        r = self.mod.memory_prune(agent="prune-agent", max_age_days=0)
        self.assertIn("diary", r)
        self.assertIn("No diary entries matched",
                      self.mod.diary_search("prune-agent", "old entry synced"))

    def test_prune_scoped_to_agent_does_not_affect_others(self):
        self.mod.memory_set("scoped-keep", "sk.key", "sk.val", ttl_days=30)
        self.mod.memory_prune(agent="other-prune-agent")
        r = self.mod.memory_get("scoped-keep", "sk.key")
        self.assertNotIn("No active fact", r)


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class DiaryTests(_MemBase):
    def test_add_returns_entry_id(self):
        r = self.mod.diary_add("diary-agent", "Ran tests successfully")
        self.assertIn("Diary entry #", r)

    def test_get_returns_entries_newest_first(self):
        self.mod.diary_add("diary-agent", "Entry A")
        self.mod.diary_add("diary-agent", "Entry B")
        r = self.mod.diary_get("diary-agent", limit=10)
        self.assertIn("Entry A", r)
        self.assertIn("Entry B", r)
        self.assertLess(r.index("Entry B"), r.index("Entry A"))

    def test_get_filters_by_tag(self):
        self.mod.diary_add("diary-agent", "Tagged entry", tags="deploy,release")
        r = self.mod.diary_get("diary-agent", tag="deploy")
        self.assertIn("Tagged entry", r)

    def test_get_empty_returns_message(self):
        self.assertIn("No diary entries", self.mod.diary_get("no-entries-agent"))

    def test_get_tag_mismatch_returns_empty(self):
        self.assertIn("No diary entries",
                      self.mod.diary_get("diary-agent", tag="no-such-tag-xyz"))


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class DiaryFTS5Tests(_MemBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mod.diary_add("fts-agent", "Deployed to production using helm", tags="deploy,helm")
        cls.mod.diary_add("fts-agent", "Ran CI pipeline on main branch", tags="ci,main")
        cls.mod.diary_add("other-agent", "Other agent deployed service", tags="deploy")

    def test_search_finds_matching_entry(self):
        r = self.mod.diary_search("fts-agent", "helm")
        self.assertIn("helm", r)
        self.assertIn("fts-agent", r)

    def test_search_scoped_to_agent_by_default(self):
        r = self.mod.diary_search("fts-agent", "deployed")
        self.assertNotIn("other-agent", r)

    def test_search_include_agents_widens_scope(self):
        r = self.mod.diary_search("fts-agent", "deployed", include_agents=["other-agent"])
        self.assertIn("other-agent", r)

    def test_search_no_match_returns_message(self):
        self.assertIn("No diary entries matched",
                      self.mod.diary_search("fts-agent", "nonexistentword99999"))

    def test_search_fts5_operational_error_raised_as_runtime_error(self):
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = sqlite3.OperationalError("bad fts query")
        with patch.object(self.mod, "_get_conn", return_value=mock_conn):
            with self.assertRaises(RuntimeError) as ctx:
                self.mod.diary_search("fts-agent", "bad")
        self.assertIn("FTS5 search error", str(ctx.exception))

    def test_search_does_not_match_scope_column_as_token(self):
        """FTS search for 'workspace' must not match entries via the scope column."""
        # All entries in setUpClass have scope='workspace' but none mention it in entry/tags
        r = self.mod.diary_search("fts-agent", "workspace")
        self.assertIn("No diary entries matched", r)


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class MemoryListIncludeAgentsTests(_MemBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mod.memory_set("agent-a", "a.key", "a.val")
        cls.mod.memory_set("agent-b", "b.key", "b.val")
        cls.mod.memory_set("shared", "shared.list.key", "s-val")

    def test_list_returns_own_keys(self):
        r = self.mod.memory_list("agent-a", include_shared=False)
        self.assertIn("agent-a/a.key", r)
        self.assertNotIn("agent-b/b.key", r)

    def test_list_includes_shared_by_default(self):
        self.assertIn("shared/shared.list.key", self.mod.memory_list("agent-a"))

    def test_list_include_agents_unions_keys(self):
        r = self.mod.memory_list("agent-a", include_shared=False, include_agents=["agent-b"])
        self.assertIn("agent-a/a.key", r)
        self.assertIn("agent-b/b.key", r)

    def test_list_empty_agent_returns_message(self):
        self.assertIn("No active facts",
                      self.mod.memory_list("empty-agent-xyz", include_shared=False))


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class MemoryGetIncludeAgentsTests(_MemBase):
    def test_get_include_agents_cross_agent_peek(self):
        self.mod.memory_set("peek-source", "cross.key", "cross-val")
        data = json.loads(
            self.mod.memory_get("peek-target", "cross.key", include_agents=["peek-source"])
        )
        self.assertEqual(data["agent"], "peek-source")
        self.assertEqual(data["value"], "cross-val")

    def test_get_include_agents_prefers_primary_agent(self):
        self.mod.memory_set("primary-agent", "pref.key", "primary-val")
        self.mod.memory_set("secondary-agent", "pref.key", "secondary-val")
        data = json.loads(
            self.mod.memory_get("primary-agent", "pref.key", include_agents=["secondary-agent"])
        )
        self.assertEqual(data["agent"], "primary-agent")


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class SecurityTests(_MemBase):
    def test_invalid_scope_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.mod.memory_set("agent", "k", "v", scope="bad-scope")

    def test_invalid_rule_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.mod.rule_add("desc", "badtype")

    def test_invalid_agent_name_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.mod.memory_set("bad agent!", "k", "v")

    def test_agent_with_hyphens_and_digits_is_valid(self):
        r = self.mod.memory_set("valid-agent-123", "k", "v")
        self.assertIn("valid-agent-123", r)

    def test_rule_add_invalid_branch_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.mod.rule_add("desc", "always", branch="invalid branch!")

    def test_rule_add_valid_branch_accepted(self):
        r = self.mod.rule_add("desc", "always", branch="feature/my-branch")
        self.assertIn("Rule #", r)

    def test_missing_workspace_root_raises_value_error(self):
        saved = os.environ.pop("WORKSPACE_ROOT")
        try:
            with self.assertRaises(ValueError) as ctx:
                self.mod._workspace_root()
            self.assertIn("WORKSPACE_ROOT", str(ctx.exception))
        finally:
            os.environ["WORKSPACE_ROOT"] = saved


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available")
class DiaryAddAtomicityTests(_MemBase):
    def test_fts_insert_failure_rolls_back_main_table(self):
        """If the FTS insert fails, the main diary row must also be rolled back."""
        import sqlite3 as _sqlite3
        real_get_conn = self.mod._get_conn
        call_count = [0]

        def patched_get_conn():
            conn = real_get_conn()
            original_execute = conn.execute

            def guarded_execute(sql, *args, **kwargs):
                call_count[0] += 1
                if "agent_diary_fts" in sql and "INSERT" in sql:
                    raise _sqlite3.OperationalError("simulated FTS failure")
                return original_execute(sql, *args, **kwargs)

            conn.execute = guarded_execute
            return conn

        count_before = len(
            real_get_conn().execute("SELECT id FROM agent_diary").fetchall()
        )
        with patch.object(self.mod, "_get_conn", side_effect=patched_get_conn):
            with self.assertRaises(Exception):
                self.mod.diary_add("atomic-agent", "Should not persist")
        count_after = len(
            real_get_conn().execute("SELECT id FROM agent_diary").fetchall()
        )
        self.assertEqual(count_before, count_after,
                         "Main diary row must be rolled back when FTS insert fails")


if __name__ == "__main__":
    unittest.main()
