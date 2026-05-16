from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_time_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "hooks" / "scripts" / "timeMcp.py"
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("test_timeMcp", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load timeMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


TIME_MODULE = load_time_module()


class TimeMcpTests(unittest.TestCase):
    def test_convert_timezone_uses_from_tz_for_naive_input(self) -> None:
        converted = TIME_MODULE.convert_timezone(
            timestamp="2026-01-01T12:00:00",
            from_tz="America/New_York",
            to_tz="UTC",
        )

        self.assertEqual(converted, "2026-01-01T17:00:00+00:00")


if __name__ == "__main__":
    unittest.main()