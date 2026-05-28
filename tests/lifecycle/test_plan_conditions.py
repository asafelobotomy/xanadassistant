from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _conditions
from scripts.lifecycle._xanad import _interview
from scripts.lifecycle._xanad import _migration
from scripts.lifecycle._xanad import _plan_c
from scripts.lifecycle._xanad._errors import LifecycleCommandError


class DetermineRepairReasonsTests(unittest.TestCase):
    def test_collects_all_repair_reasons_for_broken_install(self) -> None:
        context = {
            "installState": "installed",
            "legacyVersionState": {"malformed": True},
            "lockfileState": {
                "malformed": False,
                "needsMigration": True,
                "originalPackageName": "copilot-instructions-template",
                "data": {"package": {"name": "copilot-instructions-template"}},
            },
            "successorMigrationTargets": [".github/prompts/old.prompt.md"],
            "manifestWithStatus": {
                "managedFiles": [
                    {"target": ".github/prompts/foo.prompt.md", "status": "missing"}
                ]
            },
        }

        self.assertEqual(
            _plan_c.determine_repair_reasons(context),
            [
                "malformed-legacy-version",
                "schema-migration-required",
                "package-identity-migration-required",
                "successor-cleanup-required",
                "incomplete-install",
            ],
        )

    def test_skipped_missing_files_do_not_mark_incomplete_install(self) -> None:
        context = {
            "installState": "installed",
            "legacyVersionState": {"malformed": False},
            "lockfileState": {"malformed": False, "needsMigration": False, "data": {}},
            "successorMigrationTargets": [],
            "manifestWithStatus": {
                "managedFiles": [
                    {
                        "target": ".github/prompts/foo.prompt.md",
                        "status": "missing",
                        "skipReason": "mcp-disabled",
                    }
                ]
            },
        }

        self.assertEqual(_plan_c.determine_repair_reasons(context), [])


