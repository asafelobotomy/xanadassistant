from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class XanadAssistantPhase5Tests(XanadTestBase):
    def _make_copy_if_missing_entry(self, target: str) -> dict:
        return {
            "id": f"test-cim-{target.replace('/', '-')}",
            "surface": "prompts",
            "layer": "core",
            "source": f"template/{target}",
            "target": target,
            "ownership": ["local"],
            "strategy": "copy-if-missing",
            "requiredWhen": [],
            "tokens": [],
            "chmod": "none",
            "hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        }

    def _make_archive_retired_plan_payload(
        self,
        workspace: Path,
        retired_target: str,
        strategy: str = "archive-retired",
        archive_root: str | None = ".xanad-assistant/archive",
    ) -> dict:
        archive_targets = []
        if strategy != "report-retired" and archive_root is not None:
            archive_targets.append(
                {
                    "target": retired_target,
                    "archivePath": f"{archive_root}/{retired_target}",
                }
            )
        return {
            "result": {
                "actions": [
                    {
                        "id": "retired-test-entry",
                        "target": retired_target,
                        "action": "archive-retired",
                        "strategy": strategy,
                        "ownershipMode": None,
                    }
                ],
                "backupPlan": {
                    "required": True,
                    "root": ".xanad-assistant/backups/<apply-timestamp>",
                    "targets": [],
                    "archiveRoot": archive_root,
                    "archiveTargets": archive_targets,
                },
                "plannedLockfile": {
                    "path": ".github/xanad-assistant-lock.json",
                    "contents": self.make_minimal_lockfile(
                        timestamps={
                            "appliedAt": "<apply-timestamp>",
                            "updatedAt": "<apply-timestamp>",
                        },
                        skippedManagedFiles=[],
                        retiredManagedFiles=[],
                        unknownValues={},
                        lastBackup={"path": ".xanad-assistant/backups/<apply-timestamp>"},
                    ),
                },
                "skippedActions": [],
                "factoryRestore": False,
            }
        }

    def test_copy_if_missing_plan_skips_file_when_present(self) -> None:
        from scripts.lifecycle.xanad_assistant import build_setup_plan_actions

        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            target = ".github/prompts/custom.md"
            target_path = workspace / target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("existing content\n", encoding="utf-8")

            manifest = {"managedFiles": [self._make_copy_if_missing_entry(target)], "retiredFiles": []}
            writes, actions, skipped, retired = build_setup_plan_actions(
                workspace, repo_root, manifest, {"prompts": "local"}, {}, {}
            )

        self.assertEqual(0, writes["add"])
        self.assertEqual(0, len(actions))
        self.assertEqual(1, len(skipped))
        self.assertEqual("copy-if-missing-present", skipped[0]["reason"])
        self.assertEqual(target, skipped[0]["target"])

    def test_copy_if_missing_plan_adds_file_when_absent(self) -> None:
        from scripts.lifecycle.xanad_assistant import build_setup_plan_actions

        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            target = ".github/prompts/custom.md"

            manifest = {"managedFiles": [self._make_copy_if_missing_entry(target)], "retiredFiles": []}
            writes, actions, skipped, retired = build_setup_plan_actions(
                workspace, repo_root, manifest, {"prompts": "local"}, {}, {}
            )

        self.assertEqual(1, writes["add"])
        self.assertEqual(1, len(actions))
        self.assertEqual("add", actions[0]["action"])
        self.assertEqual("copy-if-missing", actions[0]["strategy"])
        self.assertEqual(0, len(skipped))

    def test_copy_if_missing_plan_skips_file_even_during_factory_restore(self) -> None:
        from scripts.lifecycle.xanad_assistant import build_setup_plan_actions

        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            target = ".github/prompts/custom.md"
            target_path = workspace / target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("user content\n", encoding="utf-8")

            manifest = {"managedFiles": [self._make_copy_if_missing_entry(target)], "retiredFiles": []}
            writes, actions, skipped, retired = build_setup_plan_actions(
                workspace, repo_root, manifest, {"prompts": "local"}, {}, {}, force_reinstall=True
            )

        self.assertEqual(0, writes["add"])
        self.assertEqual(0, len(actions))
        self.assertEqual(1, len(skipped))
        self.assertEqual("copy-if-missing-present", skipped[0]["reason"])

    def test_archive_retired_moves_file_to_archive_path(self) -> None:
        from unittest.mock import patch
        from scripts.lifecycle.xanad_assistant import execute_apply_plan

        repo_root = Path(__file__).resolve().parents[2]
        retired_target = ".github/old-file.md"
        archive_path = f".xanad-assistant/archive/{retired_target}"

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            retired_file = workspace / retired_target
            retired_file.parent.mkdir(parents=True, exist_ok=True)
            retired_file.write_text("old content\n", encoding="utf-8")

            plan_payload = self._make_archive_retired_plan_payload(workspace, retired_target)

            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, repo_root, plan_payload)

            self.assertFalse(retired_file.exists())
            self.assertTrue((workspace / archive_path).exists())
            self.assertEqual("old content\n", (workspace / archive_path).read_text(encoding="utf-8"))
            self.assertEqual(1, len(result["retired"]))
            self.assertEqual("archived", result["retired"][0]["action"])
            self.assertEqual(retired_target, result["retired"][0]["target"])
            self.assertEqual(1, result["writes"]["retiredArchived"])
            self.assertEqual(0, result["writes"]["retiredReported"])

    def test_report_retired_leaves_file_in_place(self) -> None:
        from unittest.mock import patch
        from scripts.lifecycle.xanad_assistant import execute_apply_plan

        repo_root = Path(__file__).resolve().parents[2]
        retired_target = ".github/old-file.md"

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            retired_file = workspace / retired_target
            retired_file.parent.mkdir(parents=True, exist_ok=True)
            retired_file.write_text("old content\n", encoding="utf-8")

            plan_payload = self._make_archive_retired_plan_payload(
                workspace, retired_target, strategy="report-retired", archive_root=None
            )

            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, repo_root, plan_payload)

            self.assertTrue(retired_file.exists())
            self.assertEqual("old content\n", retired_file.read_text(encoding="utf-8"))
            self.assertEqual(1, len(result["retired"]))
            self.assertEqual("reported", result["retired"][0]["action"])
            self.assertEqual(0, result["writes"]["retiredArchived"])
            self.assertEqual(1, result["writes"]["retiredReported"])



if __name__ == "__main__":
    unittest.main()
