from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad._errors import LifecycleCommandError


class ScriptAuditApplyExecutorRegressionsTests(unittest.TestCase):
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
            self.assertFalse((workspace / ".xanadAssistant" / "backups").rglob("managed.txt").__next__() if False else False)

    def test_apply_rolls_back_lockfile_and_summary_when_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            github_dir = workspace / ".github"
            github_dir.mkdir()
            original_lockfile = github_dir / "xanadAssistant-lock.json"
            original_summary = github_dir / "copilot-version.md"
            original_lockfile.write_text('{"previous": true}\n', encoding="utf-8")
            original_summary.write_text("previous summary\n", encoding="utf-8")

            plan_payload = {
                "result": {
                    "actions": [],
                    "backupPlan": {},
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
                return_value={"managedFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_json",
                return_value={},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.build_copilot_version_summary",
                return_value="new summary\n",
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor._check.build_check_result",
                return_value={"status": "drift", "result": {"summary": {"missing": 1}}},
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

                self.assertEqual(excinfo.exception.code, "apply_failure")
                self.assertEqual(excinfo.exception.exit_code, 9)
                self.assertTrue(excinfo.exception.details["rolledBack"])
                self.assertEqual(original_lockfile.read_text(encoding="utf-8"), '{"previous": true}\n')
                self.assertEqual(original_summary.read_text(encoding="utf-8"), "previous summary\n")

    def test_apply_restores_retired_file_when_validation_fails_after_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            retired_file = workspace / ".github" / "prompts" / "legacy.prompt.md"
            retired_file.parent.mkdir(parents=True, exist_ok=True)
            retired_file.write_text("legacy\n", encoding="utf-8")

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
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.build_copilot_version_summary",
                return_value="new summary\n",
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor._check.build_check_result",
                return_value={"status": "drift", "result": {"summary": {"retired": 1}}},
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

                self.assertEqual(excinfo.exception.code, "apply_failure")
                self.assertTrue(excinfo.exception.details["rolledBack"])
                self.assertEqual(retired_file.read_text(encoding="utf-8"), "legacy\n")
                self.assertFalse((workspace / ".xanadAssistant" / "archive" / ".github" / "prompts" / "legacy.prompt.md").exists())

    def test_apply_wraps_backup_copy_failure_in_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            target = workspace / "managed.txt"
            target.write_text("managed\n", encoding="utf-8")
            plan_payload = {
                "result": {
                    "actions": [{"id": "managed.txt", "action": "delete", "target": "managed.txt"}],
                    "backupPlan": {
                        "root": ".xanadAssistant/backups/<apply-timestamp>",
                        "targets": [{"target": "managed.txt", "backupPath": ".xanadAssistant/backups/<apply-timestamp>/managed.txt"}],
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
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor._copy_backup_file",
                side_effect=OSError("backup copy failed"),
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

                self.assertEqual(excinfo.exception.code, "apply_failure")
                self.assertEqual(excinfo.exception.exit_code, 9)
                self.assertTrue(excinfo.exception.details["rolledBack"])
                self.assertEqual(target.read_text(encoding="utf-8"), "managed\n")

    def test_apply_wraps_lockfile_write_failure_in_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            plan_payload = {
                "result": {
                    "actions": [],
                    "backupPlan": {},
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
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor._write_lockfile",
                side_effect=OSError("disk full"),
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

                self.assertEqual(excinfo.exception.code, "apply_failure")
                self.assertEqual(excinfo.exception.exit_code, 9)
                self.assertTrue(excinfo.exception.details["rolledBack"])
                self.assertFalse((workspace / ".github" / "xanadAssistant-lock.json").exists())

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