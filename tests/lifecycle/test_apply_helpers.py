from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _apply
from scripts.lifecycle._xanad import _apply_executor
from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH, LifecycleCommandError


class ApplyHelperTests(unittest.TestCase):
    def test_generate_and_materialize_apply_timestamps(self) -> None:
        applied_at, path_timestamp = _apply.generate_apply_timestamps()

        self.assertTrue(applied_at.endswith("Z"))
        self.assertIn("T", path_timestamp)
        self.assertEqual(
            _apply.materialize_apply_timestamp(".xanadAssistant/backups/<apply-timestamp>", path_timestamp),
            f".xanadAssistant/backups/{path_timestamp}",
        )

    def test_render_entry_bytes_raises_when_rendering_fails(self) -> None:
        with mock.patch("scripts.lifecycle._xanad._apply.expected_entry_bytes", return_value=None):
            with self.assertRaises(LifecycleCommandError):
                _apply.render_entry_bytes(Path("."), {"id": "managed.prompt", "strategy": "replace"}, {})

    def test_merge_json_object_file_strips_comments_and_merge_markdown_preserves_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            package_root = root / "package"
            package_root.mkdir()
            json_source = package_root / "config.json"
            json_source.write_text(json.dumps({"setting": True}), encoding="utf-8")
            json_target = root / "config.json"
            json_target.write_text('{\n  // comment\n  "existing": 1\n}\n', encoding="utf-8")
            markdown_source = package_root / "instructions.md"
            markdown_source.write_text("# Title\n\nBase\n", encoding="utf-8")
            markdown_target = root / "instructions.md"
            markdown_target.write_text("# Title\n\n<!-- user-added -->keep<!-- /user-added -->\n", encoding="utf-8")

            _apply.merge_json_object_file(json_target, package_root, {"source": "config.json"})
            _apply.merge_markdown_file(markdown_target, package_root, {"source": "instructions.md"})

            merged_json = json.loads(json_target.read_text(encoding="utf-8"))
            merged_markdown = markdown_target.read_text(encoding="utf-8")

        self.assertEqual(merged_json, {"existing": 1, "setting": True})
        self.assertIn("<!-- user-added -->keep<!-- /user-added -->", merged_markdown)

    def test_build_summary_and_apply_chmod_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "script.sh"
            target.write_text("echo hi\n", encoding="utf-8")
            summary = _apply.build_copilot_version_summary(
                {
                    "profile": "balanced",
                    "selectedPacks": ["tdd"],
                    "manifest": {"hash": "sha256:abc"},
                    "timestamps": {"appliedAt": "2026-05-16T00:00:00Z"},
                },
                {"packageVersion": "1.2.3"},
            )
            _apply.apply_chmod_rule(target, "executable")

            self.assertTrue(target.stat().st_mode & stat.S_IXUSR)

        self.assertIn("Version: 1.2.3", summary)


class ApplyExecutorTests(unittest.TestCase):
    def _write_policy_and_manifest(self, package_root: Path) -> None:
        policy_path = package_root / DEFAULT_POLICY_PATH
        manifest_path = package_root / "template" / "setup" / "install-manifest.json"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(
            json.dumps({"generationSettings": {"manifestOutput": "template/setup/install-manifest.json"}}),
            encoding="utf-8",
        )
        manifest_path.write_text(
            json.dumps(
                {
                    "managedFiles": [
                        {
                            "id": "prompts.main",
                            "target": ".github/prompts/main.prompt.md",
                            "source": "template/main.prompt.md",
                            "strategy": "replace",
                            "hash": "sha256:source",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (package_root / "template" / "main.prompt.md").write_text("prompt\n", encoding="utf-8")

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
            self._write_policy_and_manifest(package_root)
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
            self._write_policy_and_manifest(package_root)
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

            with mock.patch("scripts.lifecycle._xanad._apply_executor.collect_unmanaged_files", return_value=["unmanaged.txt"]):
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


if __name__ == "__main__":
    unittest.main()