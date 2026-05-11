from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_loc.py"


def _write_lines(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join("x\n" for _ in range(count)), encoding="utf-8")


class CheckLocTests(unittest.TestCase):
    def test_warns_for_default_threshold_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            target = repo_root / "scripts" / "long.py"
            _write_lines(target, 251)

            result = subprocess.run(
                ["python3", str(SCRIPT_PATH), "scripts/long.py"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("WARN", result.stderr)
        self.assertIn("scripts/long.py", result.stderr)

    def test_does_not_warn_for_mcp_hook_override_below_override_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            target = repo_root / "hooks" / "scripts" / "xanad-workspace-mcp.py"
            _write_lines(target, 370)

            result = subprocess.run(
                ["python3", str(SCRIPT_PATH), "hooks/scripts/xanad-workspace-mcp.py"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stderr)

    def test_mcp_hook_override_still_fails_at_hard_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            target = repo_root / "hooks" / "scripts" / "xanad-workspace-mcp.py"
            _write_lines(target, 401)

            result = subprocess.run(
                ["python3", str(SCRIPT_PATH), "hooks/scripts/xanad-workspace-mcp.py"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("ERROR", result.stderr)
        self.assertIn("hard limit: 400", result.stderr)


if __name__ == "__main__":
    unittest.main()