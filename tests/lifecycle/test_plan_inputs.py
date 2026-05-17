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


class SeedAnswersFromInstallStateTests(unittest.TestCase):
    def test_non_repair_modes_do_not_seed_answers(self) -> None:
        questions = [{"id": "profile.selected", "options": ["balanced"]}]

        result = _plan_c.seed_answers_from_install_state(
            "setup",
            questions,
            {"profile": "balanced"},
            {},
        )

        self.assertEqual(result, {})

    def test_update_mode_seeds_only_known_answers_and_filters_invalid_packs(self) -> None:
        questions = [
            {"id": "profile.selected", "options": ["balanced", "lean"]},
            {"id": "packs.selected", "options": ["tdd", "docs"]},
            {"id": "response.style", "options": ["balanced", "verbose"]},
            {"id": "mcp.enabled", "options": [True, False]},
        ]

        result = _plan_c.seed_answers_from_install_state(
            "update",
            questions,
            {
                "profile": "balanced",
                "selectedPacks": ["tdd", "unknown-pack"],
                "setupAnswers": {"response.style": "verbose", "ignored": "value"},
                "mcpEnabled": True,
            },
            {},
        )

        self.assertEqual(
            result,
            {
                "profile.selected": "balanced",
                "packs.selected": ["tdd"],
                "response.style": "verbose",
                "mcp.enabled": True,
            },
        )

    def test_existing_answers_are_not_overwritten_when_seeding(self) -> None:
        questions = [
            {"id": "profile.selected", "options": ["balanced", "lean"]},
            {"id": "packs.selected", "options": ["tdd", "docs"]},
            {"id": "mcp.enabled", "options": [True, False]},
        ]

        result = _plan_c.seed_answers_from_install_state(
            "repair",
            questions,
            {
                "profile": "balanced",
                "selectedPacks": ["tdd"],
                "mcpEnabled": False,
            },
            {
                "profile.selected": "lean",
                "packs.selected": ["docs"],
                "mcp.enabled": True,
            },
        )

        self.assertEqual(result["profile.selected"], "lean")
        self.assertEqual(result["packs.selected"], ["docs"])
        self.assertTrue(result["mcp.enabled"])


class SeedAnswersFromProfileTests(unittest.TestCase):
    def test_selected_profile_seeds_defaults_and_default_packs(self) -> None:
        registry = {
            "profiles": [
                {
                    "id": "balanced",
                    "defaultPacks": ["tdd"],
                    "setupAnswerDefaults": {
                        "response.style": "balanced",
                        "autonomy.level": "ask-first",
                    },
                }
            ]
        }

        result = _plan_c.seed_answers_from_profile(
            registry,
            {"profile.selected": "balanced"},
            {"response.style", "autonomy.level"},
        )

        self.assertEqual(
            result,
            {
                "profile.selected": "balanced",
                "response.style": "balanced",
                "autonomy.level": "ask-first",
                "packs.selected": ["tdd"],
            },
        )

    def test_unknown_profile_or_filtered_question_ids_do_not_seed(self) -> None:
        registry = {
            "profiles": [
                {
                    "id": "balanced",
                    "defaultPacks": ["tdd"],
                    "setupAnswerDefaults": {"response.style": "balanced"},
                }
            ]
        }

        filtered = _plan_c.seed_answers_from_profile(
            registry,
            {"profile.selected": "balanced", "packs.selected": ["docs"]},
            {"autonomy.level"},
        )
        unknown = _plan_c.seed_answers_from_profile(registry, {"profile.selected": "missing"})

        self.assertEqual(filtered, {"profile.selected": "balanced", "packs.selected": ["docs"]})
        self.assertEqual(unknown, {"profile.selected": "missing"})


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


