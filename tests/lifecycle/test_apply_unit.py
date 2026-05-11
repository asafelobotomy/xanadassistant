"""Unit tests for _apply.py and _execute_apply.py covering uncovered branches.

These tests call the functions directly (no subprocess) to capture coverage.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# _apply.py
# ---------------------------------------------------------------------------

class MaterializeApplyTimestampTests(unittest.TestCase):
    def test_returns_none_when_value_is_none(self):
        """_apply.py line 30: return None when value is None."""
        from scripts.lifecycle._xanad._apply import materialize_apply_timestamp
        result = materialize_apply_timestamp(None, "2026-01-01T00-00-00Z")
        self.assertIsNone(result)

    def test_replaces_apply_timestamp_placeholder(self):
        from scripts.lifecycle._xanad._apply import materialize_apply_timestamp
        result = materialize_apply_timestamp(".backup/<apply-timestamp>", "2026-01-01T00-00-00Z")
        self.assertEqual(".backup/2026-01-01T00-00-00Z", result)


class RenderEntryBytesTests(unittest.TestCase):
    def test_raises_lifecycle_command_error_when_expected_bytes_is_none(self):
        """_apply.py line 37: raise LifecycleCommandError when result is None."""
        from scripts.lifecycle._xanad._apply import render_entry_bytes
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            # merge-json-object with non-dict source → expected_entry_bytes returns None
            (pkg_root / "source.json").write_text("[1, 2, 3]", encoding="utf-8")
            entry = {
                "id": "test.entry",
                "source": "source.json",
                "strategy": "merge-json-object",
                "tokens": [],
                "hash": "sha256:fake",
            }
            with self.assertRaises(LifecycleCommandError):
                render_entry_bytes(pkg_root, entry, {})


class MergeJsonObjectFileTests(unittest.TestCase):
    def test_merges_when_target_exists_and_both_are_dicts(self):
        """_apply.py lines 47-72: merge when target exists with valid JSON dict."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "source.json").write_text('{"a": 1}', encoding="utf-8")
            target_path = workspace / ".github" / "mcp.json"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text('{"b": 2}', encoding="utf-8")
            entry = {"id": "test", "source": "source.json"}
            merge_json_object_file(target_path, pkg_root, entry)
            merged = json.loads(target_path.read_text(encoding="utf-8"))
        self.assertIn("a", merged)
        self.assertIn("b", merged)

    def test_raises_when_target_json_is_invalid(self):
        """_apply.py lines 51-56: raise when target JSON cannot be decoded."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "source.json").write_text('{"a": 1}', encoding="utf-8")
            target_path = workspace / "target.json"
            target_path.write_text("{invalid json", encoding="utf-8")
            entry = {"id": "test", "source": "source.json"}
            with self.assertRaises(LifecycleCommandError):
                merge_json_object_file(target_path, pkg_root, entry)

    def test_raises_when_target_is_not_dict(self):
        """_apply.py lines 57-62: raise when target JSON is valid but not a dict."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "source.json").write_text('{"a": 1}', encoding="utf-8")
            target_path = workspace / "target.json"
            target_path.write_text('[1, 2, 3]', encoding="utf-8")
            entry = {"id": "test", "source": "source.json"}
            with self.assertRaises(LifecycleCommandError):
                merge_json_object_file(target_path, pkg_root, entry)

    def test_writes_source_when_target_does_not_exist(self):
        """_apply.py lines 63-71: write source when target does not exist."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "source.json").write_text('{"key": "value"}', encoding="utf-8")
            target_path = workspace / "target.json"
            entry = {"id": "test", "source": "source.json"}
            merge_json_object_file(target_path, pkg_root, entry)
            result = json.loads(target_path.read_text(encoding="utf-8"))
        self.assertEqual({"key": "value"}, result)

    def test_raises_when_source_is_not_dict_and_target_missing(self):
        """_apply.py lines 67-71: raise when source JSON is not a dict."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "source.json").write_text('[1, 2, 3]', encoding="utf-8")
            target_path = workspace / "target.json"
            entry = {"id": "test", "source": "source.json"}
            with self.assertRaises(LifecycleCommandError):
                merge_json_object_file(target_path, pkg_root, entry)


class MergeMarkdownFileTests(unittest.TestCase):
    def test_merges_when_target_exists(self):
        """_apply.py lines 78-86: merge markdown when target exists preserves user-added blocks."""
        from scripts.lifecycle._xanad._apply import merge_markdown_file
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "template.md").write_text("# Header\n", encoding="utf-8")
            target_path = workspace / "target.md"
            # user-added block in the existing target should be preserved
            target_path.write_text(
                "# Header\n\n<!-- user-added -->\nMY CUSTOM CONTENT\n<!-- /user-added -->\n",
                encoding="utf-8",
            )
            entry = {"id": "test", "source": "template.md"}
            merge_markdown_file(target_path, pkg_root, entry)
            merged = target_path.read_text(encoding="utf-8")
            self.assertIn("MY CUSTOM CONTENT", merged)

    def test_writes_source_when_target_does_not_exist(self):
        """_apply.py line 85: write rendered source when target does not exist."""
        from scripts.lifecycle._xanad._apply import merge_markdown_file
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "template.md").write_text("# Hello\n", encoding="utf-8")
            target_path = workspace / "output.md"
            entry = {"id": "test", "source": "template.md"}
            merge_markdown_file(target_path, pkg_root, entry)
            content = target_path.read_text(encoding="utf-8")
        self.assertEqual("# Hello\n", content)


class BuildCopilotVersionSummaryTests(unittest.TestCase):
    def test_uses_unknown_version_when_manifest_has_no_package_version(self):
        """_apply.py line 94: package_version = 'unknown' when manifest lacks packageVersion."""
        from scripts.lifecycle._xanad._apply import build_copilot_version_summary
        lockfile = {
            "profile": "balanced",
            "selectedPacks": [],
            "manifest": {"hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z"},
        }
        result = build_copilot_version_summary(lockfile, None)
        self.assertIn("Version: unknown", result)

    def test_uses_provided_version_from_manifest(self):
        from scripts.lifecycle._xanad._apply import build_copilot_version_summary
        lockfile = {
            "profile": "balanced",
            "selectedPacks": ["lean"],
            "manifest": {"hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z"},
        }
        manifest = {"packageVersion": "1.2.3"}
        result = build_copilot_version_summary(lockfile, manifest)
        self.assertIn("Version: 1.2.3", result)
        self.assertIn("lean", result)


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
                    "root": ".xanad-assistant/backups/<apply-timestamp>" if backup_targets else None,
                    "targets": backup_targets or [],
                    "archiveRoot": None,
                    "archiveTargets": [],
                },
                "plannedLockfile": {
                    "path": ".github/xanad-assistant-lock.json",
                    "contents": {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanad-assistant", "packageRoot": str(REPO_ROOT)},
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
                    "backupPath": f".xanad-assistant/backups/<apply-timestamp>/{target_rel}",
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
                    "backupPath": ".xanad-assistant/backups/<apply-timestamp>/.github/nonexistent-file.md",
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
            plan["result"]["backupPlan"]["root"] = ".xanad-assistant/backups/<apply-timestamp>"
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
            lockfile_path = github_dir / "xanad-assistant-lock.json"
            lockfile_path.write_text('{"schemaVersion": "0.1.0"}', encoding="utf-8")
            backup_targets: list[dict] = []
            plan = self._make_minimal_plan_payload(workspace, backup_targets=backup_targets)
            # Set a backup root so the lockfile is backed up
            plan["result"]["backupPlan"]["root"] = ".xanad-assistant/backups/<apply-timestamp>"
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
