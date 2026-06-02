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
            "metadata": {"profileRegistry": {"profiles": []}, "agentRegistry": {"agents": []}},
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
            "scripts.lifecycle._xanad._interview.prepare_questions",
            return_value=([{"id": "packs.selected", "kind": "multi-choice", "default": ["docs"]}], {"packs.selected": ["docs", "secure"]}, [], []),
        ), mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}), mock.patch(
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
        self.assertEqual(result["result"]["agentCustomization"], {"availableAgents": [], "installedAgents": []})
        self.assertIn("unknown_answer_ids_ignored", {warning["code"] for warning in result["warnings"]})

    def test_plan_derives_installed_configurable_agents_and_validates_registry_linkage(self) -> None:
        context = self._base_context()
        context["metadata"] = {
            "profileRegistry": {"profiles": []},
            "agentRegistry": {
                "agents": [
                    {
                        "id": "review",
                        "name": "Review",
                        "status": "active",
                        "manifestEntryId": "agents.review.agent.md",
                        "customization": {"requiresInstalled": True, "tokenNamespace": "agent:review"},
                    }
                ]
            },
        }
        context["manifest"] = {
            "managedFiles": [
                {
                    "id": "agents.review.agent.md",
                    "surface": "agents",
                    "target": ".github/agents/review.agent.md",
                    "ownership": ["local", "plugin-backed-copilot-format"],
                    "requiredWhen": [],
                }
            ],
            "retiredFiles": [],
        }

        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), mock.patch(
            "scripts.lifecycle._xanad._interview.prepare_questions",
            return_value=([], {}, [], []),
        ), mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}), mock.patch(
            "scripts.lifecycle._xanad._plan_b.detect_pack_token_conflicts", return_value=[]), mock.patch(
            "scripts.lifecycle._xanad._plan_b.resolve_ownership_by_surface",
            return_value={},
        ), mock.patch("scripts.lifecycle._xanad._plan_b.resolve_token_values", return_value={}), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_setup_plan_actions",
            return_value=({"add": 0, "replace": 0, "merge": 0, "archiveRetired": 0, "deleted": 0}, [], [], []),
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.classify_plan_conflicts",
            return_value=([], []),
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_token_plan_summary",
            return_value=[],
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_backup_plan",
            return_value={"root": None, "targets": [], "archiveTargets": []},
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_planned_lockfile",
            return_value={},
        ):
            result = build_plan_result(Path("."), Path("."), "setup", None, False)

        self.assertEqual(result["result"]["agentCustomization"]["availableAgents"][0]["id"], "review")
        self.assertEqual(result["result"]["agentCustomization"]["installedAgents"][0]["id"], "review")

        context["policy"] = {"canonicalSurfaces": [], "tokenRules": [], "retiredFilePolicy": {"archiveRoot": ".xanad/archive"}, "ownershipDefaults": {"agents": "plugin-backed-copilot-format"}}
        context["lockfileState"]["ownershipBySurface"] = {"agents": "plugin-backed-copilot-format"}
        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), mock.patch(
            "scripts.lifecycle._xanad._interview.prepare_questions",
            return_value=([], {}, [], []),
        ), mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}), mock.patch(
            "scripts.lifecycle._xanad._plan_b.detect_pack_token_conflicts", return_value=[]), mock.patch(
            "scripts.lifecycle._xanad._plan_b.resolve_token_values", return_value={}), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_setup_plan_actions",
            return_value=({"add": 0, "replace": 0, "merge": 0, "archiveRetired": 0, "deleted": 0}, [], [], []),
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.classify_plan_conflicts",
            return_value=([], []),
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_token_plan_summary",
            return_value=[],
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_backup_plan",
            return_value={"root": None, "targets": [], "archiveTargets": []},
        ), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_planned_lockfile",
            return_value={},
        ):
            plugin_backed_result = build_plan_result(Path("."), Path("."), "setup", None, False)

        self.assertEqual(plugin_backed_result["result"]["agentCustomization"]["availableAgents"][0]["id"], "review")
        self.assertEqual(plugin_backed_result["result"]["agentCustomization"]["installedAgents"], [])

        context["metadata"]["agentRegistry"]["agents"][0]["manifestEntryId"] = "agents.missing.agent.md"
        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), mock.patch(
            "scripts.lifecycle._xanad._interview.prepare_questions",
            return_value=([], {}, [], []),
        ), mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}):
            with self.assertRaises(LifecycleCommandError) as excinfo:
                build_plan_result(Path("."), Path("."), "setup", None, False)

        self.assertEqual(excinfo.exception.code, "contract_input_failure")


class SanitizePlanOrchestrationTests(unittest.TestCase):
    def _base_context(self) -> dict:
        return {
            "policy": {"canonicalSurfaces": [], "tokenRules": [], "retiredFilePolicy": {"archiveRoot": ".xanad/archive"}},
            "metadata": {"profileRegistry": {"profiles": []}, "agentRegistry": {"agents": []}},
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

    def test_sanitize_false_produces_zero_archive_unmanaged_and_no_targets(self) -> None:
        context = self._base_context()
        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), mock.patch(
            "scripts.lifecycle._xanad._interview.prepare_questions", return_value=([], {}, [], [])
        ), mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}), mock.patch(
            "scripts.lifecycle._xanad._plan_b.classify_plan_conflicts", return_value=([], [])
        ), mock.patch("scripts.lifecycle._xanad._plan_b.build_token_plan_summary", return_value=[]), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_backup_plan",
            return_value={"root": None, "targets": [], "archiveTargets": []},
        ), mock.patch("scripts.lifecycle._xanad._plan_b.build_planned_lockfile", return_value={}):
            result = build_plan_result(Path("."), Path("."), "factory-restore", None, False, sanitize=False)

        self.assertEqual(result["result"]["writes"].get("archiveUnmanaged", 0), 0)
        sanitize_info = result["result"].get("sanitize", {})
        self.assertFalse(sanitize_info.get("enabled", True))
        self.assertEqual(sanitize_info.get("targets", []), [])

    def test_sanitize_true_includes_archive_unmanaged_actions_for_found_targets(self) -> None:
        context = self._base_context()
        fake_targets = [".github/stray.agent.md"]
        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), mock.patch(
            "scripts.lifecycle._xanad._interview.prepare_questions", return_value=([], {}, [], [])
        ), mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}), mock.patch(
            "scripts.lifecycle._xanad._plan_b.classify_plan_conflicts", return_value=([], [])
        ), mock.patch("scripts.lifecycle._xanad._plan_b.build_token_plan_summary", return_value=[]), mock.patch(
            "scripts.lifecycle._xanad._plan_b.build_backup_plan",
            return_value={"root": None, "targets": [], "archiveTargets": []},
        ), mock.patch("scripts.lifecycle._xanad._plan_b.build_planned_lockfile", return_value={}), mock.patch(
            "scripts.lifecycle._xanad._plan_b.collect_sanitizable_unmanaged_files",
            return_value=fake_targets,
        ):
            result = build_plan_result(Path("."), Path("."), "factory-restore", None, False, sanitize=True)

        sanitize_info = result["result"].get("sanitize", {})
        self.assertTrue(sanitize_info.get("enabled", False))
        self.assertEqual(sanitize_info.get("targets", []), fake_targets)
        self.assertEqual(result["result"]["writes"].get("archiveUnmanaged", 0), len(fake_targets))
        archive_actions = [a for a in result["result"].get("actions", []) if a.get("action") == "archive-unmanaged"]
        self.assertEqual(len(archive_actions), len(fake_targets))


if __name__ == "__main__":
    unittest.main()
