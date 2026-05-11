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

class ExecuteApplyUnitTests(unittest.TestCase):
    """Tests for execute_apply_plan calling it directly (no subprocess)."""

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

    def test_dry_run_returns_early_without_writing(self):
        """dry_run=True returns summary without executing apply."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            plan = self._make_minimal_plan_payload(workspace)
            result = execute_apply_plan(workspace, REPO_ROOT, plan, dry_run=True)
        self.assertTrue(result["dryRun"])
        self.assertFalse(result["backup"]["created"])

    def test_backup_targets_loop_copies_existing_file(self):
        """_execute_apply.py lines 53-61: backup_targets loop copies source files."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            (workspace / ".github").mkdir(parents=True)
            # Create a file that will be backed up
            target_rel = ".github/some-existing-file.md"
            target_file = workspace / target_rel
            target_file.write_text("# Existing", encoding="utf-8")
            backup_targets = [
                {
                    "target": target_rel,
                    "action": "replace",
                    "backupPath": f".xanadAssistant/backups/<apply-timestamp>/{target_rel}",
                }
            ]
            plan = self._make_minimal_plan_payload(workspace, backup_targets=backup_targets)
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, REPO_ROOT, plan)
        self.assertTrue(result["backup"]["created"])

    def test_backup_targets_loop_skips_missing_source(self):
        """_execute_apply.py line 55: continue when source_path does not exist."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            # Backup target file does NOT exist in workspace
            backup_targets = [
                {
                    "target": ".github/nonexistent-file.md",
                    "action": "replace",
                    "backupPath": ".xanadAssistant/backups/<apply-timestamp>/.github/nonexistent-file.md",
                }
            ]
            plan = self._make_minimal_plan_payload(workspace, backup_targets=backup_targets)
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, REPO_ROOT, plan)
        # Backup root was created (mkdir) but the source didn't exist so nothing was copied
        self.assertTrue(result["backup"]["created"])

    def test_factory_restore_removes_unmanaged_files(self):
        """_execute_apply.py lines 64-73: factory restore removes unmanaged files."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            agents_dir = workspace / ".github" / "agents"
            agents_dir.mkdir(parents=True)
            # Unmanaged file in a managed directory
            unmanaged = agents_dir / "rogue-agent.md"
            unmanaged.write_text("# Rogue", encoding="utf-8")
            plan = self._make_minimal_plan_payload(workspace, factory_restore=True)
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                execute_apply_plan(workspace, REPO_ROOT, plan)
        # The unmanaged file should have been removed
        self.assertFalse(unmanaged.exists())

    def test_invalid_merge_strategy_raises(self):
        """_execute_apply.py lines 98-99: raise for unsupported merge strategy."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            # Find a real manifest entry ID to reference
            from scripts.lifecycle._xanad._loader import load_manifest, load_json
            from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
            manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
            entries = manifest.get("managedFiles", [])
            if not entries:
                self.skipTest("No managed files in manifest")
            first_entry = entries[0]
            actions = [{
                "id": first_entry["id"],
                "surface": first_entry["surface"],
                "target": first_entry["target"],
                "action": "merge",
                "strategy": "unsupported-strategy-xyz",
                "tokens": [],
                "tokenValues": {},
                "ownershipMode": "local",
            }]
            plan = self._make_minimal_plan_payload(workspace, actions=actions)
            with self.assertRaises(LifecycleCommandError) as ctx:
                execute_apply_plan(workspace, REPO_ROOT, plan)
        self.assertEqual("apply_failure", ctx.exception.code)

    def test_action_referencing_missing_manifest_entry_raises(self):
        """_execute_apply.py line 107: raise when manifest entry ID not found."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            actions = [{
                "id": "nonexistent.entry.id.xyz",
                "surface": "agents",
                "target": ".github/agents/fake.agent.md",
                "action": "add",
                "strategy": "copy",
                "tokens": [],
                "tokenValues": {},
                "ownershipMode": "local",
            }]
            plan = self._make_minimal_plan_payload(workspace, actions=actions)
            with self.assertRaises(LifecycleCommandError):
                execute_apply_plan(workspace, REPO_ROOT, plan)

    def test_add_action_writes_file_and_increments_counter(self):
        """_execute_apply.py lines 114, 131, 134: add action writes file."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        # Pick an entry with strategy "copy" (not merge)
        copy_entry = next(
            (e for e in entries if e.get("strategy") not in {"merge-json-object", "preserve-marked-markdown-blocks"}),
            None,
        )
        if copy_entry is None:
            self.skipTest("No copy-strategy entries in manifest")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            actions = [{
                "id": copy_entry["id"],
                "surface": copy_entry["surface"],
                "target": copy_entry["target"],
                "action": "add",
                "strategy": copy_entry["strategy"],
                "tokens": copy_entry.get("tokens", []),
                "tokenValues": {},
                "ownershipMode": "local",
            }]
            plan = self._make_minimal_plan_payload(workspace, actions=actions)
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, REPO_ROOT, plan)
            self.assertEqual(1, result["writes"]["added"])
            self.assertTrue((workspace / copy_entry["target"]).exists())

    def test_replace_action_increments_replaced_counter(self):
        """_execute_apply.py line 135: replace action increments replaced counter."""
        from scripts.lifecycle._xanad._execute_apply import execute_apply_plan
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        entries = manifest.get("managedFiles", [])
        copy_entry = next(
            (e for e in entries if e.get("strategy") not in {"merge-json-object", "preserve-marked-markdown-blocks"}),
            None,
        )
        if copy_entry is None:
            self.skipTest("No copy-strategy entries in manifest")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            # Pre-create target so action is "replace" (file exists)
            target_path = workspace / copy_entry["target"]
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("# Old content", encoding="utf-8")
            actions = [{
                "id": copy_entry["id"],
                "surface": copy_entry["surface"],
                "target": copy_entry["target"],
                "action": "replace",
                "strategy": copy_entry["strategy"],
                "tokens": copy_entry.get("tokens", []),
                "tokenValues": {},
                "ownershipMode": "local",
            }]
            plan = self._make_minimal_plan_payload(workspace, actions=actions)
            with patch("scripts.lifecycle._xanad._check.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, REPO_ROOT, plan)
            self.assertEqual(1, result["writes"]["replaced"])



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