class ConditionsTests(unittest.TestCase):
    def test_parse_condition_literal_and_matching_supports_scalars_lists_and_booleans(self) -> None:
        self.assertTrue(_conditions.condition_matches("mcp.enabled=true", {"mcp.enabled": True}))
        self.assertTrue(
            _conditions.condition_matches(
                "packs.selected=tdd",
                {"packs.selected": ["docs", "tdd"]},
            )
        )
        self.assertFalse(_conditions.condition_matches("response.style=verbose", {"response.style": "balanced"}))
        self.assertTrue(_conditions.condition_matches("mcp.enabled", {"mcp.enabled": True}))

    def test_entry_required_for_plan_and_normalize_answers_handle_mcp_surfaces(self) -> None:
        entry = {"requiredWhen": ["mcp.enabled=true", "packs.selected=tdd"]}
        policy = {"canonicalSurfaces": ["hook-scripts", "mcp-config"]}

        required = _conditions.entry_required_for_plan(
            entry,
            {"mcp.enabled": True, "packs.selected": ["tdd"]},
        )
        normalized = _conditions.normalize_plan_answers(policy, {"mcp.enabled": False})

        self.assertTrue(required)
        self.assertIn("hooks.enabled", normalized)
        self.assertFalse(normalized["hooks.enabled"])

    def test_resolve_token_values_uses_scan_fallback_labels_and_pack_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "packs" / "core").mkdir(parents=True)
            (root / "packs" / "core" / "tokens.json").write_text(
                json.dumps({"BASE": "core"}),
                encoding="utf-8",
            )
            (root / "packs" / "docs").mkdir(parents=True)
            (root / "packs" / "docs" / "tokens.json").write_text(
                json.dumps({"BASE": "docs-override", "DOC_STYLE": "clear"}),
                encoding="utf-8",
            )
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "pyproject.toml").write_text("[tool.poetry]\nname='demo'\n", encoding="utf-8")

            result = _conditions.resolve_token_values(
                {
                    "tokenRules": [
                        {"token": "{{PRIMARY_LANGUAGE}}"},
                        {"token": "{{PACKAGE_MANAGER}}"},
                        {"token": "{{TEST_COMMAND}}"},
                        {"token": "{{WORKSPACE_NAME}}"},
                        {"token": "{{XANAD_PROFILE}}"},
                    ]
                },
                workspace,
                {
                    "profile.selected": "balanced",
                    "packs.selected": ["docs"],
                },
                package_root=root,
            )

        self.assertEqual(result["{{PRIMARY_LANGUAGE}}"], "Python")
        self.assertEqual(result["{{PACKAGE_MANAGER}}"], "Poetry")
        self.assertEqual(result["{{TEST_COMMAND}}"], "(not detected)")
        self.assertEqual(result["{{WORKSPACE_NAME}}"], "workspace")
        self.assertEqual(result["{{XANAD_PROFILE}}"], "balanced")
        self.assertEqual(result["{{BASE}}"], "docs-override")
        self.assertEqual(result["{{DOC_STYLE}}"], "clear")

    def test_condition_helpers_cover_string_required_when_and_rendering_fallbacks(self) -> None:
        entry = {"requiredWhen": "feature.enabled=true"}
        self.assertTrue(_conditions.entry_required_for_plan(entry, {"feature.enabled": True}))
        self.assertEqual(_conditions.parse_condition_literal(" False "), False)

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            token_values = _conditions.resolve_token_values(
                {
                    "canonicalSurfaces": [],
                    "tokenRules": [
                        {"token": "{{WORKSPACE_NAME}}"},
                        {"token": "{{RESPONSE_STYLE}}"},
                        {"token": "{{AUTONOMY_LEVEL}}"},
                        {"token": "{{AGENT_PERSONA}}"},
                        {"token": "{{TESTING_PHILOSOPHY}}"},
                    ],
                },
                workspace,
                {},
                package_root=None,
            )

        self.assertEqual(token_values["{{WORKSPACE_NAME}}"], workspace.name)
        self.assertEqual(token_values["{{RESPONSE_STYLE}}"], "(not configured)")
        rendered = _conditions.render_tokenized_text("Hello {{WORKSPACE_NAME}}", token_values)
        self.assertEqual(rendered, f"Hello {workspace.name}")

    def test_resolve_token_values_agent_max_requests_uses_answer_or_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            policy = {"canonicalSurfaces": [], "tokenRules": [{"token": "{{AGENT_MAX_REQUESTS}}"}]}

            # Answer provided
            result = _conditions.resolve_token_values(policy, workspace, {"settings.agent.maxRequests": "64"})
            self.assertEqual(result["{{AGENT_MAX_REQUESTS}}"], "64")

            # No answer → default 128
            result = _conditions.resolve_token_values(policy, workspace, {})
            self.assertEqual(result["{{AGENT_MAX_REQUESTS}}"], "128")

            # Non-digit answer → default 128
            result = _conditions.resolve_token_values(policy, workspace, {"settings.agent.maxRequests": "many"})
            self.assertEqual(result["{{AGENT_MAX_REQUESTS}}"], "128")

    def test_resolve_token_values_copilot_next_edit_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            policy = {"canonicalSurfaces": [], "tokenRules": [{"token": "{{COPILOT_NEXT_EDIT_SUGGESTIONS}}"}]}

            result = _conditions.resolve_token_values(policy, workspace, {"settings.copilot.nextEditSuggestions": "disabled"})
            self.assertEqual(result["{{COPILOT_NEXT_EDIT_SUGGESTIONS}}"], "disabled")

            result = _conditions.resolve_token_values(policy, workspace, {})
            self.assertEqual(result["{{COPILOT_NEXT_EDIT_SUGGESTIONS}}"], "enabled")

            result = _conditions.resolve_token_values(policy, workspace, {"settings.copilot.nextEditSuggestions": "bogus"})
            self.assertEqual(result["{{COPILOT_NEXT_EDIT_SUGGESTIONS}}"], "enabled")

    def test_resolve_token_values_editor_inline_suggest_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            policy = {"canonicalSurfaces": [], "tokenRules": [{"token": "{{EDITOR_INLINE_SUGGEST_ENABLED}}"}]}

            result = _conditions.resolve_token_values(policy, workspace, {"settings.editor.inlineSuggest.enabled": True})
            self.assertEqual(result["{{EDITOR_INLINE_SUGGEST_ENABLED}}"], "true")

            result = _conditions.resolve_token_values(policy, workspace, {"settings.editor.inlineSuggest.enabled": False})
            self.assertEqual(result["{{EDITOR_INLINE_SUGGEST_ENABLED}}"], "false")

            result = _conditions.resolve_token_values(policy, workspace, {})
            self.assertEqual(result["{{EDITOR_INLINE_SUGGEST_ENABLED}}"], "true")

    def test_resolve_token_values_editor_inline_suggest_toolbar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            policy = {"canonicalSurfaces": [], "tokenRules": [{"token": "{{EDITOR_INLINE_SUGGEST_TOOLBAR}}"}]}

            for valid in ("onHover", "always", "never"):
                result = _conditions.resolve_token_values(policy, workspace, {"settings.editor.inlineSuggest.toolbar": valid})
                self.assertEqual(result["{{EDITOR_INLINE_SUGGEST_TOOLBAR}}"], valid)

            result = _conditions.resolve_token_values(policy, workspace, {})
            self.assertEqual(result["{{EDITOR_INLINE_SUGGEST_TOOLBAR}}"], "onHover")

    def test_resolve_token_values_boolean_settings_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            for token, answer_key in (
                ("{{COPILOT_CODESEARCH_ENABLED}}", "settings.copilot.codesearch"),
                ("{{FILES_TRIM_TRAILING_WHITESPACE}}", "settings.files.trimTrailingWhitespace"),
                ("{{FILES_INSERT_FINAL_NEWLINE}}", "settings.files.insertFinalNewline"),
                ("{{FILES_TRIM_FINAL_NEWLINES}}", "settings.files.trimFinalNewlines"),
            ):
                policy = {"canonicalSurfaces": [], "tokenRules": [{"token": token}]}

                result = _conditions.resolve_token_values(policy, workspace, {answer_key: True})
                self.assertEqual(result[token], "true", f"{token} True -> 'true'")

                result = _conditions.resolve_token_values(policy, workspace, {answer_key: False})
                self.assertEqual(result[token], "false", f"{token} False -> 'false'")

                result = _conditions.resolve_token_values(policy, workspace, {})
                self.assertEqual(result[token], "true", f"{token} missing -> 'true' (default)")


if __name__ == "__main__":
    unittest.main()
