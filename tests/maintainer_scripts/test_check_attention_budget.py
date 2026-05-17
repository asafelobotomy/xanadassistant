from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from scripts import check_attention_budget


class CheckAttentionBudgetTests(unittest.TestCase):
    def test_parse_budget_validates_shape_and_values(self) -> None:
        self.assertEqual(check_attention_budget.parse_budget("docs/file.md=12"), ("docs/file.md", 12))

        for value in ("missing-separator", "=12", "docs/file.md=zero"):
            with self.assertRaises(Exception):
                check_attention_budget.parse_budget(value)

        with self.assertRaises(Exception):
            check_attention_budget.parse_budget("docs/file.md=0")

    def test_run_reports_ok_missing_and_budget_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ok_file = root / "ok.md"
            long_file = root / "long.md"
            ok_file.write_text("one\ntwo\n", encoding="utf-8")
            long_file.write_text("1\n2\n3\n4\n", encoding="utf-8")

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = check_attention_budget.run(
                    root,
                    [("ok.md", 3), ("long.md", 2), ("missing.md", 1)],
                )

        output = stderr.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("OK    ok.md", output)
        self.assertIn("ERROR attention budget exceeded  long.md", output)
        self.assertIn("ERROR missing file  missing.md", output)

    def test_main_uses_default_budgets_or_cli_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            custom = root / "custom.md"
            custom.write_text("one\n", encoding="utf-8")

            with unittest.mock.patch("scripts.check_attention_budget.run", return_value=0) as run:
                exit_code = check_attention_budget.main(["--repo-root", str(root), "--budget", "custom.md=5"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(run.call_args.args[0], root.resolve())
        self.assertEqual(run.call_args.args[1], [("custom.md", 5)])


if __name__ == "__main__":
    unittest.main()