class MigrationAndPackTokensTests(unittest.TestCase):
    def _lockfile_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": "0.1.0",
            "package": {"name": _migration.CURRENT_PACKAGE_NAME},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:ok"},
            "timestamps": {},
            "selectedPacks": [],
            "files": [],
        }
        payload.update(overrides)
        return payload

    def test_lockfile_migration_detects_missing_fields_and_preserves_previous_package_name(self) -> None:
        self.assertTrue(_migration._lockfile_needs_migration({"manifest": {}}))

        migrated = _migration.migrate_lockfile_shape(
            {
                "package": {"name": "copilot-instructions-template"},
                "manifest": {},
                "timestamps": None,
                "selectedPacks": "not-a-list",
                "files": None,
            }
        )

        self.assertEqual(migrated["package"]["name"], _migration.CURRENT_PACKAGE_NAME)
        self.assertEqual(migrated["unknownValues"]["migratedFromPackageName"], "copilot-instructions-template")
        self.assertEqual(migrated["manifest"]["hash"], "sha256:unknown")
        self.assertEqual(migrated["selectedPacks"], [])
        self.assertEqual(migrated["files"], [])

    def test_lockfile_migration_helper_branches_cover_non_dicts_and_existing_valid_shape(self) -> None:
        self.assertFalse(_migration._lockfile_needs_migration([]))
        self.assertTrue(_migration._lockfile_needs_migration(self._lockfile_payload(package=[])))
        self.assertTrue(_migration._lockfile_needs_migration(self._lockfile_payload(manifest={"schemaVersion": "0.1.0"})))
        self.assertFalse(_migration._lockfile_needs_migration(self._lockfile_payload()))

        migrated = _migration.migrate_lockfile_shape(
            self._lockfile_payload(
                timestamps={"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                selectedPacks=["docs"],
                files=[{"target": ".github/prompts/main.prompt.md"}],
                unknownValues={"keep": True},
                skippedManagedFiles=[".github/mcp/scripts/gitMcp.py"],
                resolvedTokenConflicts={"voice": "docs"},
            )
        )

        self.assertEqual(migrated["package"], {"name": _migration.CURRENT_PACKAGE_NAME})
        self.assertEqual(migrated["manifest"]["hash"], "sha256:ok")
        self.assertEqual(migrated["selectedPacks"], ["docs"])
        self.assertEqual(migrated["unknownValues"], {"keep": True})
        self.assertEqual(migrated["skippedManagedFiles"], [".github/mcp/scripts/gitMcp.py"])
        self.assertEqual(migrated["resolvedTokenConflicts"], {"voice": "docs"})

    def test_migrate_lockfile_shape_replaces_invalid_unknown_values_container(self) -> None:
        migrated = _migration.migrate_lockfile_shape(
            {
                "package": {"name": "copilot-instructions-template"},
                "manifest": {},
                "timestamps": {},
                "selectedPacks": [],
                "files": [],
                "unknownValues": [],
            }
        )

        self.assertEqual(migrated["unknownValues"]["migratedFromPackageName"], "copilot-instructions-template")

    def test_load_pack_tokens_skips_invalid_sources_and_honors_resolved_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "packs" / "core").mkdir(parents=True)
            (root / "packs" / "core" / "tokens.json").write_text(
                json.dumps({"VOICE": "base", "STYLE": "plain"}),
                encoding="utf-8",
            )
            (root / "packs" / "docs").mkdir(parents=True)
            (root / "packs" / "docs" / "tokens.json").write_text(
                json.dumps({"VOICE": "docs", "DOC_STYLE": "clear"}),
                encoding="utf-8",
            )
            (root / "packs" / "secure").mkdir(parents=True)
            (root / "packs" / "secure" / "tokens.json").write_text("{invalid", encoding="utf-8")

            result = _conditions.load_pack_tokens(
                root,
                ["docs", "secure"],
                {"VOICE": "docs"},
            )

        self.assertEqual(result["{{VOICE}}"], "docs")
        self.assertEqual(result["{{STYLE}}"], "plain")
        self.assertEqual(result["{{DOC_STYLE}}"], "clear")


