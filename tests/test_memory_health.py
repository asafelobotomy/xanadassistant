from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._memory_check import check_memory_health


class CheckMemoryHealthTests(unittest.TestCase):
    def test_skips_checks_when_memory_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            warnings = check_memory_health(
                workspace,
                setup_answers={"hooks.enabled": False, "mcp.enabled": False},
            )

        self.assertEqual(warnings, [])

    def test_reports_missing_artifacts_when_memory_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            warnings = check_memory_health(
                workspace,
                setup_answers={"hooks.enabled": True, "mcp.enabled": True},
            )

        warning_codes = {warning["code"] for warning in warnings}
        self.assertEqual(warning_codes, {"memory_mcp_missing", "memory_db_missing"})


if __name__ == "__main__":
    unittest.main()