"""Unit tests for scripts/lifecycle/_xanad/_conditions.py — token resolution and rendering."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._conditions import (
    resolve_token_values,
    render_tokenized_text,
    condition_matches,
    entry_required_for_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

_MINIMAL_POLICY = {
    "tokenRules": [
        {"token": "{{PRIMARY_LANGUAGE}}", "required": False},
        {"token": "{{PACKAGE_MANAGER}}", "required": False},
        {"token": "{{TEST_COMMAND}}", "required": False},
        {"token": "{{WORKSPACE_NAME}}", "required": False},
        {"token": "{{RESPONSE_STYLE}}", "required": False},
        {"token": "{{AUTONOMY_LEVEL}}", "required": False},
        {"token": "{{AGENT_PERSONA}}", "required": False},
        {"token": "{{TESTING_PHILOSOPHY}}", "required": False},
    ]
}


class ResolveTokenValuesFallbackTests(unittest.TestCase):
    """Scan tokens that cannot be detected must get a fallback, not stay as raw {{...}}."""

    def test_empty_workspace_scan_tokens_get_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            token_values = resolve_token_values(_MINIMAL_POLICY, Path(tmp), {})
        self.assertEqual("(not detected)", token_values.get("{{PRIMARY_LANGUAGE}}"))
        self.assertEqual("(not detected)", token_values.get("{{PACKAGE_MANAGER}}"))
        self.assertEqual("(not detected)", token_values.get("{{TEST_COMMAND}}"))

    def test_detected_scan_tokens_are_not_overwritten_by_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "go.mod").write_text("module example.com/app\n", encoding="utf-8")
            token_values = resolve_token_values(_MINIMAL_POLICY, ws, {})
        self.assertEqual("Go", token_values.get("{{PRIMARY_LANGUAGE}}"))
        self.assertEqual("go modules", token_values.get("{{PACKAGE_MANAGER}}"))
        self.assertEqual("go test ./...", token_values.get("{{TEST_COMMAND}}"))

    def test_fallback_not_applied_when_scan_tokens_absent_from_policy(self) -> None:
        policy_no_scan = {"tokenRules": [{"token": "{{WORKSPACE_NAME}}", "required": False}]}
        with tempfile.TemporaryDirectory() as tmp:
            token_values = resolve_token_values(policy_no_scan, Path(tmp), {})
        self.assertNotIn("{{PRIMARY_LANGUAGE}}", token_values)
        self.assertNotIn("{{PACKAGE_MANAGER}}", token_values)
        self.assertNotIn("{{TEST_COMMAND}}", token_values)

    def test_workspace_name_token_resolves_to_directory_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            token_values = resolve_token_values(_MINIMAL_POLICY, ws, {})
        self.assertEqual(ws.name, token_values.get("{{WORKSPACE_NAME}}"))

    def test_answer_backed_tokens_resolve_from_resolved_answers(self) -> None:
        answers = {
            "response.style": "balanced",
            "autonomy.level": "ask-first",
            "agent.persona": "professional",
            "testing.philosophy": "always",
        }
        with tempfile.TemporaryDirectory() as tmp:
            token_values = resolve_token_values(_MINIMAL_POLICY, Path(tmp), answers)
        self.assertIn("Balanced", token_values.get("{{RESPONSE_STYLE}}", ""))
        self.assertIn("Ask first", token_values.get("{{AUTONOMY_LEVEL}}", ""))
        self.assertIn("Professional", token_values.get("{{AGENT_PERSONA}}", ""))
        self.assertIn("Always", token_values.get("{{TESTING_PHILOSOPHY}}", ""))


class RenderTokenizedTextTests(unittest.TestCase):
    def test_replaces_known_token(self) -> None:
        result = render_tokenized_text("Language: {{PRIMARY_LANGUAGE}}", {"{{PRIMARY_LANGUAGE}}": "Python"})
        self.assertEqual("Language: Python", result)

    def test_leaves_unknown_token_unchanged(self) -> None:
        result = render_tokenized_text("x: {{UNKNOWN}}", {"{{PRIMARY_LANGUAGE}}": "Python"})
        self.assertEqual("x: {{UNKNOWN}}", result)

    def test_replaces_multiple_tokens(self) -> None:
        result = render_tokenized_text(
            "{{PRIMARY_LANGUAGE}} / {{PACKAGE_MANAGER}}",
            {"{{PRIMARY_LANGUAGE}}": "Go", "{{PACKAGE_MANAGER}}": "go modules"},
        )
        self.assertEqual("Go / go modules", result)

    def test_fallback_values_produce_no_raw_placeholders(self) -> None:
        template = "Language: {{PRIMARY_LANGUAGE}} · PM: {{PACKAGE_MANAGER}} · Test: {{TEST_COMMAND}}"
        token_values = {
            "{{PRIMARY_LANGUAGE}}": "(not detected)",
            "{{PACKAGE_MANAGER}}": "(not detected)",
            "{{TEST_COMMAND}}": "(not detected)",
        }
        result = render_tokenized_text(template, token_values)
        self.assertNotIn("{{", result)
        self.assertNotIn("}}", result)


class ConditionMatchesTests(unittest.TestCase):
    def test_equality_condition_matches_exact_value(self) -> None:
        self.assertTrue(condition_matches("key=value", {"key": "value"}))

    def test_equality_condition_does_not_match_wrong_value(self) -> None:
        self.assertFalse(condition_matches("key=value", {"key": "other"}))

    def test_presence_condition_matches_truthy(self) -> None:
        self.assertTrue(condition_matches("key", {"key": True}))

    def test_presence_condition_does_not_match_missing(self) -> None:
        self.assertFalse(condition_matches("key", {}))

    def test_equality_condition_matches_within_list(self) -> None:
        self.assertTrue(condition_matches("key=a", {"key": ["a", "b"]}))

    def test_equality_condition_misses_outside_list(self) -> None:
        self.assertFalse(condition_matches("key=c", {"key": ["a", "b"]}))


class EntryRequiredForPlanTests(unittest.TestCase):
    def test_entry_with_no_conditions_is_always_required(self) -> None:
        entry = {"requiredWhen": []}
        self.assertTrue(entry_required_for_plan(entry, {}))

    def test_entry_required_when_all_conditions_match(self) -> None:
        entry = {"requiredWhen": ["a=1", "b=2"]}
        self.assertTrue(entry_required_for_plan(entry, {"a": "1", "b": "2"}))

    def test_entry_not_required_when_any_condition_fails(self) -> None:
        entry = {"requiredWhen": ["a=1", "b=2"]}
        self.assertFalse(entry_required_for_plan(entry, {"a": "1", "b": "3"}))

    def test_string_condition_is_normalized_to_list(self) -> None:
        entry = {"requiredWhen": "hooks.enabled"}
        self.assertTrue(entry_required_for_plan(entry, {"hooks.enabled": True}))
        self.assertFalse(entry_required_for_plan(entry, {}))
