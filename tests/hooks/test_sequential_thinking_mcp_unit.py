"""Unit tests for mcpSequentialThinkingServer.py hook."""
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


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class SequentialThinkingMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_hyphen("mcpSequentialThinkingServer.py")

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
# gitMcp.py  (local operations only)
# ---------------------------------------------------------------------------

REPO_PATH = str(REPO_ROOT)



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
