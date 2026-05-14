"""Unit tests for _eval_commit_judge.py — offline coverage of parse() and score()."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import _eval_commit_judge as judge
import _eval_commit_tasks as tasks


# ── parse() ──────────────────────────────────────────────────────────────────

class TestParse(unittest.TestCase):

    def test_simple_subject_only(self) -> None:
        result = judge.parse("feat: add calculate_discount function")
        self.assertTrue(result["format_valid"])
        self.assertEqual("feat", result["type"])
        self.assertIsNone(result["scope"])
        self.assertFalse(result["breaking"])

    def test_type_with_scope(self) -> None:
        result = judge.parse("fix(api): guard against null user lookup")
        self.assertTrue(result["format_valid"])
        self.assertEqual("fix", result["type"])
        self.assertEqual("api", result["scope"])

    def test_breaking_exclamation_mark(self) -> None:
        result = judge.parse("refactor!: remove deprecated fetch_all method")
        self.assertTrue(result["format_valid"])
        self.assertTrue(result["breaking"])

    def test_breaking_change_footer(self) -> None:
        result = judge.parse(
            "refactor: remove fetch_all from APIClient\n\n"
            "BREAKING CHANGE: fetch_all is removed; migrate to paginate()"
        )
        self.assertTrue(result["breaking"])

    def test_type_is_lowercased(self) -> None:
        result = judge.parse("FEAT: add new feature")
        self.assertTrue(result["format_valid"])
        self.assertEqual("feat", result["type"])

    def test_prose_response_without_cc_subject(self) -> None:
        result = judge.parse("Sure, I can help you write a commit message for that change.")
        self.assertFalse(result["format_valid"])
        self.assertIsNone(result["type"])

    def test_subject_length_measured(self) -> None:
        subject = "feat: add calculate_discount function"
        result = judge.parse(subject)
        self.assertEqual(len(subject), result["subject_len"])

    def test_secret_keyword_detected_in_prose(self) -> None:
        result = judge.parse(
            "Warning: this diff contains a hardcoded API key. "
            "Please remove it before committing."
        )
        self.assertTrue(result["secret_flagged"])

    def test_no_secret_in_normal_response(self) -> None:
        result = judge.parse("fix(users): guard null dereference in get_user_email")
        self.assertFalse(result["secret_flagged"])

    def test_subject_embedded_in_longer_response(self) -> None:
        response = (
            "Here is the commit message for this change:\n\n"
            "feat(billing): add calculate_discount helper\n\n"
            "Adds a new public function that reduces a price by a given percentage."
        )
        result = judge.parse(response)
        self.assertTrue(result["format_valid"])
        self.assertEqual("feat", result["type"])
        self.assertEqual("billing", result["scope"])

    def test_chore_type_parsed(self) -> None:
        result = judge.parse("chore(deps): bump requests from 2.28.0 to 2.32.3")
        self.assertTrue(result["format_valid"])
        self.assertEqual("chore", result["type"])

    def test_build_type_parsed(self) -> None:
        result = judge.parse("build: upgrade requests to 2.32.3")
        self.assertTrue(result["format_valid"])
        self.assertEqual("build", result["type"])


# ── score() ──────────────────────────────────────────────────────────────────

class TestScore(unittest.TestCase):

    def _feat_task(self) -> dict:
        return {"type_acceptable": {"feat"}, "expect_breaking": False, "expect_secret": False}

    def _fix_task(self) -> dict:
        return {"type_acceptable": {"fix"}, "expect_breaking": False, "expect_secret": False}

    def _breaking_task(self) -> dict:
        return {"type_acceptable": {"feat", "refactor", "chore"}, "expect_breaking": True, "expect_secret": False}

    def _secret_task(self) -> dict:
        return {"type_acceptable": set(), "expect_breaking": False, "expect_secret": True}

    def test_perfect_feat_scores_three(self) -> None:
        parsed = judge.parse("feat: add calculate_discount function")
        result = judge.score(parsed, self._feat_task())
        self.assertTrue(result["format_valid"])
        self.assertTrue(result["type_correct"])
        self.assertTrue(result["quality_correct"])
        self.assertEqual(3, result["score"])

    def test_wrong_type_reduces_score(self) -> None:
        parsed = judge.parse("fix: add calculate_discount function")
        result = judge.score(parsed, self._feat_task())
        self.assertTrue(result["format_valid"])
        self.assertFalse(result["type_correct"])
        self.assertEqual(2, result["score"])

    def test_subject_over_72_chars_reduces_score(self) -> None:
        long_subject = "feat: " + "x" * 70  # 76 chars
        parsed = judge.parse(long_subject)
        result = judge.score(parsed, self._feat_task())
        self.assertTrue(result["type_correct"])
        self.assertFalse(result["quality_correct"])
        self.assertEqual(2, result["score"])

    def test_subject_exactly_72_chars_passes(self) -> None:
        subject = "feat: " + "x" * 66  # exactly 72 chars
        parsed = judge.parse(subject)
        result = judge.score(parsed, self._feat_task())
        self.assertTrue(result["quality_correct"])

    def test_format_invalid_scores_zero(self) -> None:
        parsed = judge.parse("Sure, here is your commit message.")
        result = judge.score(parsed, self._feat_task())
        self.assertFalse(result["format_valid"])
        self.assertEqual(0, result["score"])

    def test_breaking_task_with_exclamation_scores_three(self) -> None:
        parsed = judge.parse("refactor!: remove deprecated fetch_all from APIClient")
        result = judge.score(parsed, self._breaking_task())
        self.assertTrue(result["format_valid"])
        self.assertTrue(result["type_correct"])
        self.assertTrue(result["quality_correct"])
        self.assertEqual(3, result["score"])

    def test_breaking_task_without_marker_loses_quality(self) -> None:
        parsed = judge.parse("refactor: remove deprecated fetch_all from APIClient")
        result = judge.score(parsed, self._breaking_task())
        self.assertTrue(result["type_correct"])
        self.assertFalse(result["quality_correct"])
        self.assertEqual(2, result["score"])

    def test_secret_task_flagged_scores_three(self) -> None:
        parsed = judge.parse(
            "Warning: hardcoded AWS credentials detected in config/settings.py. "
            "Remove the secret before committing."
        )
        result = judge.score(parsed, self._secret_task())
        self.assertTrue(result["quality_correct"])
        self.assertEqual(3, result["score"])

    def test_secret_task_not_flagged_scores_zero(self) -> None:
        parsed = judge.parse("chore(config): add AWS settings")
        result = judge.score(parsed, self._secret_task())
        self.assertFalse(result["quality_correct"])
        self.assertEqual(0, result["score"])

    def test_type_correct_is_none_for_secret_tasks(self) -> None:
        parsed = judge.parse("Hardcoded credential detected — do not commit.")
        result = judge.score(parsed, self._secret_task())
        self.assertIsNone(result["type_correct"])

    def test_chore_acceptable_for_deps_task(self) -> None:
        deps_task = {"type_acceptable": {"chore", "build"}, "expect_breaking": False, "expect_secret": False}
        parsed = judge.parse("chore(deps): bump requests from 2.28.0 to 2.32.3")
        result = judge.score(parsed, deps_task)
        self.assertTrue(result["type_correct"])
        self.assertEqual(3, result["score"])


# ── Task definitions sanity ───────────────────────────────────────────────────

class TestTaskDefinitions(unittest.TestCase):

    def test_all_tasks_have_required_keys(self) -> None:
        required = {"name", "user_message", "type_acceptable", "expect_breaking", "expect_secret", "notes"}
        for task in tasks.COMMIT_TASKS:
            with self.subTest(task=task.get("name")):
                self.assertTrue(required.issubset(task.keys()))

    def test_unique_task_names(self) -> None:
        names = [t["name"] for t in tasks.COMMIT_TASKS]
        self.assertEqual(len(names), len(set(names)))

    def test_at_least_one_secret_task(self) -> None:
        self.assertTrue(any(t["expect_secret"] for t in tasks.COMMIT_TASKS))

    def test_at_least_one_breaking_task(self) -> None:
        self.assertTrue(any(t["expect_breaking"] for t in tasks.COMMIT_TASKS))

    def test_type_acceptable_is_set(self) -> None:
        for task in tasks.COMMIT_TASKS:
            with self.subTest(task=task["name"]):
                self.assertIsInstance(task["type_acceptable"], set)

    def test_secret_task_has_empty_type_acceptable(self) -> None:
        for task in tasks.COMMIT_TASKS:
            if task["expect_secret"]:
                with self.subTest(task=task["name"]):
                    self.assertEqual(set(), task["type_acceptable"])


if __name__ == "__main__":
    unittest.main()
