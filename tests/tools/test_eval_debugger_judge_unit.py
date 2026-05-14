"""Unit tests for _eval_debugger_judge.py — offline coverage of parse() and score()."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import _eval_debugger_judge as judge
import _eval_debugger_tasks as tasks


# ── parse() ──────────────────────────────────────────────────────────────────

class TestParse(unittest.TestCase):

    def test_returns_dict_with_required_keys(self) -> None:
        result = judge.parse("The root cause is a missing default.")
        for key in ("text", "word_count", "has_code_fence", "has_diagnosis_marker"):
            with self.subTest(key=key):
                self.assertIn(key, result)

    def test_word_count(self) -> None:
        result = judge.parse("one two three")
        self.assertEqual(3, result["word_count"])

    def test_has_code_fence_true(self) -> None:
        result = judge.parse("Use `dict.get()` instead:\n\n```python\nx = d.get('key', 0)\n```")
        self.assertTrue(result["has_code_fence"])

    def test_has_code_fence_false(self) -> None:
        result = judge.parse("Use dict.get() with a default value.")
        self.assertFalse(result["has_code_fence"])

    def test_diagnosis_marker_root_cause(self) -> None:
        result = judge.parse("The root cause is a KeyError raised when the key is absent.")
        self.assertTrue(result["has_diagnosis_marker"])

    def test_diagnosis_marker_fix_is(self) -> None:
        result = judge.parse("The fix is to use .get() with a default.")
        self.assertTrue(result["has_diagnosis_marker"])

    def test_diagnosis_marker_absent_in_generic_response(self) -> None:
        result = judge.parse("Sure, I can help you with that Python code.")
        self.assertFalse(result["has_diagnosis_marker"])

    def test_text_preserved_verbatim(self) -> None:
        text = "Use config.get('timeout', 5000) to avoid KeyError."
        result = judge.parse(text)
        self.assertEqual(text, result["text"])


# ── score() ──────────────────────────────────────────────────────────────────

class TestScore(unittest.TestCase):

    def _make_task(
        self,
        cause_keywords: list[str],
        fix_keywords: list[str],
        scope_creep_keywords: list[str],
    ) -> dict:
        return {
            "cause_keywords":        cause_keywords,
            "fix_keywords":          fix_keywords,
            "scope_creep_keywords":  scope_creep_keywords,
        }

    def _parsed(self, text: str) -> dict:
        return judge.parse(text)

    def test_perfect_response_scores_three(self) -> None:
        task = self._make_task(
            cause_keywords=["keyerror", "missing"],
            fix_keywords=[".get("],
            scope_creep_keywords=["math.pi", "compute_pi"],
        )
        parsed = self._parsed(
            "The root cause is a KeyError — the 'timeout' key is missing from the config dict. "
            "Use config.get('timeout', 5000) instead of direct access."
        )
        result = judge.score(parsed, task)
        self.assertTrue(result["cause_identified"])
        self.assertTrue(result["fix_prescribed"])
        self.assertTrue(result["focused"])
        self.assertEqual(3, result["score"])

    def test_scope_creep_reduces_score(self) -> None:
        task = self._make_task(
            cause_keywords=["keyerror"],
            fix_keywords=[".get("],
            scope_creep_keywords=["math.pi", "compute_pi"],
        )
        # Response drifts into the red herring
        parsed = self._parsed(
            "The KeyError is because 'timeout' is missing. Use config.get('timeout', 5000). "
            "Also, compute_pi could just use math.pi from the standard library."
        )
        result = judge.score(parsed, task)
        self.assertTrue(result["cause_identified"])
        self.assertTrue(result["fix_prescribed"])
        self.assertFalse(result["focused"])
        self.assertEqual(2, result["score"])

    def test_missing_cause_scores_two(self) -> None:
        task = self._make_task(
            cause_keywords=["keyerror"],
            fix_keywords=[".get("],
            scope_creep_keywords=["math.pi"],
        )
        parsed = self._parsed(
            "In get_timeout(), replace config['timeout'] with config.get('timeout', 5000)."
        )
        result = judge.score(parsed, task)
        self.assertFalse(result["cause_identified"])
        self.assertTrue(result["fix_prescribed"])
        self.assertTrue(result["focused"])
        self.assertEqual(2, result["score"])

    def test_missing_fix_scores_two(self) -> None:
        task = self._make_task(
            cause_keywords=["keyerror"],
            fix_keywords=[".get("],
            scope_creep_keywords=["math.pi"],
        )
        parsed = self._parsed(
            "The KeyError happens because 'timeout' is absent from the dict."
        )
        result = judge.score(parsed, task)
        self.assertTrue(result["cause_identified"])
        self.assertFalse(result["fix_prescribed"])
        self.assertTrue(result["focused"])
        self.assertEqual(2, result["score"])

    def test_all_missing_scores_zero(self) -> None:
        task = self._make_task(
            cause_keywords=["keyerror"],
            fix_keywords=[".get("],
            scope_creep_keywords=["math.pi"],
        )
        # Wrong scope + no cause + no fix
        parsed = self._parsed("Sure, I can look at this. Also, math.pi is more precise.")
        result = judge.score(parsed, task)
        self.assertFalse(result["cause_identified"])
        self.assertFalse(result["fix_prescribed"])
        self.assertFalse(result["focused"])
        self.assertEqual(0, result["score"])

    def test_cause_keyword_case_insensitive(self) -> None:
        task = self._make_task(
            cause_keywords=["keyerror"],
            fix_keywords=["irrelevant"],
            scope_creep_keywords=["irrelevant"],
        )
        parsed = self._parsed("A KeyError is raised because the key does not exist.")
        result = judge.score(parsed, task)
        self.assertTrue(result["cause_identified"])

    def test_fix_keyword_case_insensitive(self) -> None:
        task = self._make_task(
            cause_keywords=["irrelevant"],
            fix_keywords=[".get("],
            scope_creep_keywords=["irrelevant"],
        )
        parsed = self._parsed("The fix is config.GET('timeout', 5000).")
        result = judge.score(parsed, task)
        self.assertTrue(result["fix_prescribed"])

    def test_scope_creep_keyword_case_insensitive(self) -> None:
        task = self._make_task(
            cause_keywords=["irrelevant"],
            fix_keywords=["irrelevant"],
            scope_creep_keywords=["math.pi"],
        )
        parsed = self._parsed("You could also use MATH.PI for more precision.")
        result = judge.score(parsed, task)
        self.assertFalse(result["focused"])

    def test_any_cause_keyword_sufficient(self) -> None:
        task = self._make_task(
            cause_keywords=["absent", "missing", "not present"],
            fix_keywords=["irrelevant"],
            scope_creep_keywords=["irrelevant"],
        )
        parsed = self._parsed("The key is absent from the dict.")
        result = judge.score(parsed, task)
        self.assertTrue(result["cause_identified"])

    def test_none_attribute_task(self) -> None:
        task = self._make_task(
            cause_keywords=["none", "nonetype", "attributeerror"],
            fix_keywords=["is none", "if name"],
            scope_creep_keywords=["find_max", "max("],
        )
        parsed = self._parsed(
            "The AttributeError occurs because headers.get() returns None when the header "
            "is absent. Guard with: if name is not None: return name.strip().title()"
        )
        result = judge.score(parsed, task)
        self.assertEqual(3, result["score"])

    def test_none_attribute_task_with_scope_creep(self) -> None:
        task = self._make_task(
            cause_keywords=["none"],
            fix_keywords=["if name"],
            scope_creep_keywords=["find_max", "max("],
        )
        # cause ✓, fix ✓ (has "if name is not None"), focused ✗ (drifts into find_max)
        parsed = self._parsed(
            "The None attribute error is the bug; guard with if name is not None. "
            "Also, find_max could use max()."
        )
        result = judge.score(parsed, task)
        self.assertEqual(2, result["score"])  # focused=False reduces score

    def test_off_by_one_task(self) -> None:
        task = self._make_task(
            cause_keywords=["indexerror", "i + 1"],
            fix_keywords=["- 1", "zip"],
            scope_creep_keywords=["normalize_score", "todo"],
        )
        parsed = self._parsed(
            "The IndexError is caused by i + 1 exceeding the last valid index. "
            "Fix: range(len(values) - 1)."
        )
        result = judge.score(parsed, task)
        self.assertEqual(3, result["score"])

    def test_mock_patch_task(self) -> None:
        task = self._make_task(
            cause_keywords=["mutable", "default", "shared", "evaluated once"],
            fix_keywords=["tags=none", "none as default", "if tags is none"],
            scope_creep_keywords=["isinstance", "type(tag) ==", "use isinstance"],
        )
        parsed = self._parsed(
            "The root cause is that [] is a mutable default argument — Python evaluates it "
            "once at function definition, so all instances share the same list. "
            "Fix: use tags=None and assign self.tags = tags if tags is not None else []."
        )
        result = judge.score(parsed, task)
        self.assertEqual(3, result["score"])

    def test_mutable_default_with_isinstance_scope_creep(self) -> None:
        task = self._make_task(
            cause_keywords=["mutable", "default"],
            fix_keywords=["if tags is none"],
            scope_creep_keywords=["isinstance", "use isinstance"],
        )
        parsed = self._parsed(
            "The mutable default argument causes shared state. Fix: tags=None + if tags is None. "
            "Also, use isinstance(tag, str) instead of type(tag) == str in validate_tag."
        )
        result = judge.score(parsed, task)
        self.assertEqual(2, result["score"])  # focused=False reduces score

    def test_broad_except_task(self) -> None:
        task = self._make_task(
            cause_keywords=["broad", "pass", "except exception"],
            fix_keywords=["raise", "valueerror"],
            scope_creep_keywords=["wildcard", "import *", "star import"],
        )
        parsed = self._parsed(
            "The broad except Exception: pass in process_records silently swallows errors. "
            "Replace pass with raise or narrow to except ValueError: raise."
        )
        result = judge.score(parsed, task)
        self.assertEqual(3, result["score"])

    def test_broad_except_with_wildcard_scope_creep(self) -> None:
        task = self._make_task(
            cause_keywords=["pass", "swallow"],
            fix_keywords=["raise"],
            scope_creep_keywords=["wildcard", "import *", "star import"],
        )
        parsed = self._parsed(
            "The except Exception: pass swallows errors silently. Use raise. "
            "Also, using import * (wildcard import) is bad practice."
        )
        result = judge.score(parsed, task)
        self.assertEqual(2, result["score"])  # focused=False


# ── Task definitions sanity ───────────────────────────────────────────────────

class TestTaskDefinitions(unittest.TestCase):

    def test_all_tasks_have_required_keys(self) -> None:
        required = {"name", "user_request", "cause_keywords", "fix_keywords",
                    "scope_creep_keywords", "notes"}
        for task in tasks.DEBUGGER_TASKS:
            with self.subTest(task=task.get("name")):
                self.assertTrue(required.issubset(task.keys()))

    def test_unique_task_names(self) -> None:
        names = [t["name"] for t in tasks.DEBUGGER_TASKS]
        self.assertEqual(len(names), len(set(names)))

    def test_keyword_lists_are_non_empty(self) -> None:
        for task in tasks.DEBUGGER_TASKS:
            with self.subTest(task=task["name"]):
                self.assertTrue(len(task["cause_keywords"]) > 0)
                self.assertTrue(len(task["fix_keywords"]) > 0)
                self.assertTrue(len(task["scope_creep_keywords"]) > 0)

    def test_five_tasks_defined(self) -> None:
        self.assertEqual(5, len(tasks.DEBUGGER_TASKS))

    def test_user_request_contains_traceback_or_code(self) -> None:
        for task in tasks.DEBUGGER_TASKS:
            with self.subTest(task=task["name"]):
                has_code = "```" in task["user_request"] or "Traceback" in task["user_request"]
                self.assertTrue(has_code, "user_request should include code or traceback")

    def test_scope_creep_keywords_do_not_overlap_cause_fix(self) -> None:
        """Red-herring keywords should not accidentally match the buggy code."""
        for task in tasks.DEBUGGER_TASKS:
            with self.subTest(task=task["name"]):
                cause_set = {kw.lower() for kw in task["cause_keywords"]}
                fix_set   = {kw.lower() for kw in task["fix_keywords"]}
                creep_set = {kw.lower() for kw in task["scope_creep_keywords"]}
                self.assertTrue(
                    creep_set.isdisjoint(cause_set | fix_set),
                    f"scope_creep_keywords overlap with cause/fix keywords",
                )


if __name__ == "__main__":
    unittest.main()
