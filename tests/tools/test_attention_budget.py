from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_attention_budget.py"


class AttentionBudgetTests(unittest.TestCase):
    def test_succeeds_when_files_are_within_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            target = repo_root / "docs" / "note.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("line 1\nline 2\n", encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT_PATH),
                    "--repo-root",
                    str(repo_root),
                    "--budget",
                    "docs/note.md=2",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("OK    docs/note.md  2/2", result.stderr)

    def test_fails_when_file_exceeds_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            target = repo_root / "docs" / "note.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT_PATH),
                    "--repo-root",
                    str(repo_root),
                    "--budget",
                    "docs/note.md=2",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("ERROR attention budget exceeded  docs/note.md  3>2", result.stderr)

    def test_fails_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT_PATH),
                    "--repo-root",
                    str(repo_root),
                    "--budget",
                    "docs/missing.md=2",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("ERROR missing file  docs/missing.md", result.stderr)


if __name__ == "__main__":
    unittest.main()