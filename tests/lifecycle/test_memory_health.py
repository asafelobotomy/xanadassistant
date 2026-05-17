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
        self.assertEqual(
            warning_codes,
            {"memory_mcp_missing", "memory_mcp_unregistered", "memory_db_missing"},
        )

    def test_reports_missing_mcp_config_when_hook_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            hook_path = workspace / ".github" / "hooks" / "scripts" / "memoryMcp.py"
            hook_path.parent.mkdir(parents=True, exist_ok=True)
            hook_path.write_text("# installed hook\n", encoding="utf-8")

            warnings = check_memory_health(
                workspace,
                setup_answers={"hooks.enabled": True, "mcp.enabled": True},
            )

        warning_codes = {warning["code"] for warning in warnings}
        self.assertIn("memory_mcp_unregistered", warning_codes)


if __name__ == "__main__":
    unittest.main()
