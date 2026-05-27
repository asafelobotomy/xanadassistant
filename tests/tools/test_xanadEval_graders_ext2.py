"""Unit tests for new extended grader types: script, human, skill_invocation, and max_calls.

Tests _grade_script, _grade_human, _grade_skill_invocation, and the max_calls
addition to _grade_tool_constraint; all dispatched through _run_graders.
Imported via the xanadEval facade.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from xanadEval_test_support import xe

_grade_script = xe._grade_script
_grade_human = xe._grade_human
_grade_skill_invocation = xe._grade_skill_invocation
_grade_tool_constraint = xe._grade_tool_constraint
_run_graders = xe._run_graders


# ── ScriptGraderTests ─────────────────────────────────────────────────────────


class ScriptGraderTests(unittest.TestCase):
    """Tests for _grade_script (JSON context in/out subprocess)."""

    def _python_cmd(self, code: str) -> list[str]:
        return [sys.executable, "-c", code]

    def test_missing_command_fails(self) -> None:
        passed, score, feedback = _grade_script({})
        self.assertFalse(passed)
        self.assertIn("command", feedback)

    def test_nonexistent_command_fails_gracefully(self) -> None:
        passed, score, feedback = _grade_script({"command": "__no_such_exe_xyz__"})
        self.assertFalse(passed)
        self.assertIn("not found", feedback)

    def test_exit_0_passes_when_no_json(self) -> None:
        passed, score, feedback = _grade_script(
            {"command": sys.executable, "args": ["-c", "import sys; sys.exit(0)"]}
        )
        self.assertTrue(passed)
        self.assertEqual(score, 1.0)

    def test_exit_nonzero_fails(self) -> None:
        passed, score, _ = _grade_script(
            {"command": sys.executable, "args": ["-c", "import sys; sys.exit(1)"]}
        )
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)

    def test_json_stdout_score_used(self) -> None:
        script = 'import sys, json; sys.stdout.write(json.dumps({"score": 0.8, "passed": True, "message": "ok"}))'
        passed, score, msg = _grade_script(
            {"command": sys.executable, "args": ["-c", script]}
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 0.8)
        self.assertEqual(msg, "ok")

    def test_json_score_0_fails(self) -> None:
        script = 'import sys, json; sys.stdout.write(json.dumps({"score": 0.0, "passed": False}))'
        passed, score, _ = _grade_script(
            {"command": sys.executable, "args": ["-c", script]}
        )
        self.assertFalse(passed)
        self.assertAlmostEqual(score, 0.0)

    def test_ctx_serialised_to_stdin(self) -> None:
        """Script receives ctx payload as JSON via stdin."""
        script = (
            "import sys, json; d=json.loads(sys.stdin.read()); "
            "sys.stdout.write(json.dumps({'score': 1.0 if d.get('tool_calls') else 0.0, 'passed': True}))"
        )
        passed, score, _ = _grade_script(
            {"command": sys.executable, "args": ["-c", script]},
            ctx={"tool_calls": ["read_file"]},
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 1.0)

    def test_timeout_respected(self) -> None:
        passed, score, feedback = _grade_script(
            {"command": sys.executable, "args": ["-c", "import time; time.sleep(60)"],
             "timeout": 1}
        )
        self.assertFalse(passed)
        self.assertIn("timed out", feedback)

    def test_invalid_timeout_returns_grader_tuple(self) -> None:
        passed, score, feedback = _grade_script(
            {"command": sys.executable, "timeout": "bad"}
        )
        self.assertFalse(passed)
        self.assertIn("timeout", feedback)

    def test_response_included_in_stdin_payload(self) -> None:
        """Script stdin JSON contains the task response under 'response' key."""
        script = (
            "import sys, json; d=json.loads(sys.stdin.read()); "
            "sys.stdout.write(json.dumps({'score': 1.0 if d.get('response')=='EXPECTED' else 0.0, 'passed': True}))"
        )
        passed, score, _ = _grade_script(
            {"command": sys.executable, "args": ["-c", script]},
            response="EXPECTED",
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 1.0)

    def test_run_graders_dispatches_script(self) -> None:
        graders = [{"type": "script", "name": "s",
                    "config": {"command": sys.executable,
                               "args": ["-c", "import sys; sys.exit(0)"]}}]
        results = _run_graders("any", graders, "gpt-4o-mini", "")
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["pass"])


# ── HumanGraderTests ──────────────────────────────────────────────────────────


class HumanGraderTests(unittest.TestCase):
    """Tests for _grade_human (pending marker for human review)."""

    def test_always_returns_none_pass_score(self) -> None:
        passed, score, details = _grade_human({"criteria": ["Is it clear?"]})
        self.assertIsNone(passed)
        self.assertIsNone(score)

    def test_criteria_in_payload(self) -> None:
        _, _, details = _grade_human({"criteria": ["Is it clear?", "Is it concise?"]})
        self.assertEqual(details["criteria"], ["Is it clear?", "Is it concise?"])
        self.assertTrue(details["pending"])

    def test_instructions_included_when_present(self) -> None:
        _, _, details = _grade_human({"criteria": [], "instructions": "Check formatting."})
        self.assertEqual(details["instructions"], "Check formatting.")

    def test_empty_criteria_allowed(self) -> None:
        _, _, details = _grade_human({})
        self.assertEqual(details["criteria"], [])
        self.assertTrue(details["pending"])

    def test_run_graders_human_sets_pending(self) -> None:
        graders = [{"type": "human", "name": "review",
                    "config": {"criteria": ["Good?"]}}]
        results = _run_graders("any", graders, "gpt-4o-mini", "")
        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0]["pass"])
        self.assertTrue(results[0]["pending"])
        self.assertEqual(results[0]["criteria"], ["Good?"])


# ── SkillInvocationGraderTests ────────────────────────────────────────────────


class SkillInvocationGraderTests(unittest.TestCase):
    """Tests for _grade_skill_invocation."""

    def test_missing_config_fails(self) -> None:
        passed, score, feedback = _grade_skill_invocation({})
        self.assertFalse(passed)
        self.assertIn("required", feedback)

    def test_required_skill_present_passes(self) -> None:
        passed, score, _ = _grade_skill_invocation(
            {"required_skills": ["ciPreflight"]},
            ctx={"skill_invocations": ["ciPreflight"]},
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 1.0)

    def test_required_skill_absent_fails(self) -> None:
        passed, score, _ = _grade_skill_invocation(
            {"required_skills": ["ciPreflight"]},
            ctx={"skill_invocations": []},
        )
        self.assertFalse(passed)
        self.assertAlmostEqual(score, 0.0)

    def test_forbidden_skill_hard_fails(self) -> None:
        passed, score, feedback = _grade_skill_invocation(
            {"forbidden_skills": ["dangerSkill"]},
            ctx={"skill_invocations": ["dangerSkill"]},
        )
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)
        self.assertIn("forbidden", feedback)

    def test_only_forbidden_no_violation_passes(self) -> None:
        passed, score, _ = _grade_skill_invocation(
            {"forbidden_skills": ["dangerSkill"]},
            ctx={"skill_invocations": ["safeSkill"]},
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 1.0)

    def test_any_order_mode_partial_f1(self) -> None:
        _, score, _ = _grade_skill_invocation(
            {"required_skills": ["A", "B", "C"], "mode": "any_order"},
            ctx={"skill_invocations": ["A", "B"]},
        )
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_in_order_mode_respects_sequence(self) -> None:
        passed_correct, _, _ = _grade_skill_invocation(
            {"required_skills": ["A", "B"], "mode": "in_order"},
            ctx={"skill_invocations": ["A", "B"]},
        )
        passed_wrong, _, _ = _grade_skill_invocation(
            {"required_skills": ["A", "B"], "mode": "in_order"},
            ctx={"skill_invocations": ["B", "A"]},
        )
        self.assertTrue(passed_correct)
        self.assertFalse(passed_wrong)

    def test_allow_extra_false_penalises_extras(self) -> None:
        passed_strict, score_strict, _ = _grade_skill_invocation(
            {"required_skills": ["A"], "allow_extra": False},
            ctx={"skill_invocations": ["A", "B", "C"]},
        )
        _, score_loose, _ = _grade_skill_invocation(
            {"required_skills": ["A"], "allow_extra": True},
            ctx={"skill_invocations": ["A", "B", "C"]},
        )
        self.assertFalse(passed_strict)
        self.assertLess(score_strict, score_loose)

    def test_unknown_mode_fails(self) -> None:
        passed, score, feedback = _grade_skill_invocation(
            {"required_skills": ["A"], "mode": "bogus"},
            ctx={},
        )
        self.assertFalse(passed)
        self.assertIn("mode", feedback)

    def test_run_graders_dispatches_skill_invocation(self) -> None:
        graders = [{"type": "skill_invocation", "name": "si",
                    "config": {"required_skills": ["ciPreflight"]}}]
        results = _run_graders("any", graders, "gpt-4o-mini", "",
                               ctx={"skill_invocations": ["ciPreflight"]})
        self.assertTrue(results[0]["pass"])


# ── MaxCallsTests ─────────────────────────────────────────────────────────────


class MaxCallsTests(unittest.TestCase):
    """Tests for the max_calls addition to _grade_tool_constraint."""

    def test_max_calls_within_limit_passes(self) -> None:
        passed, score, _ = _grade_tool_constraint(
            {"max_calls": 5},
            ctx={"tool_calls": ["a", "b", "c"]},
        )
        self.assertTrue(passed)
        self.assertAlmostEqual(score, 1.0)

    def test_max_calls_exceeded_fails(self) -> None:
        passed, score, _ = _grade_tool_constraint(
            {"max_calls": 2},
            ctx={"tool_calls": ["a", "b", "c"]},
        )
        self.assertFalse(passed)
        self.assertLess(score, 1.0)

    def test_max_calls_combined_with_expect(self) -> None:
        passed, _, _ = _grade_tool_constraint(
            {"expect_tools": [{"tool": "read_file"}], "max_calls": 3},
            ctx={"tool_calls": [{"tool": "read_file"}, {"tool": "write_file"}]},
        )
        self.assertTrue(passed)

    def test_empty_config_still_fails(self) -> None:
        passed, score, feedback = _grade_tool_constraint({})
        self.assertFalse(passed)
        self.assertIn("required", feedback)

    def test_run_graders_dispatches_max_calls(self) -> None:
        graders = [{"type": "tool_constraint", "name": "tc",
                    "config": {"max_calls": 1}}]
        results = _run_graders("any", graders, "gpt-4o-mini", "",
                               ctx={"tool_calls": ["only_one"]})
        self.assertTrue(results[0]["pass"])


if __name__ == "__main__":
    unittest.main()
