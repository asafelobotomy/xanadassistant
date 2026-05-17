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
