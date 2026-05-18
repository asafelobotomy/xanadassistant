from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad._errors import LifecycleCommandError


class ScriptAuditApplyExecutorPathRegressionsTests(unittest.TestCase):
    def test_apply_rejects_backup_source_symlink_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()
            package_root = root / "package"
            package_root.mkdir()
            outside_file = root / "outside.txt"
            outside_file.write_text("outside\n", encoding="utf-8")
            symlink_path = workspace / "managed.txt"
            symlink_path.symlink_to(outside_file)

            plan_payload = {
                "result": {
                    "actions": [],
                    "backupPlan": {
                        "root": ".xanadAssistant/backups/<apply-timestamp>",
                        "targets": [
                            {
                                "target": "managed.txt",
                                "backupPath": ".xanadAssistant/backups/<apply-timestamp>/managed.txt",
                            }
                        ],
                        "archiveTargets": [],
                    },
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "setupAnswers": {},
                        },
                    },
                    "factoryRestore": False,
                    "skippedActions": [],
                    "writes": {},
                }
            }

            from scripts.lifecycle._xanad._execute_apply import execute_apply_plan

            with mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_manifest",
                return_value={"managedFiles": [], "retiredFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_json",
                return_value={},
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

            self.assertEqual(excinfo.exception.code, "apply_failure")
            self.assertTrue(symlink_path.is_symlink())
            self.assertEqual(outside_file.read_text(encoding="utf-8"), "outside\n")
            self.assertFalse(any((workspace / ".xanadAssistant" / "backups").rglob("managed.txt")))

    def test_apply_rejects_delete_target_symlink_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()
            package_root = root / "package"
            package_root.mkdir()
            outside_dir = root / "outside"
            outside_dir.mkdir()
            outside_file = outside_dir / "victim.txt"
            outside_file.write_text("victim\n", encoding="utf-8")
            target_path = workspace / ".github" / "prompts" / "victim.txt"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.symlink_to(outside_file)

            plan_payload = {
                "result": {
                    "actions": [{"id": "delete:victim", "action": "delete", "target": ".github/prompts/victim.txt"}],
                    "backupPlan": {
                        "root": ".xanadAssistant/backups/<apply-timestamp>",
                        "targets": [],
                        "archiveTargets": [],
                    },
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "setupAnswers": {},
                        },
                    },
                    "factoryRestore": False,
                    "skippedActions": [],
                    "writes": {"deleted": 1},
                }
            }

            from scripts.lifecycle._xanad._execute_apply import execute_apply_plan

            with mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_manifest",
                return_value={"managedFiles": [], "retiredFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_json",
                return_value={},
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

            self.assertEqual(excinfo.exception.code, "apply_failure")
            self.assertTrue(target_path.is_symlink())
            self.assertEqual(outside_file.read_text(encoding="utf-8"), "victim\n")

    def test_apply_rejects_archive_retired_target_symlink_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()
            package_root = root / "package"
            package_root.mkdir()
            outside_dir = root / "outside"
            outside_dir.mkdir()
            outside_file = outside_dir / "legacy.prompt.md"
            outside_file.write_text("legacy\n", encoding="utf-8")
            target_path = workspace / ".github" / "prompts" / "legacy.prompt.md"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.symlink_to(outside_file)

            plan_payload = {
                "result": {
                    "actions": [
                        {
                            "id": "retired.legacy",
                            "action": "archive-retired",
                            "target": ".github/prompts/legacy.prompt.md",
                        }
                    ],
                    "backupPlan": {
                        "root": ".xanadAssistant/backups/<apply-timestamp>",
                        "targets": [],
                        "archiveTargets": [
                            {
                                "target": ".github/prompts/legacy.prompt.md",
                                "archivePath": ".xanadAssistant/archive/.github/prompts/legacy.prompt.md",
                            }
                        ],
                    },
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "setupAnswers": {},
                        },
                    },
                    "factoryRestore": False,
                    "skippedActions": [],
                    "writes": {"archiveRetired": 1},
                }
            }

            from scripts.lifecycle._xanad._execute_apply import execute_apply_plan

            with mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_manifest",
                return_value={"managedFiles": [], "retiredFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_json",
                return_value={},
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

            self.assertEqual(excinfo.exception.code, "apply_failure")
            self.assertTrue(target_path.is_symlink())
            self.assertEqual(outside_file.read_text(encoding="utf-8"), "legacy\n")
            self.assertFalse((workspace / ".xanadAssistant" / "archive").exists())


if __name__ == "__main__":
    unittest.main()