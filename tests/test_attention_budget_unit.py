"""Direct unit tests for scripts/check_attention_budget.py — covers functions missed by subprocess tests."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

import scripts.check_attention_budget as cab


class ParseBudgetTests(unittest.TestCase):
    def test_parse_budget_valid(self) -> None:
        path_text, limit = cab.parse_budget("docs/note.md=100")
        self.assertEqual("docs/note.md", path_text)
        self.assertEqual(100, limit)

    def test_parse_budget_valid_whitespace_around_path(self) -> None:
        path_text, limit = cab.parse_budget("docs/note.md =50")
        self.assertEqual("docs/note.md", path_text)
        self.assertEqual(50, limit)

    def test_parse_budget_no_equals_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cab.parse_budget("docs/note.md")

    def test_parse_budget_empty_path_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cab.parse_budget("=100")

    def test_parse_budget_non_integer_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cab.parse_budget("docs/note.md=abc")

    def test_parse_budget_zero_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cab.parse_budget("docs/note.md=0")

    def test_parse_budget_negative_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cab.parse_budget("docs/note.md=-5")

    def test_parse_budget_minimum_valid(self) -> None:
        path_text, limit = cab.parse_budget("file.md=1")
        self.assertEqual("file.md", path_text)
        self.assertEqual(1, limit)


class CountLinesTests(unittest.TestCase):
    def test_count_lines_correct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.md"
            path.write_text("line1\nline2\n", encoding="utf-8")
            self.assertEqual(2, cab.count_lines(path))

    def test_count_lines_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.md"
            path.write_text("", encoding="utf-8")
            self.assertEqual(0, cab.count_lines(path))


class RunTests(unittest.TestCase):
    def test_run_returns_zero_within_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "docs" / "note.md"
            path.parent.mkdir()
            path.write_text("line1\nline2\n", encoding="utf-8")
            result = cab.run(root, [("docs/note.md", 5)])
            self.assertEqual(0, result)

    def test_run_returns_zero_at_exact_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "docs" / "note.md"
            path.parent.mkdir()
            path.write_text("line1\nline2\n", encoding="utf-8")
            result = cab.run(root, [("docs/note.md", 2)])
            self.assertEqual(0, result)

    def test_run_returns_one_over_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "docs" / "note.md"
            path.parent.mkdir()
            path.write_text("line1\nline2\nline3\n", encoding="utf-8")
            result = cab.run(root, [("docs/note.md", 2)])
            self.assertEqual(1, result)

    def test_run_returns_one_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = cab.run(root, [("missing.md", 100)])
            self.assertEqual(1, result)

    def test_run_multiple_budgets_accumulates_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "file.md"
            path.write_text("line\n", encoding="utf-8")
            result = cab.run(root, [("file.md", 1), ("missing.md", 100)])
            self.assertEqual(1, result)


class AttentionBudgetMainTests(unittest.TestCase):
    def test_main_with_custom_budget_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "docs" / "note.md"
            path.parent.mkdir()
            path.write_text("short\n", encoding="utf-8")
            result = cab.main(["--repo-root", str(root), "--budget", "docs/note.md=10"])
            self.assertEqual(0, result)

    def test_main_with_custom_budget_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "docs" / "note.md"
            path.parent.mkdir()
            path.write_text("line1\nline2\nline3\n", encoding="utf-8")
            result = cab.main(["--repo-root", str(root), "--budget", "docs/note.md=2"])
            self.assertEqual(1, result)

    def test_main_uses_default_budgets_when_none_specified(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result = cab.main(["--repo-root", str(repo_root)])
        self.assertIn(result, (0, 1))  # Either pass or fail, but must not crash