class InterviewAnswerResolutionTests(unittest.TestCase):
    def _assert_load_answers_error(self, path: str | None) -> LifecycleCommandError:
        with self.assertRaises(LifecycleCommandError) as excinfo:
            _interview.load_answers(path)
        return excinfo.exception

    def _interview_context(self, policy: dict[str, object], metadata: dict[str, object]) -> dict[str, object]:
        return {
            "policy": policy,
            "metadata": metadata,
            "manifest": {"managedFiles": []},
            "lockfileState": {},
            "warnings": ["warn"],
            "installState": "installed",
            "metadataArtifacts": {"policy": {"loaded": True}},
        }

    def test_build_interview_questions_and_result_cover_setup_update_and_other_modes(self) -> None:
        policy = {
            "ownershipDefaults": {"agents": "local", "skills": "plugin-backed-copilot-format"},
            "canonicalSurfaces": ["mcp-config"],
        }
        metadata = {
            "profileRegistry": {"profiles": [{"id": "balanced", "status": "active"}, {"id": "old", "status": "retired"}]},
            "packRegistry": {"packs": [{"id": "tdd", "optional": True, "status": "active"}, {"id": "dead", "optional": True, "status": "retired"}]},
        }

        questions = _interview.build_interview_questions(policy, metadata, "setup")
        question_ids = {question["id"] for question in questions}
        self.assertIn("setup.depth", question_ids)
        self.assertIn("profile.selected", question_ids)
        self.assertIn("packs.selected", question_ids)
        self.assertIn("ownership.agents", question_ids)

        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._interview.collect_context",
            return_value=self._interview_context(policy, metadata),
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.scan_existing_copilot_files",
            return_value=[".github/copilot-instructions.md"],
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.scan_consumer_kept_updates",
            return_value=[".github/prompts/custom.prompt.md"],
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.build_source_summary",
            return_value={"kind": "package-root"},
        ):
            workspace = Path(tmpdir)
            package_root = Path(tmpdir)
            setup_payload = _interview.build_interview_result(workspace, package_root, "setup")
            update_payload = _interview.build_interview_result(workspace, package_root, "update")
            repair_payload = _interview.build_interview_result(workspace, package_root, "repair")

        self.assertEqual(setup_payload["result"]["existingFiles"], [".github/copilot-instructions.md"])
        self.assertEqual(update_payload["result"]["existingFiles"], [".github/prompts/custom.prompt.md"])
        self.assertEqual(repair_payload["result"]["existingFiles"], [])

    def test_build_error_payload(self) -> None:
        payload, exit_code = _interview.build_error_payload(
            "plan",
            Path("/workspace"),
            Path("/package"),
            "contract_input_failure",
            "broken",
            4,
            mode="setup",
            details={"field": "x"},
        )

        self.assertEqual(exit_code, 4)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["errors"][0]["details"], {"field": "x"})

    def test_load_answers_returns_empty_mapping_without_path(self) -> None:
        self.assertEqual(_interview.load_answers(None), {})

    def test_load_answers_rejects_invalid_missing_and_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_path = Path(tmpdir) / "invalid.json"
            missing_path = Path(tmpdir) / "missing.json"
            list_path = Path(tmpdir) / "answers.json"
            invalid_path.write_text("{bad", encoding="utf-8")
            list_path.write_text("[]", encoding="utf-8")

            for path in (str(invalid_path), str(missing_path), str(list_path)):
                with self.subTest(path=path):
                    error = self._assert_load_answers_error(path)
                    self.assertEqual(error.code, "contract_input_failure")

    def test_validate_answer_value_rejects_invalid_choice_multi_choice_and_confirm(self) -> None:
        cases = [
            ({"id": "profile.selected", "kind": "choice", "options": ["balanced"]}, "invalid"),
            (
                {
                    "id": "packs.selected",
                    "kind": "multi-choice",
                    "options": ["tdd"],
                    "maxSelections": 1,
                },
                ["tdd", "docs"],
            ),
            ({"id": "mcp.enabled", "kind": "confirm"}, "yes"),
        ]

        for question, value in cases:
            with self.subTest(question=question["id"], value=value):
                with self.assertRaises(LifecycleCommandError):
                    _interview.validate_answer_value(question, value)

    def test_resolve_question_answers_uses_defaults_recommended_and_reports_unknown_ids(self) -> None:
        questions = [
            {"id": "setup.depth", "kind": "choice", "options": ["simple"], "default": "simple"},
            {"id": "profile.selected", "kind": "choice", "options": ["balanced"], "recommended": "balanced"},
            {"id": "ownership.skills", "kind": "choice", "options": ["local"], "required": True},
        ]

        resolved, unresolved, unknown_ids = _interview.resolve_question_answers(
            questions,
            {"extra.answer": True},
        )

        self.assertEqual(resolved["setup.depth"], "simple")
        self.assertEqual(resolved["profile.selected"], "balanced")
        self.assertEqual(unresolved, ["ownership.skills"])
        self.assertEqual(unknown_ids, ["extra.answer"])


if __name__ == "__main__":
    unittest.main()