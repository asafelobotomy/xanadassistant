from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _interview
from scripts.lifecycle._xanad._errors import LifecycleCommandError
from scripts.lifecycle._xanad._plan_b import build_plan_result


class ReinterviewCurrentValueAnnotationTests(unittest.TestCase):
    def _base_context(self, lockfile_state: dict | None = None) -> dict:
        policy = {
            "ownershipDefaults": {"agents": "local"},
            "canonicalSurfaces": [],
        }
        metadata = {
            "profileRegistry": {"profiles": [{"id": "balanced", "name": "Balanced", "summary": ".", "status": "active"}]},
            "packRegistry": {"packs": []},
            "agentRegistry": {"agents": []},
        }
        return {
            "policy": policy,
            "metadata": metadata,
            "manifest": {"managedFiles": []},
            "lockfileState": lockfile_state or {},
            "warnings": [],
            "installState": "installed",
            "metadataArtifacts": {},
        }

    def test_update_mode_annotates_current_values_from_lockfile_setup_answers(self) -> None:
        context = self._base_context({
            "setupAnswers": {
                "response.style": "verbose",
                "profile.selected": "balanced",
            }
        })

        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._interview.collect_context", return_value=context
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.scan_consumer_kept_updates", return_value=[]
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.build_source_summary", return_value={"kind": "package-root"}
        ):
            payload = _interview.build_interview_result(Path(tmpdir), Path(tmpdir), "update")

        questions_by_id = {q["id"]: q for q in payload["result"]["questions"]}
        self.assertEqual(questions_by_id["response.style"]["currentValue"], "verbose")
        self.assertEqual(questions_by_id["profile.selected"]["currentValue"], "balanced")
        self.assertNotIn("currentValue", questions_by_id.get("setup.depth", {}))

    def test_setup_mode_does_not_annotate_current_values(self) -> None:
        context = self._base_context({
            "setupAnswers": {"response.style": "verbose"}
        })

        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._interview.collect_context", return_value=context
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.scan_existing_copilot_files", return_value=[]
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.build_source_summary", return_value={"kind": "package-root"}
        ):
            payload = _interview.build_interview_result(Path(tmpdir), Path(tmpdir), "setup")

        for q in payload["result"]["questions"]:
            self.assertNotIn("currentValue", q, f"setup-mode question {q['id']} must not have currentValue")

    def test_update_mode_with_empty_setup_answers_returns_questions_without_current_values(self) -> None:
        context = self._base_context({"setupAnswers": {}})

        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._interview.collect_context", return_value=context
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.scan_consumer_kept_updates", return_value=[]
        ), mock.patch(
            "scripts.lifecycle._xanad._interview.build_source_summary", return_value={"kind": "package-root"}
        ):
            payload = _interview.build_interview_result(Path(tmpdir), Path(tmpdir), "update")

        for q in payload["result"]["questions"]:
            self.assertNotIn("currentValue", q)


class ReinterviewSafetyGateTests(unittest.TestCase):
    def _installed_context(self) -> dict:
        return {
            "policy": {"canonicalSurfaces": [], "tokenRules": [], "retiredFilePolicy": {"archiveRoot": ".xanad/archive"}},
            "metadata": {"profileRegistry": {"profiles": []}, "agentRegistry": {"agents": []}},
            "manifest": {"managedFiles": [], "retiredFiles": []},
            "warnings": [],
            "installState": "installed",
            "installPaths": {},
            "artifacts": {},
            "metadataArtifacts": {},
            "lockfileState": {
                "present": True,
                "malformed": False,
                "needsMigration": False,
                "consumerResolutions": {},
                "resolvedTokenConflicts": {},
            },
            "legacyVersionState": {"malformed": False},
            "successorMigrationTargets": [],
        }

    def test_update_with_answers_path_raises_for_malformed_lockfile(self) -> None:
        context = self._installed_context()
        context["lockfileState"]["malformed"] = True

        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), \
             mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}):
            with self.assertRaises(LifecycleCommandError) as excinfo:
                build_plan_result(Path("."), Path("."), "update", "/answers.json", False)

        self.assertEqual(excinfo.exception.code, "inspection_failure")
        self.assertEqual(excinfo.exception.details.get("reason"), "malformed-lockfile")

    def test_update_with_answers_path_raises_for_schema_migration_required(self) -> None:
        context = self._installed_context()
        context["lockfileState"]["needsMigration"] = True

        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), \
             mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}):
            with self.assertRaises(LifecycleCommandError) as excinfo:
                build_plan_result(Path("."), Path("."), "update", "/answers.json", False)

        self.assertEqual(excinfo.exception.code, "inspection_failure")
        self.assertEqual(excinfo.exception.details.get("reason"), "schema-migration-required")

    def test_update_with_answers_path_raises_for_successor_cleanup_required(self) -> None:
        context = self._installed_context()
        context["successorMigrationTargets"] = [".github/agents/old.agent.md"]

        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), \
             mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}):
            with self.assertRaises(LifecycleCommandError) as excinfo:
                build_plan_result(Path("."), Path("."), "update", "/answers.json", False)

        self.assertEqual(excinfo.exception.code, "inspection_failure")
        self.assertEqual(excinfo.exception.details.get("reason"), "successor-cleanup-required")

    def test_update_without_answers_path_skips_reinterview_gate(self) -> None:
        context = self._installed_context()
        context["lockfileState"]["malformed"] = True  # would block re-interview but not plain update

        with mock.patch("scripts.lifecycle._xanad._plan_b.collect_context", return_value=context), \
             mock.patch("scripts.lifecycle._xanad._plan_b.load_answers", return_value={}), \
             mock.patch("scripts.lifecycle._xanad._interview.prepare_questions", return_value=([], {}, [], [])), \
             mock.patch("scripts.lifecycle._xanad._plan_b.detect_pack_token_conflicts", return_value=[]), \
             mock.patch("scripts.lifecycle._xanad._plan_b.resolve_ownership_by_surface", return_value={}), \
             mock.patch("scripts.lifecycle._xanad._plan_b.resolve_token_values", return_value={}), \
             mock.patch("scripts.lifecycle._xanad._plan_b.build_setup_plan_actions",
                 return_value=({"add": 0, "replace": 0, "merge": 0, "archiveRetired": 0, "deleted": 0}, [], [], [])), \
             mock.patch("scripts.lifecycle._xanad._plan_b.classify_plan_conflicts", return_value=([], [])), \
             mock.patch("scripts.lifecycle._xanad._plan_b.build_token_plan_summary", return_value=[]), \
             mock.patch("scripts.lifecycle._xanad._plan_b.build_backup_plan",
                 return_value={"root": None, "targets": [], "archiveTargets": []}), \
             mock.patch("scripts.lifecycle._xanad._plan_b.build_planned_lockfile", return_value={}):
            result = build_plan_result(Path("."), Path("."), "update", None, False)

        self.assertIn(result["status"], {"ok", "approval-required"})


if __name__ == "__main__":
    unittest.main()
