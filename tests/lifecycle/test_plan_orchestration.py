from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad._errors import LifecycleCommandError
from scripts.lifecycle._xanad._plan_b import build_plan_result


class PlanOrchestrationTests(unittest.TestCase):
    def _base_context(self) -> dict:
        return {
            "policy": {"canonicalSurfaces": [], "tokenRules": [], "retiredFilePolicy": {"archiveRoot": ".xanad/archive"}},
            "metadata": {"profileRegistry": {"profiles": []}},
            "manifest": {"managedFiles": [], "retiredFiles": []},
            "warnings": [],
            "installState": "installed",
            "installPaths": {"lockfile": ".github/xanadAssistant-lock.json"},
            "artifacts": {},
            "metadataArtifacts": {},
            "lockfileState": {"consumerResolutions": {}, "present": True, "malformed": False, "resolvedTokenConflicts": {}},
            "legacyVersionState": {"malformed": False},
            "successorMigrationTargets": [],
            "packageRoot": Path(tempfile.gettempdir()),
        }

    def test_update_requires_existing_install(self) -> None:
        context = self._base_context()
        context["installState"] = "not-installed"

        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context):
            with self.assertRaises(LifecycleCommandError) as excinfo:
                build_plan_result(Path("."), Path("."), "update", None, False)

        self.assertEqual(excinfo.exception.code, "inspection_failure")

    def test_unresolved_pack_conflicts_return_approval_required_payload(self) -> None:
        context = self._base_context()

        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_interview_questions",
            return_value=[{"id": "packs.selected", "kind": "multi-choice", "default": ["docs"]}],
        ), mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}), mock.patch(
            "scripts.lifecycle._xanad._plan_b.resolve_question_answers",
            return_value=({"packs.selected": ["docs", "secure"]}, [], []),
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.detect_pack_token_conflicts",
            return_value=[{"token": "voice", "questionId": "resolvedTokenConflicts.voice", "packs": ["docs", "secure"], "candidates": {"docs": "docs", "secure": "secure"}}],
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.collect_conflict_resolutions",
            return_value=({}, ["resolvedTokenConflicts.voice"]),
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_conflict_questions",
            return_value=[{"id": "resolvedTokenConflicts.voice", "kind": "choice"}],
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.determine_repair_reasons",
            return_value=["schema-migration-required"],
        ):
            result = build_plan_result(Path("."), Path("."), "repair", None, False)

        self.assertEqual(result["status"], "approval-required")
        self.assertTrue(result["result"]["approvalRequired"])
        self.assertEqual(result["result"]["conflictDetails"][0]["token"], "voice")
        self.assertFalse(result["result"]["questionsResolved"])

    def test_successful_plan_result_uses_real_action_building_and_reports_unknown_answers(self) -> None:
        context = self._base_context()

        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir) / "package"
            workspace = Path(tmpdir) / "workspace"
            package_root.mkdir()
            workspace.mkdir()
            (package_root / "template").mkdir(parents=True)
            (package_root / "template" / "main.prompt.md").write_text("prompt\n", encoding="utf-8")
            context.update(
                {
                    "packageRoot": package_root,
                    "policy": {"canonicalSurfaces": [], "tokenRules": [], "retiredFilePolicy": {"archiveRoot": ".xanad/archive"}, "ownershipDefaults": {}},
                    "metadata": {"profileRegistry": {"profiles": []}, "packRegistry": {"packs": []}},
                    "manifest": {
                        "managedFiles": [
                            {
                                "id": "prompts.main",
                                "surface": "prompts",
                                "target": ".github/prompts/main.prompt.md",
                                "source": "template/main.prompt.md",
                                "strategy": "replace",
                                "tokens": [],
                                "ownership": ["local"],
                                "hash": "sha256:source",
                            }
                        ],
                        "retiredFiles": [],
                    },
                    "lockfileState": {
                        "consumerResolutions": {},
                        "present": True,
                        "malformed": False,
                        "resolvedTokenConflicts": {},
                        "setupAnswers": {},
                        "mcpEnabled": False,
                        "selectedPacks": [],
                        "files": [],
                        "unknownValues": {},
                        "skippedManagedFiles": [],
                    },
                }
            )

            with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), mock.patch(
                "scripts.lifecycle._xanad._plan_b.load_answers",
                return_value={"unknown.answer": True},
            ), mock.patch(
                "scripts.lifecycle._xanad._plan_b.detect_pack_token_conflicts",
                return_value=[],
            ):
                result = build_plan_result(workspace, package_root, "setup", None, False, resolutions_path=None)

        self.assertEqual(result["status"], "approval-required")
        self.assertEqual(result["result"]["writes"]["add"], 1)
        self.assertEqual(result["result"]["actions"][0]["target"], ".github/prompts/main.prompt.md")
        self.assertIn("unknown_answer_ids_ignored", {warning["code"] for warning in result["warnings"]})


if __name__ == "__main__":
    unittest.main()