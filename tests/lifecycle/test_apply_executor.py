from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _apply_executor
from scripts.lifecycle._xanad._errors import LifecycleCommandError

from tests.lifecycle._apply_test_support import write_policy_and_manifest


class ApplyExecutorTests(unittest.TestCase):
    def test_execute_apply_plan_supports_dry_run(self) -> None:
        payload = {
            "result": {
                "writes": {"add": 1, "replace": 0, "merge": 0, "archiveRetired": 0, "deleted": 0},
                "skippedActions": [{"target": ".github/mcp/scripts/gitMcp.py"}],
                "plannedLockfile": {"path": ".github/xanadAssistant-lock.json"},
            }
        }

        result = _apply_executor.execute_apply_plan(Path("."), Path("."), payload, dry_run=True)

        self.assertTrue(result["dryRun"])
        self.assertEqual(result["writes"]["added"], 1)
        self.assertEqual(result["writes"]["skipped"], 1)

    def test_execute_apply_plan_writes_files_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            write_policy_and_manifest(package_root)
            plan_payload = {
                "result": {
                    "actions": [
                        {
                            "id": "prompts.main",
                            "target": ".github/prompts/main.prompt.md",
                            "action": "add",
                            "strategy": "replace",
                            "ownershipMode": "local",
                            "tokenValues": {},
                        }
                    ],
                    "backupPlan": {"root": ".xanadAssistant/backups/<apply-timestamp>", "targets": [], "archiveTargets": []},
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "timestamps": {"appliedAt": "<apply-timestamp>", "updatedAt": "<apply-timestamp>"},
                            "setupAnswers": {"memory.gitignore": True},
                            "selectedPacks": [],
                            "files": [],
                        },
                    },
                    "factoryRestore": False,
                    "skippedActions": [],
                }
            }

            with mock.patch("scripts.lifecycle._xanad._apply_executor._check.build_check_result", return_value={"status": "clean", "result": {"summary": {}}}):
                result = _apply_executor.execute_apply_plan(workspace, package_root, plan_payload, dry_run=False)

            self.assertTrue((workspace / ".github" / "prompts" / "main.prompt.md").exists())
            self.assertTrue((workspace / ".github" / "xanadAssistant-lock.json").exists())
            self.assertTrue((workspace / ".github" / "copilot-version.md").exists())
            self.assertTrue((workspace / ".gitignore").exists())
            self.assertEqual((workspace / ".gitignore").read_text(encoding="utf-8"), ".github/xanadAssistant/memory/\n")
            summary_text = (workspace / ".github" / "copilot-version.md").read_text(encoding="utf-8")
            self.assertIn("Selected packs: none", summary_text)
            self.assertIn("Lockfile: .github/xanadAssistant-lock.json", summary_text)
            self.assertEqual(result["validation"]["status"], "passed")

    def test_apply_executor_helper_paths_cover_gitignore_snapshots_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            gitignore = workspace / ".gitignore"
            gitignore.write_text("build/\n", encoding="utf-8")

            _apply_executor._apply_memory_gitignore(workspace, {"memory.gitignore": True})
            _apply_executor._apply_memory_gitignore(workspace, {"memory.gitignore": True})
            self.assertEqual(gitignore.read_text(encoding="utf-8"), "build/\n.github/xanadAssistant/memory/\n")

            target = workspace / "file.txt"
            snapshot_missing = _apply_executor._snapshot_file(target)
            target.write_text("before\n", encoding="utf-8")
            snapshot_present = _apply_executor._snapshot_file(target)
            target.write_text("after\n", encoding="utf-8")
            _apply_executor._restore_snapshot(target, snapshot_present)
            restored_text = target.read_text(encoding="utf-8")
            _apply_executor._restore_snapshot(target, snapshot_missing)
            self.assertFalse(target.exists())

            created = workspace / "created.txt"
            created.write_text("created\n", encoding="utf-8")
            archived = workspace / ".xanadAssistant" / "archive" / "old.txt"
            archived.parent.mkdir(parents=True, exist_ok=True)
            archived.write_text("old\n", encoding="utf-8")
            backup_root = workspace / ".xanadAssistant" / "backups" / "run"
            (backup_root / "managed.txt").parent.mkdir(parents=True, exist_ok=True)
            (backup_root / "managed.txt").write_text("managed\n", encoding="utf-8")
            _apply_executor._rollback_apply(
                workspace,
                ".xanadAssistant/backups/run",
                {"created.txt"},
                {".xanadAssistant/archive/old.txt"},
                {"managed.txt": b"snapshot\n"},
            )

        self.assertEqual(restored_text, "before\n")

    def test_build_dry_run_and_execute_apply_plan_cover_factory_restore_and_merge_failure(self) -> None:
        dry_run = _apply_executor._build_dry_run_result(
            {
                "result": {
                    "writes": {"add": 1, "replace": 2, "merge": 3, "archiveRetired": 4, "deleted": 5},
                    "skippedActions": [{"target": "x"}, {"target": "y"}],
                }
            },
            {"path": ".github/xanadAssistant-lock.json"},
        )
        self.assertEqual(dry_run["writes"]["skipped"], 2)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            write_policy_and_manifest(package_root)
            unmanaged = workspace / "unmanaged.txt"
            unmanaged.write_text("keep?\n", encoding="utf-8")
            plan_payload = {
                "result": {
                    "actions": [
                        {
                            "id": "prompts.main",
                            "target": ".github/prompts/main.prompt.md",
                            "action": "merge",
                            "strategy": "unsupported-merge",
                            "tokenValues": {},
                        }
                    ],
                    "backupPlan": {"root": ".xanadAssistant/backups/<apply-timestamp>", "targets": [], "archiveTargets": []},
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "setupAnswers": {},
                        },
                    },
                    "factoryRestore": True,
                    "skippedActions": [],
                }
            }

            with self.assertRaises(LifecycleCommandError) as excinfo:
                _apply_executor.execute_apply_plan(workspace, package_root, plan_payload, dry_run=False)

        self.assertEqual(excinfo.exception.code, "apply_failure")

    def test_factory_restore_preserves_unmanaged_lookalike_when_validation_only_reports_unmanaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            write_policy_and_manifest(package_root)
            custom_file = workspace / ".github" / "prompts" / "custom.prompt.md"
            custom_file.parent.mkdir(parents=True, exist_ok=True)
            custom_file.write_text("custom\n", encoding="utf-8")

            plan_payload = {
                "result": {
                    "actions": [],
                    "backupPlan": {"root": ".xanadAssistant/backups/<apply-timestamp>", "targets": [], "archiveTargets": []},
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "timestamps": {"appliedAt": "<apply-timestamp>", "updatedAt": "<apply-timestamp>"},
                            "setupAnswers": {},
                            "selectedPacks": [],
                            "files": [],
                        },
                    },
                    "factoryRestore": True,
                    "skippedActions": [],
                }
            }

            validation = {
                "status": "drift",
                "result": {"summary": {"missing": 0, "stale": 0, "malformed": 0, "retired": 0, "unmanaged": 1, "unknown": 0}},
            }
            with mock.patch("scripts.lifecycle._xanad._apply_executor._check.build_check_result", return_value=validation):
                result = _apply_executor.execute_apply_plan(workspace, package_root, plan_payload, dry_run=False)

            self.assertEqual(result["validation"]["status"], "passed")
            self.assertEqual(custom_file.read_text(encoding="utf-8"), "custom\n")

    def test_factory_restore_preserves_symlinked_unmanaged_lookalike_without_backup_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            write_policy_and_manifest(package_root)
            outside_file = root / "outside.txt"
            outside_file.write_text("outside\n", encoding="utf-8")
            custom_link = workspace / ".github" / "prompts" / "custom.prompt.md"
            custom_link.parent.mkdir(parents=True, exist_ok=True)
            custom_link.symlink_to(outside_file)

            plan_payload = {
                "result": {
                    "actions": [],
                    "backupPlan": {"root": ".xanadAssistant/backups/<apply-timestamp>", "targets": [], "archiveTargets": []},
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "timestamps": {"appliedAt": "<apply-timestamp>", "updatedAt": "<apply-timestamp>"},
                            "setupAnswers": {},
                            "selectedPacks": [],
                            "files": [],
                        },
                    },
                    "factoryRestore": True,
                    "skippedActions": [],
                }
            }

            validation = {
                "status": "drift",
                "result": {"summary": {"missing": 0, "stale": 0, "malformed": 0, "retired": 0, "unmanaged": 1, "unknown": 0}},
            }
            with mock.patch("scripts.lifecycle._xanad._apply_executor._check.build_check_result", return_value=validation):
                _apply_executor.execute_apply_plan(workspace, package_root, plan_payload, dry_run=False)

            self.assertTrue(custom_link.is_symlink())
            self.assertEqual(outside_file.read_text(encoding="utf-8"), "outside\n")
            backup_root = workspace / ".xanadAssistant" / "backups"
            self.assertFalse(any(backup_root.rglob("custom.prompt.md")))

    def test_factory_restore_still_fails_when_validation_reports_non_unmanaged_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            write_policy_and_manifest(package_root)

            plan_payload = {
                "result": {
                    "actions": [],
                    "backupPlan": {"root": ".xanadAssistant/backups/<apply-timestamp>", "targets": [], "archiveTargets": []},
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "timestamps": {"appliedAt": "<apply-timestamp>", "updatedAt": "<apply-timestamp>"},
                            "setupAnswers": {},
                            "selectedPacks": [],
                            "files": [],
                        },
                    },
                    "factoryRestore": True,
                    "skippedActions": [],
                }
            }

            validation = {
                "status": "drift",
                "result": {"summary": {"missing": 1, "stale": 0, "malformed": 0, "retired": 0, "unmanaged": 1, "unknown": 0}},
            }
            with mock.patch("scripts.lifecycle._xanad._apply_executor._check.build_check_result", return_value=validation):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    _apply_executor.execute_apply_plan(workspace, package_root, plan_payload, dry_run=False)

            self.assertEqual(excinfo.exception.code, "apply_failure")

    def test_rollback_metadata_reports_failure_when_rollback_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            with mock.patch("scripts.lifecycle._xanad._apply_executor._rollback_apply", side_effect=RuntimeError("rollback failed")):
                result = _apply_executor._rollback_metadata(workspace, None, set(), set(), {})

        self.assertFalse(result["rolledBack"])
        self.assertIn("rollback failed", result["rollbackError"])

    def test_assert_within_workspace_raises_for_outside_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside_dir:
            workspace = Path(tmpdir).resolve()
            outside = Path(outside_dir).resolve()
            outside_file = outside / "secret.txt"

            with self.assertRaises(LifecycleCommandError) as exc:
                _apply_executor._assert_within_workspace(outside_file, workspace)

        self.assertEqual(exc.exception.code, "apply_failure")

    def test_assert_within_workspace_accepts_paths_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir).resolve()
            inside = workspace / ".github" / "agents" / "foo.md"
            _apply_executor._assert_within_workspace(inside, workspace)

    def test_apply_memory_gitignore_removes_entry_when_opted_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            gitignore = workspace / ".gitignore"
            gitignore.write_text("build/\n.github/xanadAssistant/memory/\n", encoding="utf-8")

            _apply_executor._apply_memory_gitignore(workspace, {"memory.gitignore": False})

            self.assertEqual(gitignore.read_text(encoding="utf-8"), "build/\n")

    def test_apply_memory_gitignore_opted_out_is_noop_when_entry_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            gitignore = workspace / ".gitignore"
            gitignore.write_text("build/\n", encoding="utf-8")

            _apply_executor._apply_memory_gitignore(workspace, {"memory.gitignore": False})

            self.assertEqual(gitignore.read_text(encoding="utf-8"), "build/\n")

    def test_apply_memory_gitignore_opted_out_is_noop_when_gitignore_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            _apply_executor._apply_memory_gitignore(workspace, {"memory.gitignore": False})

            self.assertFalse((workspace / ".gitignore").exists())

    def test_build_dry_run_result_includes_sanitized_and_unmanagedarchived(self) -> None:
        payload = {
            "result": {
                "writes": {"add": 0, "replace": 0, "merge": 0, "archiveRetired": 0, "deleted": 0, "archiveUnmanaged": 2},
                "skippedActions": [],
                "plannedLockfile": {"path": ".github/xanadAssistant-lock.json"},
            }
        }

        result = _apply_executor.execute_apply_plan(Path("."), Path("."), payload, dry_run=True)

        self.assertIn("sanitized", result)
        self.assertEqual(result["sanitized"], [])
        self.assertEqual(result["writes"]["unmanagedArchived"], 2)

    def test_execute_apply_plan_archives_sanitizable_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            write_policy_and_manifest(package_root)
            # Create an unmanaged Copilot-shaped file
            github = workspace / ".github"
            github.mkdir(parents=True)
            unmanaged_agent = github / "unmanaged.agent.md"
            unmanaged_agent.write_text("# unmanaged\n", encoding="utf-8")

            plan_payload = {
                "result": {
                    "actions": [
                        {
                            "id": ".github/unmanaged.agent.md",
                            "target": ".github/unmanaged.agent.md",
                            "action": "archive-unmanaged",
                            "strategy": "move",
                        }
                    ],
                    "backupPlan": {"root": None, "targets": [], "archiveTargets": []},
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "timestamps": {"appliedAt": "<apply-timestamp>", "updatedAt": "<apply-timestamp>"},
                            "setupAnswers": {"memory.gitignore": False},
                            "selectedPacks": [],
                            "files": [],
                        },
                    },
                    "factoryRestore": False,
                    "sanitize": {"enabled": True, "targets": [".github/unmanaged.agent.md"]},
                    "skippedActions": [],
                }
            }

            with mock.patch("scripts.lifecycle._xanad._apply_executor._check.build_check_result", return_value={"status": "clean", "result": {"summary": {}}}):
                result = _apply_executor.execute_apply_plan(workspace, package_root, plan_payload, dry_run=False)

            self.assertFalse(unmanaged_agent.exists(), "Unmanaged file should have been archived")
            self.assertEqual(result["writes"]["unmanagedArchived"], 1)
            self.assertEqual(len(result["sanitized"]), 1)
            sanitized = result["sanitized"][0]
            self.assertEqual(sanitized["target"], ".github/unmanaged.agent.md")
            self.assertEqual(sanitized["action"], "archived")
            archive_dest = workspace / sanitized["archivePath"]
            self.assertTrue(archive_dest.exists(), "Archive destination should exist")


if __name__ == "__main__":
    unittest.main()
