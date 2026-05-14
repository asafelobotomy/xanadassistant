"""Unit tests for _eval_judge.py — pure offline coverage of parse() and score()."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import _eval_judge as judge
import _eval_tasks as tasks


# ── parse() ──────────────────────────────────────────────────────────────────

class TestParse(unittest.TestCase):

    def test_well_formed_response(self) -> None:
        text = (
            "Tier: Simple\n"
            "Scope: Rename claculate_total in three files\n"
            "Approach: Direct implementation in default agent\n"
            "Blockers: none\n"
        )
        result = judge.parse(text)
        self.assertIsNotNone(result)
        self.assertEqual("Simple", result["tier"])
        self.assertEqual("none", result["blockers"])

    def test_case_insensitive_field_labels(self) -> None:
        text = (
            "tier: Compound\n"
            "scope: Migrate ORM layer\n"
            "approach: Planner → implementation\n"
            "blockers: none\n"
        )
        result = judge.parse(text)
        self.assertIsNotNone(result)
        self.assertEqual("Compound", result["tier"])

    def test_tier_is_capitalised(self) -> None:
        text = (
            "Tier: trivial\n"
            "Scope: Single typo fix\n"
            "Approach: Direct\n"
            "Blockers: none\n"
        )
        result = judge.parse(text)
        self.assertIsNotNone(result)
        self.assertEqual("Trivial", result["tier"])

    def test_response_wrapped_in_code_block(self) -> None:
        text = (
            "Here is my triage:\n\n"
            "```\n"
            "Tier: Blocked\n"
            "Scope: Unknown — request underspecified\n"
            "Approach: Andon cord\n"
            "Blockers: No indication of what to change or why\n"
            "```\n"
        )
        result = judge.parse(text)
        self.assertIsNotNone(result)
        self.assertEqual("Blocked", result["tier"])

    def test_missing_blockers_field_returns_none(self) -> None:
        text = (
            "Tier: Simple\n"
            "Scope: Small change\n"
            "Approach: Direct\n"
        )
        result = judge.parse(text)
        self.assertIsNone(result)

    def test_empty_string_returns_none(self) -> None:
        self.assertIsNone(judge.parse(""))

    def test_prose_without_format_returns_none(self) -> None:
        self.assertIsNone(judge.parse("This is a complex migration task."))

    def test_blockers_trailing_backtick_stripped(self) -> None:
        text = (
            "Tier: Blocked\n"
            "Scope: Drop production table\n"
            "Approach: Andon cord\n"
            "Blockers: Irreversible without confirmation`\n"
        )
        result = judge.parse(text)
        self.assertIsNotNone(result)
        self.assertFalse(result["blockers"].endswith("`"))

    def test_blockers_angle_bracket_none_stripped(self) -> None:
        """Model sometimes fills the template placeholder literally: <none>."""
        text = (
            "Tier: Compound\n"
            "Scope: Extract JWT logic to core/tokens.py\n"
            "Approach: Planner → Implementation\n"
            "Blockers: <none>\n"
        )
        result = judge.parse(text)
        self.assertIsNotNone(result)
        self.assertEqual("none", result["blockers"])

    def test_extra_text_before_format_is_ignored(self) -> None:
        text = (
            "Let me analyse this request carefully.\n\n"
            "Tier: Complex\n"
            "Scope: Full auth subsystem refactor\n"
            "Approach: Planner → specialist agents\n"
            "Blockers: none\n"
        )
        result = judge.parse(text)
        self.assertIsNotNone(result)
        self.assertEqual("Complex", result["tier"])


# ── score() ──────────────────────────────────────────────────────────────────

class TestScore(unittest.TestCase):

    def _simple_task(self) -> dict:
        return {
            "tier_acceptable": {"Simple", "Trivial"},
            "expect_blockers": False,
        }

    def _blocked_task(self) -> dict:
        return {
            "tier_acceptable": {"Blocked"},
            "expect_blockers": True,
        }

    def test_none_parsed_gives_zero_score(self) -> None:
        result = judge.score(None, self._simple_task())
        self.assertFalse(result["format_valid"])
        self.assertFalse(result["tier_correct"])
        self.assertFalse(result["blocker_correct"])
        self.assertEqual(0, result["score"])

    def test_perfect_simple_task_scores_three(self) -> None:
        parsed = {"tier": "Simple", "scope": "x", "approach": "y", "blockers": "none"}
        result = judge.score(parsed, self._simple_task())
        self.assertTrue(result["format_valid"])
        self.assertTrue(result["tier_correct"])
        self.assertTrue(result["blocker_correct"])
        self.assertEqual(3, result["score"])

    def test_wrong_tier_reduces_score(self) -> None:
        parsed = {"tier": "Complex", "scope": "x", "approach": "y", "blockers": "none"}
        result = judge.score(parsed, self._simple_task())
        self.assertTrue(result["format_valid"])
        self.assertFalse(result["tier_correct"])
        self.assertEqual(2, result["score"])

    def test_unexpected_blocker_reduces_score(self) -> None:
        parsed = {"tier": "Simple", "scope": "x", "approach": "y",
                  "blockers": "Missing details about the change"}
        result = judge.score(parsed, self._simple_task())
        self.assertTrue(result["tier_correct"])
        self.assertFalse(result["blocker_correct"])
        self.assertEqual(2, result["score"])

    def test_blocked_task_with_specific_blocker_scores_three(self) -> None:
        parsed = {"tier": "Blocked", "scope": "unknown",
                  "approach": "andon cord",
                  "blockers": "No indication of what to change or why"}
        result = judge.score(parsed, self._blocked_task())
        self.assertTrue(result["tier_correct"])
        self.assertTrue(result["blocker_correct"])
        self.assertEqual(3, result["score"])

    def test_blocked_task_with_none_blocker_penalised(self) -> None:
        parsed = {"tier": "Blocked", "scope": "x", "approach": "y", "blockers": "none"}
        result = judge.score(parsed, self._blocked_task())
        self.assertTrue(result["tier_correct"])
        self.assertFalse(result["blocker_correct"])
        self.assertEqual(2, result["score"])

    def test_tier_acceptable_set_is_stored_in_output(self) -> None:
        parsed = {"tier": "Simple", "scope": "x", "approach": "y", "blockers": "none"}
        result = judge.score(parsed, self._simple_task())
        self.assertIn("expected_tiers", result)
        self.assertEqual(sorted({"Simple", "Trivial"}), result["expected_tiers"])

    def test_na_is_treated_as_no_blocker(self) -> None:
        parsed = {"tier": "Simple", "scope": "x", "approach": "y", "blockers": "n/a"}
        result = judge.score(parsed, self._simple_task())
        self.assertTrue(result["blocker_correct"])


# ── Task definitions sanity ───────────────────────────────────────────────────

class TestTaskDefinitions(unittest.TestCase):

    def test_all_tasks_have_required_keys(self) -> None:
        required = {"name", "user_request", "tier_acceptable", "expect_blockers", "notes"}
        for task in tasks.TRIAGE_TASKS:
            with self.subTest(task=task.get("name")):
                self.assertTrue(required.issubset(task.keys()))

    def test_tier_acceptable_is_non_empty_set(self) -> None:
        for task in tasks.TRIAGE_TASKS:
            with self.subTest(task=task["name"]):
                self.assertIsInstance(task["tier_acceptable"], set)
                self.assertGreater(len(task["tier_acceptable"]), 0)

    def test_unique_task_names(self) -> None:
        names = [t["name"] for t in tasks.TRIAGE_TASKS]
        self.assertEqual(len(names), len(set(names)))

    def test_at_least_one_blocked_task(self) -> None:
        blocked = [t for t in tasks.TRIAGE_TASKS if t["expect_blockers"]]
        self.assertGreater(len(blocked), 0)

    def test_at_least_one_non_blocked_task(self) -> None:
        non_blocked = [t for t in tasks.TRIAGE_TASKS if not t["expect_blockers"]]
        self.assertGreater(len(non_blocked), 0)


if __name__ == "__main__":
    unittest.main()
