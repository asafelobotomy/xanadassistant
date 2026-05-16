from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_sequential_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "hooks" / "scripts" / "mcpSequentialThinkingServer.py"
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("test_seqThinkingMcp", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load mcpSequentialThinkingServer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SEQ_MODULE = load_sequential_module()


class SequentialThinkingMcpTests(unittest.TestCase):
    def test_sequentialthinking_rejects_invalid_branch_id(self) -> None:
        SEQ_MODULE.reset_thinking_session()
        result = SEQ_MODULE.sequentialthinking(
            thought="Start",
            next_thought_needed=True,
            thought_number=1,
            total_thoughts=2,
            branch_id="bad branch id",
        )

        self.assertEqual(result["status"], "failed")
        self.assertIn("branch_id", result["error"])


if __name__ == "__main__":
    unittest.main()