from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_sequential_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load sequentialThinkingMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SOURCE_SEQ_MODULE = load_sequential_module("mcp/scripts/sequentialThinkingMcp.py", "test_seqThinkingMcp_source")
MANAGED_SEQ_MODULE = load_sequential_module(".github/mcp/scripts/sequentialThinkingMcp.py", "test_seqThinkingMcp_managed")


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
                    thought_number=1,
                    total_thoughts=1,
                )

                self.assertEqual(too_long["status"], "failed")
                self.assertIn("maximum length", too_long["error"])
                self.assertEqual(missing_ref["status"], "failed")
                self.assertIn("does not match any recorded thought number", missing_ref["error"])
                self.assertEqual(branched["branches"], ["alt_path"])
                self.assertEqual(branched["total_thoughts"], 2)
                self.assertEqual(history_full["status"], "failed")
                self.assertIn("history limit", history_full["error"])


if __name__ == "__main__":
    unittest.main()