from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_lean_test_reporter_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "packs" / "lean" / "hooks" / "leanTestReporter.py"
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("test_leanTestReporter", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load leanTestReporter.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


LEAN_TEST_REPORTER_MODULE = load_lean_test_reporter_module()


class LeanTestReporterTests(unittest.TestCase):
    def test_pytest_summary_preserves_skipped_count(self) -> None:
        output = (
            "============================= test session starts =============================\n"
            "collected 6 items\n"
            "\n"
            "tests/test_example.py .Fs.s.                                         [100%]\n"
            "=================== 1 failed, 3 passed, 2 skipped in 0.12s ===================\n"
        )

        summary = LEAN_TEST_REPORTER_MODULE.count_summary(output, runner="pytest")

        self.assertEqual(summary, "Ran: 6 — failed: 1, passed: 3, skipped: 2")


if __name__ == "__main__":
    unittest.main()