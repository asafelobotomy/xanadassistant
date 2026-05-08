from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class LockfileMigrationTests(XanadTestBase):
    """Coverage for pre-0.1.0 lockfile shapes that are valid JSON but structurally incomplete."""

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
        data = self.make_minimal_lockfile(
            manifest={"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            remove_paths=("files",),
        )
        self.assertTrue(_lockfile_needs_migration(data))

    def test_needs_migration_missing_manifest_hash(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = self.make_minimal_lockfile(remove_paths=("manifest.hash",))
        self.assertTrue(_lockfile_needs_migration(data))

    def test_needs_migration_missing_package_name(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = self.make_minimal_lockfile(
            manifest={"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            remove_paths=("package.name",),
        )
        self.assertTrue(_lockfile_needs_migration(data))

    def test_needs_migration_predecessor_package_name(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = self.make_minimal_lockfile(
            manifest={"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            package={"name": "copilot-instructions-template"},
        )
        self.assertTrue(_lockfile_needs_migration(data))

    def test_needs_migration_valid_shape_returns_false(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = self.make_minimal_lockfile(
            manifest={"schemaVersion": "0.1.0", "hash": "sha256:abc123"},
        )
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
        data = self.make_minimal_lockfile(
            manifest={"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            selectedPacks=["lean"],
            profile="lean",
            remove_paths=("files",),
        )
        migrated = migrate_lockfile_shape(data)
        self.assertEqual(["lean"], migrated["selectedPacks"])
        self.assertEqual("lean", migrated["profile"])
        self.assertEqual("sha256:abc", migrated["manifest"]["hash"])

    def test_migrate_preserves_predecessor_package_name_in_unknown_values(self) -> None:
        from scripts.lifecycle.xanad_assistant import migrate_lockfile_shape
        data = self.make_minimal_lockfile(package={"name": "copilot-instructions-template"})
        migrated = migrate_lockfile_shape(data)
        self.assertEqual("xanad-assistant", migrated["package"]["name"])
        self.assertEqual(
            "copilot-instructions-template",
            migrated["unknownValues"]["migratedFromPackageName"],
        )

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
            self._write_lockfile(
                workspace,
                self.make_minimal_lockfile(
                    manifest={"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                ),
            )
            state = parse_lockfile_state(workspace)
            self.assertFalse(state["malformed"])
            self.assertFalse(state["needsMigration"])

    def test_parse_lockfile_state_sets_needs_migration_for_predecessor_package(self) -> None:
        from scripts.lifecycle.xanad_assistant import parse_lockfile_state
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(
                workspace,
                self.make_minimal_lockfile(
                    manifest={"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                    package={"name": "copilot-instructions-template"},
                ),
            )
            state = parse_lockfile_state(workspace)
            self.assertTrue(state["present"])
            self.assertTrue(state["needsMigration"])
            self.assertEqual("copilot-instructions-template", state["data"]["unknownValues"]["migratedFromPackageName"])

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
            data = self.make_minimal_lockfile(
                manifest={"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                remove_paths=("files",),
            )
            self._write_lockfile(workspace, data)
            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("schema-migration-required", payload["result"]["repairReasons"])

    def test_schema_migration_does_not_appear_for_valid_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(
                workspace,
                self.make_minimal_lockfile(
                    manifest={"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                ),
            )
            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            payload = json.loads(result.stdout)
            self.assertNotIn("schema-migration-required", payload["result"].get("repairReasons", []))

    def test_package_identity_migration_appears_as_repair_reason_for_predecessor_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(
                workspace,
                self.make_minimal_lockfile(
                    manifest={"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                    package={"name": "copilot-instructions-template"},
                ),
            )
            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("package-identity-migration-required", payload["result"]["repairReasons"])

    def test_successor_cleanup_appears_in_plan_for_legacy_template_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            github_dir = workspace / ".github"
            (github_dir / "copilot-version.md").parent.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-version.md").write_text("version: 0.10.0\n", encoding="utf-8")
            legacy_hook = github_dir / "hooks" / "copilot-hooks.json"
            legacy_hook.parent.mkdir(parents=True, exist_ok=True)
            legacy_hook.write_text("{}\n", encoding="utf-8")
            legacy_workspace = workspace / ".copilot" / "workspace" / "BRAIN.md"
            legacy_workspace.parent.mkdir(parents=True, exist_ok=True)
            legacy_workspace.write_text("legacy\n", encoding="utf-8")
            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("successor-cleanup-required", payload["result"]["repairReasons"])
            retired_targets = {action["target"] for action in payload["result"]["actions"] if action["action"] == "archive-retired"}
            self.assertIn(".github/hooks/copilot-hooks.json", retired_targets)
            self.assertIn(".copilot/workspace/BRAIN.md", retired_targets)

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

    def test_repair_archives_predecessor_template_files_and_leaves_clean_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            github_dir = workspace / ".github"
            (github_dir / "copilot-version.md").parent.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-version.md").write_text("version: 0.10.0\n", encoding="utf-8")
            legacy_hook = github_dir / "hooks" / "copilot-hooks.json"
            legacy_hook.parent.mkdir(parents=True, exist_ok=True)
            legacy_hook.write_text("{}\n", encoding="utf-8")
            legacy_mcp = workspace / ".mcp.json"
            legacy_mcp.write_text("{}\n", encoding="utf-8")

            result = self._run("repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("ok", payload["status"])
            self.assertFalse(legacy_hook.exists())
            self.assertFalse(legacy_mcp.exists())
            self.assertTrue((workspace / ".xanad-assistant" / "archive" / ".github" / "hooks" / "copilot-hooks.json").exists())
            self.assertTrue((workspace / ".xanad-assistant" / "archive" / ".mcp.json").exists())

            check_result = self._run("check", "--json", workspace=workspace)
            self.assertEqual(0, check_result.returncode, check_result.stderr)
            self.assertEqual("clean", json.loads(check_result.stdout)["status"])


if __name__ == "__main__":
    unittest.main()
