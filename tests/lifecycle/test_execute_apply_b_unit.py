"""Unit tests for _execute_apply.py covering execute_apply_plan branches."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# _execute_apply.py
# ---------------------------------------------------------------------------

class ExecuteApplyUnitBTests(unittest.TestCase):
    def _make_minimal_plan_payload(
        self,
        workspace: Path,
        actions: list[dict] | None = None,
        backup_targets: list[dict] | None = None,
        factory_restore: bool = False,
    ) -> dict:
        """Build a minimal plan_payload for execute_apply_plan."""
        from scripts.lifecycle._xanad._merge import sha256_json
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        manifest_hash = sha256_json(manifest) if manifest else "sha256:fake"
        return {
            "result": {
                "actions": actions or [],
                "backupPlan": {
                    "required": bool(backup_targets),
                    "root": ".xanadAssistant/backups/<apply-timestamp>" if backup_targets else None,
                    "targets": backup_targets or [],
                    "archiveRoot": None,
                    "archiveTargets": [],
                },
                "plannedLockfile": {
                    "path": ".github/xanadAssistant-lock.json",
                    "contents": {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanadAssistant", "packageRoot": str(REPO_ROOT)},
                        "manifest": {"schemaVersion": "0.1.0", "hash": manifest_hash},
                        "timestamps": {
                            "appliedAt": "<apply-timestamp>",
                            "updatedAt": "<apply-timestamp>",
                        },
                        "selectedPacks": [],
                        "profile": "balanced",
                        "ownershipBySurface": {},
                        "setupAnswers": {},
                        "installMetadata": {"mcpAvailable": True, "mcpEnabled": False},
                        "files": [],
                        "skippedManagedFiles": [],
                        "retiredManagedFiles": [],
                        "unknownValues": {},
                    },
                },
                "writes": {"add": 0, "replace": 0, "merge": 0, "archiveRetired": 0},
                "skippedActions": [],
                "factoryRestore": factory_restore,
            }
        }

    def test_merge_json_action_merges_file(self):
        """_execute_apply.py lines 123-128: merge-json-object action calls merge_json_object_file."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        entries = manifest.get("managedFiles", [])
        merge_entry = next(
            (e for e in entries if e.get("strategy") == "merge-json-object"),
            None,
        )
        if merge_entry is None:
            self.skipTest("No merge-json-object entries in manifest")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            actions = [{
                "id": merge_entry["id"],
                "surface": merge_entry["surface"],
                "target": merge_entry["target"],
                "action": "merge",
                "strategy": "merge-json-object",
                "tokens": merge_entry.get("tokens", []),
                "tokenValues": {},
                "ownershipMode": "local",
            }]
            plan = self._make_minimal_plan_payload(workspace, actions=actions)
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, REPO_ROOT, plan)
            self.assertEqual(1, result["writes"]["merged"])

    def test_validation_failure_raises(self):
        """_execute_apply.py lines 147-149: raise when post-apply check is not clean."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            plan = self._make_minimal_plan_payload(workspace)
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {
                    "status": "drift",
                    "result": {"summary": {"missing": 1, "stale": 0}},
                }
                with self.assertRaises(LifecycleCommandError) as ctx:
                    execute_apply_plan(workspace, REPO_ROOT, plan)
        self.assertEqual("apply_failure", ctx.exception.code)

    def test_invalid_merge_strategy_raises_apply_failure(self):
        """_execute_apply.py lines 98-99: merge with unknown strategy raises LifecycleCommandError."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            actions = [{
                "id": "test-merge-unknown",
                "surface": "agents",
                "target": ".github/agents/test.md",
                "action": "merge",
                "strategy": "unknown-strategy-xyz",
                "tokens": [],
                "tokenValues": {},
                "ownershipMode": "local",
            }]
            plan = self._make_minimal_plan_payload(workspace, actions=actions)
            with self.assertRaises(LifecycleCommandError) as ctx:
                execute_apply_plan(workspace, REPO_ROOT, plan)
        self.assertEqual("apply_failure", ctx.exception.code)

    def test_backup_target_skips_when_backup_path_is_none(self):
        """_execute_apply.py line 58: continue when materialize returns None for backupPath."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            (workspace / ".github").mkdir(parents=True)
            existing = workspace / ".github" / "existing.md"
            existing.write_text("# Existing", encoding="utf-8")
            # backupPath=None → materialize_apply_timestamp returns None → continue
            backup_targets = [
                {"target": ".github/existing.md", "action": "replace", "backupPath": None}
            ]
            plan = self._make_minimal_plan_payload(workspace, backup_targets=backup_targets)
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, REPO_ROOT, plan)
        self.assertTrue(result["backup"]["created"])

    def test_factory_restore_with_backup_copies_unmanaged_before_remove(self):
        """_execute_apply.py lines 69-71: unmanaged file is backed up when backup_root is set."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            agents_dir = workspace / ".github" / "agents"
            agents_dir.mkdir(parents=True)
            unmanaged = agents_dir / "rogue-agent.md"
            unmanaged.write_text("# Rogue", encoding="utf-8")
            # Provide a backup root so lines 69-71 (copy before remove) are hit
            backup_targets: list[dict] = []
            plan = self._make_minimal_plan_payload(
                workspace, backup_targets=backup_targets, factory_restore=True,
            )
            # Override the backup plan to include a root so backup_root is not None
            plan["result"]["backupPlan"]["root"] = ".xanadAssistant/backups/<apply-timestamp>"
            plan["result"]["backupPlan"]["required"] = True
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                execute_apply_plan(workspace, REPO_ROOT, plan)
        self.assertFalse(unmanaged.exists())

    def test_merge_markdown_action_merges_file(self):
        """_execute_apply.py line 126: preserve-marked-markdown-blocks action calls merge_markdown_file."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        entries = manifest.get("managedFiles", [])
        merge_entry = next(
            (e for e in entries if e.get("strategy") == "preserve-marked-markdown-blocks"),
            None,
        )
        if merge_entry is None:
            self.skipTest("No preserve-marked-markdown-blocks entries in manifest")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            actions = [{
                "id": merge_entry["id"],
                "surface": merge_entry["surface"],
                "target": merge_entry["target"],
                "action": "merge",
                "strategy": "preserve-marked-markdown-blocks",
                "tokens": merge_entry.get("tokens", []),
                "tokenValues": {},
                "ownershipMode": "local",
            }]
            plan = self._make_minimal_plan_payload(workspace, actions=actions)
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, REPO_ROOT, plan)
            self.assertEqual(1, result["writes"]["merged"])

    def test_backup_existing_lockfile_when_backup_root_set(self):
        """_execute_apply.py lines 147-149: existing lockfile is backed up."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True)
            # Create an existing lockfile so it gets backed up
            lockfile_path = github_dir / "xanadAssistant-lock.json"
            lockfile_path.write_text('{"schemaVersion": "0.1.0"}', encoding="utf-8")
            backup_targets: list[dict] = []
            plan = self._make_minimal_plan_payload(workspace, backup_targets=backup_targets)
            # Set a backup root so the lockfile is backed up
            plan["result"]["backupPlan"]["root"] = ".xanadAssistant/backups/<apply-timestamp>"
            plan["result"]["backupPlan"]["required"] = True
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, REPO_ROOT, plan)
        self.assertTrue(result["backup"]["created"])

    def test_archive_retired_unlinks_existing_file_when_no_archive_path(self):
        """_execute_apply.py lines 98-99: archive-retired target exists but no archivePath → unlink."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True)
            # Create a file that should be removed by archive-retired
            retired_file = github_dir / "old-file.md"
            retired_file.write_text("# Old", encoding="utf-8")
            actions = [
                {
                    "action": "archive-retired",
                    "target": ".github/old-file.md",
                    "strategy": "archive-retired",
                }
            ]
            plan = self._make_minimal_plan_payload(workspace, actions=actions)
            # archiveTargets is empty by default → no archive path → elif target_path.exists()
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                execute_apply_plan(workspace, REPO_ROOT, plan)
        self.assertFalse(retired_file.exists())



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
