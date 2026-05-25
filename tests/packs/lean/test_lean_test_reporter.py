from __future__ import annotations

import unittest

from tests.mcp_servers._mcp_module_loader import load_mcp_script_module


def load_lean_test_reporter_module():
    return load_mcp_script_module(
        "packs/lean/mcp/leanTestReporter.py",
        "test_leanTestReporter",
        "leanTestReporter.py",
    )


LEAN_TEST_REPORTER_MODULE = load_lean_test_reporter_module()


class LeanTestReporterTests(unittest.TestCase):
    def test_detect_runner_and_filter_pytest_failures(self) -> None:
        output = (
            "============================= FAILURES =============================\n"
            "____________________________ test_example ____________________________\n"
            "tests/test_example.py:12: AssertionError\n"
            "=================== 1 failed, 3 passed, 2 skipped in 0.12s ===================\n"
        )

        runner = LEAN_TEST_REPORTER_MODULE._detect_runner(output)
        filtered = LEAN_TEST_REPORTER_MODULE.filter_failures(output, runner="auto")

        self.assertEqual(runner, "pytest")
        self.assertIn("FAIL  test_example", filtered)
        self.assertIn("tests/test_example.py:12", filtered)

    def test_filter_unittest_failures_and_generic_summary(self) -> None:
        unittest_output = (
            "FAIL: test_name (pkg.TestCase)\n"
            "-----\n"
            "Traceback (most recent call last):\n"
            "  File \"tests/test_unit.py\", line 8, in test_name\n"
            "AssertionError: boom\n"
            "Ran 3 tests in 0.01s\n"
            "FAILED (failures=1)\n"
        )
        generic_output = "42 passing\n1 failing\n"

        filtered = LEAN_TEST_REPORTER_MODULE.filter_failures(unittest_output, runner="unittest")
        summary = LEAN_TEST_REPORTER_MODULE.count_summary(generic_output, runner="auto")

        self.assertIn("FAIL  test_name (pkg.TestCase)", filtered)
        self.assertIn("tests/test_unit.py:8", filtered)
        self.assertEqual(summary, "1 failing")

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

    def test_filter_failures_returns_summary_when_no_failures_found(self) -> None:
        output = "Ran 2 tests in 0.01s\nOK\n"

        filtered = LEAN_TEST_REPORTER_MODULE.filter_failures(output, runner="unittest")

        self.assertEqual(filtered, "Ran: 2 — failed: 0, passed: 2, skipped: 0")


if __name__ == "__main__":
    unittest.main()