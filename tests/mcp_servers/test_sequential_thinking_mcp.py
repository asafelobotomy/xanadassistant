from __future__ import annotations

import unittest

from tests.mcp_servers._mcp_module_loader import load_mcp_script_module

SOURCE_SEQ_MODULE = load_mcp_script_module(
    "mcp/scripts/sequentialThinkingMcp.py", "test_seqThinkingMcp_source", "sequentialThinkingMcp.py"
)
MANAGED_SEQ_MODULE = load_mcp_script_module(
    ".github/mcp/scripts/sequentialThinkingMcp.py", "test_seqThinkingMcp_managed", "sequentialThinkingMcp.py"
)


class SequentialThinkingMcpTests(unittest.TestCase):
    def test_sequentialthinking_rejects_invalid_branch_id(self) -> None:
        for module in (SOURCE_SEQ_MODULE, MANAGED_SEQ_MODULE):
            with self.subTest(module=module.__name__):
                module.reset_thinking_session()
                result = module.sequentialthinking(
                    thought="Start",
                    next_thought_needed=True,
                    thought_number=1,
                    total_thoughts=2,
                    branch_id="bad branch id",
                )

                self.assertEqual(result["status"], "failed")
                self.assertIn("branch_id", result["error"])

    def test_reset_thinking_session_clears_accumulated_thoughts(self) -> None:
        for module in (SOURCE_SEQ_MODULE, MANAGED_SEQ_MODULE):
            with self.subTest(module=module.__name__):
                module.reset_thinking_session()
                first = module.sequentialthinking(
                    thought="Start",
                    next_thought_needed=False,
                    thought_number=1,
                    total_thoughts=1,
                )
                module.reset_thinking_session()
                second = module.sequentialthinking(
                    thought="Again",
                    next_thought_needed=False,
                    thought_number=1,
                    total_thoughts=1,
                )

                self.assertEqual(first["thought_history_length"], 1)
                self.assertEqual(second["thought_history_length"], 1)
                self.assertEqual(second["thought_number"], 1)

    def test_sequentialthinking_validates_history_references_and_limits(self) -> None:
        for module in (SOURCE_SEQ_MODULE, MANAGED_SEQ_MODULE):
            with self.subTest(module=module.__name__):
                module.reset_thinking_session()
                too_long = module.sequentialthinking(
                    thought="x" * (module.MAX_THOUGHT_CHARS + 1),
                    next_thought_needed=True,
                    thought_number=1,
                    total_thoughts=1,
                )
                missing_ref = module.sequentialthinking(
                    thought="Revise",
                    next_thought_needed=True,
                    thought_number=2,
                    total_thoughts=2,
                    is_revision=True,
                    revises_thought=1,
                )

                module.reset_thinking_session()
                module.sequentialthinking(
                    thought="Base",
                    next_thought_needed=True,
                    thought_number=1,
                    total_thoughts=1,
                )
                branched = module.sequentialthinking(
                    thought="Branch",
                    next_thought_needed=False,
                    thought_number=2,
                    total_thoughts=1,
                    branch_from_thought=1,
                    branch_id="alt_path",
                )

                module._session.thought_history = [
                    {
                        "thought": "existing",
                        "thought_number": index + 1,
                        "total_thoughts": module.MAX_HISTORY,
                        "next_thought_needed": True,
                    }
                    for index in range(module.MAX_HISTORY)
                ]
                history_full = module.sequentialthinking(
                    thought="Overflow",
                    next_thought_needed=False,
                    thought_number=module.MAX_HISTORY + 1,
                    total_thoughts=module.MAX_HISTORY + 1,
                )

                self.assertEqual(too_long["status"], "failed")
                self.assertIn("maximum length", too_long["error"])
                self.assertEqual(missing_ref["status"], "failed")
                self.assertIn("does not match any recorded thought number", missing_ref["error"])
                self.assertEqual(branched["branches"], ["alt_path"])
                self.assertEqual(branched["total_thoughts"], 2)
                self.assertEqual(history_full["status"], "failed")
                self.assertIn("history limit", history_full["error"])

    def test_revision_fields_must_be_consistent(self) -> None:
        for module in (SOURCE_SEQ_MODULE, MANAGED_SEQ_MODULE):
            with self.subTest(module=module.__name__):
                module.reset_thinking_session()
                # is_revision=True without revises_thought
                result = module.sequentialthinking(
                    thought="I revise something",
                    next_thought_needed=True,
                    thought_number=1,
                    total_thoughts=3,
                    is_revision=True,
                )
                self.assertEqual(result["status"], "failed")
                self.assertIn("revises_thought is required", result["error"])

                # revises_thought set without is_revision=True
                result2 = module.sequentialthinking(
                    thought="I reference a thought",
                    next_thought_needed=True,
                    thought_number=5,
                    total_thoughts=3,
                    revises_thought=3,
                )
                self.assertEqual(result2["status"], "failed")
                self.assertIn("is_revision must be True", result2["error"])

    def test_branch_fields_must_be_paired(self) -> None:
        for module in (SOURCE_SEQ_MODULE, MANAGED_SEQ_MODULE):
            with self.subTest(module=module.__name__):
                module.reset_thinking_session()
                module.sequentialthinking(
                    thought="Base", next_thought_needed=True,
                    thought_number=1, total_thoughts=3,
                )
                # branch_from_thought without branch_id
                result = module.sequentialthinking(
                    thought="Branch without id",
                    next_thought_needed=True,
                    thought_number=2,
                    total_thoughts=3,
                    branch_from_thought=1,
                )
                self.assertEqual(result["status"], "failed")
                self.assertIn("branch_from_thought and branch_id", result["error"])

                # branch_id without branch_from_thought
                result2 = module.sequentialthinking(
                    thought="Id without branch",
                    next_thought_needed=True,
                    thought_number=2,
                    total_thoughts=3,
                    branch_id="orphan",
                )
                self.assertEqual(result2["status"], "failed")
                self.assertIn("branch_from_thought and branch_id", result2["error"])

    def test_thought_number_uniqueness_enforced(self) -> None:
        for module in (SOURCE_SEQ_MODULE, MANAGED_SEQ_MODULE):
            with self.subTest(module=module.__name__):
                module.reset_thinking_session()
                first = module.sequentialthinking(
                    thought="First", next_thought_needed=True,
                    thought_number=1, total_thoughts=2,
                )
                self.assertEqual(first["thought_number"], 1)
                duplicate = module.sequentialthinking(
                    thought="Also first",
                    next_thought_needed=False,
                    thought_number=1,
                    total_thoughts=2,
                )
                self.assertEqual(duplicate["status"], "failed")
                self.assertIn("already recorded", duplicate["error"])

    def test_needs_more_thoughts_must_be_bool_when_provided(self) -> None:
        for module in (SOURCE_SEQ_MODULE, MANAGED_SEQ_MODULE):
            with self.subTest(module=module.__name__):
                module.reset_thinking_session()
                result = module.sequentialthinking(
                    thought="Checking advisory",
                    next_thought_needed=True,
                    thought_number=1,
                    total_thoughts=2,
                    needs_more_thoughts="yes",  # non-bool
                )
                self.assertEqual(result["status"], "failed")
                self.assertIn("needs_more_thoughts", result["error"])

    def test_needs_more_thoughts_stored_in_entry_when_valid(self) -> None:
        for module in (SOURCE_SEQ_MODULE, MANAGED_SEQ_MODULE):
            with self.subTest(module=module.__name__):
                module.reset_thinking_session()
                result = module.sequentialthinking(
                    thought="More thoughts needed",
                    next_thought_needed=True,
                    thought_number=1,
                    total_thoughts=2,
                    needs_more_thoughts=True,
                )
                self.assertNotIn("status", result, "expected success but got an error")
                self.assertEqual(result["thought_number"], 1)
                entry = module._session.thought_history[-1]
                self.assertIs(entry.get("needs_more_thoughts"), True)

    def test_source_and_managed_sequential_thinking_scripts_match(self) -> None:
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[2]
        source = (repo_root / "mcp/scripts/sequentialThinkingMcp.py").read_bytes()
        managed = (repo_root / ".github/mcp/scripts/sequentialThinkingMcp.py").read_bytes()
        self.assertEqual(source, managed, "source and managed sequentialThinkingMcp.py differ")


if __name__ == "__main__":
    unittest.main()