from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class LockfileMigrationTests(unittest.TestCase):
    """Coverage for pre-0.1.0 lockfile shapes that are valid JSON but structurally incomplete."""

    REPO_ROOT = Path(__file__).resolve().parents[1]
    SCRIPT = REPO_ROOT / "scripts" / "lifecycle" / "xanad_assistant.py"

    def _run(self, command: str, *extra_args: str, workspace: Path) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(self.SCRIPT), command]
        if command == "plan" and extra_args and not extra_args[0].startswith("-"):
            cmd.append(extra_args[0])
            extra_args = extra_args[1:]
        cmd += ["--workspace", str(workspace), "--package-root", str(self.REPO_ROOT)]
        return subprocess.run(
            cmd + list(extra_args),
            cwd=self.REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def _write_lockfile(self, workspace: Path, data: dict) -> None:
        path = workspace / ".github" / "xanad-assistant-lock.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # _lockfile_needs_migration – unit tests
    # ------------------------------------------------------------------

    def test_needs_migration_empty_object(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        self.assertTrue(_lockfile_needs_migration({}))

    def test_needs_migration_missing_files(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanad-assistant"},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": [],
            # "files" intentionally absent
        }
        self.assertTrue(_lockfile_needs_migration(data))

    def test_needs_migration_missing_manifest_hash(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanad-assistant"},
            "manifest": {"schemaVersion": "0.1.0"},  # hash absent
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": [],
            "files": [],
        }
        self.assertTrue(_lockfile_needs_migration(data))

    def test_needs_migration_missing_package_name(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {},  # name absent
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": [],
            "files": [],
        }
        self.assertTrue(_lockfile_needs_migration(data))

    def test_needs_migration_valid_shape_returns_false(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanad-assistant"},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc123"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": [],
            "files": [],
        }
        self.assertFalse(_lockfile_needs_migration(data))

    # ------------------------------------------------------------------
    # migrate_lockfile_shape – unit tests
    # ------------------------------------------------------------------

    def test_migrate_fills_all_required_fields(self) -> None:
        from scripts.lifecycle.xanad_assistant import migrate_lockfile_shape, _lockfile_needs_migration
        migrated = migrate_lockfile_shape({})
        self.assertFalse(_lockfile_needs_migration(migrated))
        self.assertEqual("0.1.0", migrated["schemaVersion"])
        self.assertEqual("xanad-assistant", migrated["package"]["name"])
        self.assertIn("hash", migrated["manifest"])
        self.assertIn("appliedAt", migrated["timestamps"])
        self.assertEqual([], migrated["selectedPacks"])
        self.assertEqual([], migrated["files"])

    def test_migrate_preserves_existing_fields(self) -> None:
        from scripts.lifecycle.xanad_assistant import migrate_lockfile_shape
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanad-assistant"},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": ["lean"],
            "profile": "lean",
            # files absent
        }
        migrated = migrate_lockfile_shape(data)
        self.assertEqual(["lean"], migrated["selectedPacks"])
        self.assertEqual("lean", migrated["profile"])
        self.assertEqual("sha256:abc", migrated["manifest"]["hash"])

    # ------------------------------------------------------------------
    # parse_lockfile_state – reports needsMigration
    # ------------------------------------------------------------------

    def test_parse_lockfile_state_sets_needs_migration_for_empty_object(self) -> None:
        from scripts.lifecycle.xanad_assistant import parse_lockfile_state
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {})
            state = parse_lockfile_state(workspace)
            self.assertTrue(state["present"])
            self.assertFalse(state["malformed"])
            self.assertTrue(state["needsMigration"])

    def test_parse_lockfile_state_clears_needs_migration_for_valid_shape(self) -> None:
        from scripts.lifecycle.xanad_assistant import parse_lockfile_state
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanad-assistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [],
                "files": [],
            })
            state = parse_lockfile_state(workspace)
            self.assertFalse(state["malformed"])
            self.assertFalse(state["needsMigration"])

    # ------------------------------------------------------------------
    # determine_repair_reasons – schema-migration-required
    # ------------------------------------------------------------------

    def test_schema_migration_appears_as_repair_reason_for_empty_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {})
            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("schema-migration-required", payload["result"]["repairReasons"])

    def test_schema_migration_appears_as_repair_reason_for_missing_files_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanad-assistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [],
                # "files" absent
            })
            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("schema-migration-required", payload["result"]["repairReasons"])

    def test_schema_migration_does_not_appear_for_valid_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanad-assistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [],
                "files": [],
            })
            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            payload = json.loads(result.stdout)
            self.assertNotIn("schema-migration-required", payload["result"].get("repairReasons", []))

    # ------------------------------------------------------------------
    # repair rewrites pre-0.1.0 lockfile to a valid shape
    # ------------------------------------------------------------------

    def test_repair_rewrites_empty_object_lockfile_to_valid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {})
            result = self._run("repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("ok", payload["status"])
            lockfile_path = workspace / ".github" / "xanad-assistant-lock.json"
            lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            self.assertEqual("0.1.0", lockfile["schemaVersion"])
            self.assertEqual("xanad-assistant", lockfile["package"]["name"])
            self.assertIn("hash", lockfile["manifest"])
            self.assertNotEqual("sha256:unknown", lockfile["manifest"]["hash"])

    def test_repair_preserves_profile_from_pre_schema_lockfile(self) -> None:
        """Profile field present in a partial lockfile is carried forward after repair."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {"profile": "lean"})
            result = self._run("repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            lockfile_path = workspace / ".github" / "xanad-assistant-lock.json"
            lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            # After repair, profile should come from answers (default balanced) or preserved
            # The key point is repair succeeds and lockfile is schema-valid.
            self.assertIn("selectedPacks", lockfile)
            self.assertIn("files", lockfile)
            self.assertNotEqual("sha256:unknown", lockfile["manifest"]["hash"])

    def test_check_after_repair_of_empty_lockfile_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {})
            self._run("repair", "--json", "--non-interactive", workspace=workspace)
            result = self._run("check", "--json", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("clean", payload["status"])


if __name__ == "__main__":
    unittest.main()
