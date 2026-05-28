from __future__ import annotations

import unittest

from tests.mcp_servers._mcp_module_loader import load_mcp_script_pair

SOURCE_TIME_MODULE, MANAGED_TIME_MODULE = load_mcp_script_pair("timeMcp.py", "test_timeMcp")


class TimeMcpTests(unittest.TestCase):
    def test_convert_timezone_uses_from_tz_for_naive_input(self) -> None:
        for module in (SOURCE_TIME_MODULE, MANAGED_TIME_MODULE):
            with self.subTest(module=module.__name__):
                converted = module.convert_timezone(
                    timestamp="2026-01-01T12:00:00",
                    from_tz="America/New_York",
                    to_tz="UTC",
                )

                self.assertEqual(converted, "2026-01-01T17:00:00+00:00")

    def test_elapsed_and_format_duration_cover_remaining_branches(self) -> None:
        for module in (SOURCE_TIME_MODULE, MANAGED_TIME_MODULE):
            with self.subTest(module=module.__name__):
                self.assertEqual(module.format_duration(0.25), "250.0ms")
                self.assertEqual(module.format_duration(12), "12.00s")
                self.assertEqual(module.format_duration(61), "1m 1s")
                self.assertEqual(module.format_duration(3661), "1h 1m 1s")
                self.assertEqual(module.format_duration(90061), "1d 1h 1m")
                self.assertIn("negative", module.elapsed("2026-01-02T00:00:00+00:00", "2026-01-01T00:00:00+00:00"))

    def test_invalid_inputs_raise_clear_value_errors(self) -> None:
        for module in (SOURCE_TIME_MODULE, MANAGED_TIME_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "Cannot parse"):
                    module.elapsed("not-a-date", "2026-01-01T00:00:00+00:00")
                with self.assertRaisesRegex(ValueError, "Unknown timezone"):
                    module.current_time("Mars/Olympus")


if __name__ == "__main__":
    unittest.main()