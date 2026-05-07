from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class XanadAssistantPhase5Tests(unittest.TestCase):
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
                    "contents": {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanad-assistant"},
                        "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                        "timestamps": {
                            "appliedAt": "<apply-timestamp>",
                            "updatedAt": "<apply-timestamp>",
                        },
                        "selectedPacks": [],
                        "files": [],
                        "skippedManagedFiles": [],
                        "retiredManagedFiles": [],
                        "unknownValues": {},
                        "lastBackup": {"path": ".xanad-assistant/backups/<apply-timestamp>"},
                    },
                },
                "skippedActions": [],
                "factoryRestore": False,
            }
        }

    def test_lockfile_written_by_apply_validates_against_schema(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        lock_schema = json.loads(
            (repo_root / "template/setup/xanad-assistant-lock.schema.json").read_text(encoding="utf-8")
        )
        from tests.schema_validation import validate_instance

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "scripts/lifecycle/xanad_assistant.py"),
                    "apply",
                    "--json",
                    "--workspace",
                    str(workspace),
                    "--package-root",
                    str(repo_root),
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode)
            lockfile_path = workspace / ".github" / "xanad-assistant-lock.json"
            self.assertTrue(lockfile_path.exists())
            lockfile_data = json.loads(lockfile_path.read_text(encoding="utf-8"))
            validate_instance(lockfile_data, lock_schema, lock_schema)

    def test_repair_with_malformed_lockfile_backs_up_and_rewrites(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        original_lockfile_content = "NOT VALID JSON {{{"

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True)

            (github_dir / "copilot-instructions.md").write_text("modified\n", encoding="utf-8")
            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True)
            prompt.write_text("modified\n", encoding="utf-8")

            lockfile_path = github_dir / "xanad-assistant-lock.json"
            lockfile_path.write_text(original_lockfile_content, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "scripts/lifecycle/xanad_assistant.py"),
                    "repair",
                    "--json",
                    "--workspace",
                    str(workspace),
                    "--package-root",
                    str(repo_root),
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode)
            payload = json.loads(result.stdout)
            self.assertEqual("repair", payload["command"])
            self.assertEqual("ok", payload["status"])
            self.assertEqual("passed", payload["result"]["validation"]["status"])
            self.assertTrue(payload["result"]["backup"]["created"])

            backup_root = payload["result"]["backup"]["path"]
            self.assertIsNotNone(backup_root)

            lockfile_backup = workspace / backup_root / ".github" / "xanad-assistant-lock.json"
            self.assertTrue(lockfile_backup.exists(), f"Lockfile backup not found at {lockfile_backup}")
            self.assertEqual(original_lockfile_content, lockfile_backup.read_text(encoding="utf-8"))

            new_lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            self.assertEqual("0.1.0", new_lockfile["schemaVersion"])

    def test_validation_failure_leaves_backup_intact(self) -> None:
        from unittest.mock import patch
        from scripts.lifecycle.xanad_assistant import (
            build_plan_result,
            execute_apply_plan,
            LifecycleCommandError,
        )

        repo_root = Path(__file__).resolve().parents[1]
        raised_error = None

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            plan_payload = build_plan_result(workspace, repo_root, "setup", None, False)

            with patch("scripts.lifecycle.xanad_assistant.build_check_result") as mock_check:
                mock_check.return_value = {
                    "status": "drift",
                    "result": {
                        "summary": {
                            "missing": 1,
                            "stale": 0,
                            "malformed": 0,
                            "retired": 0,
                            "unmanaged": 0,
                            "unknown": 0,
                            "skipped": 0,
                            "clean": 0,
                        },
                    },
                }

                try:
                    execute_apply_plan(workspace, repo_root, plan_payload)
                    self.fail("Expected LifecycleCommandError was not raised")
                except LifecycleCommandError as exc:
                    raised_error = exc

            self.assertIsNotNone(raised_error)
            self.assertEqual("apply_failure", raised_error.code)
            self.assertEqual(9, raised_error.exit_code)
            self.assertIn("backupPath", raised_error.details)

            backup_path_str = raised_error.details["backupPath"]
            self.assertIsNotNone(backup_path_str)
            self.assertTrue(
                (workspace / backup_path_str).exists(),
                f"Backup directory not found at {workspace / backup_path_str}",
            )



if __name__ == "__main__":
    unittest.main()
