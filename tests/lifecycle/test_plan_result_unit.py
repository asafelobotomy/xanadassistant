"""Unit tests for plan result, PlanB, and inspect helpers."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]


def _minimal_context(
    workspace: Path,
    install_state: str = "not-installed",
    lockfile_state: dict | None = None,
    legacy_version_state: dict | None = None,
) -> dict:
    """Build a minimal context dict for testing plan/inspect functions."""
    from scripts.lifecycle._xanad._loader import load_manifest, load_json, load_optional_json
    from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
    from pathlib import Path as _Path
    policy = load_json(REPO_ROOT / DEFAULT_POLICY_PATH)
    manifest = load_manifest(REPO_ROOT, policy)
    return {
        "workspace": str(workspace),
        "packageRoot": REPO_ROOT,
        "policy": policy,
        "metadata": {},
        "metadataArtifacts": {},
        "artifacts": {},
        "installState": install_state,
        "installPaths": {},
        "existingSurfaces": {},
        "manifest": manifest,
        "manifestWithStatus": None,
        "warnings": [],
        "lockfileState": lockfile_state or {
            "present": False, "malformed": False, "path": ".github/xanadAssistant-lock.json",
            "data": None, "needsMigration": False, "profile": None, "selectedPacks": [],
            "ownershipBySurface": {}, "files": [], "skippedManagedFiles": [],
            "unknownValues": {}, "originalPackageName": None,
        },
        "legacyVersionState": legacy_version_state or {
            "present": False, "malformed": False,
            "path": ".github/copilot-version.md", "data": None,
        },
        "successorMigrationTargets": [],
    }


# ---------------------------------------------------------------------------
# _plan_c.py — determine_repair_reasons and seeding functions
# ---------------------------------------------------------------------------

class PlanBTests(unittest.TestCase):

    def test_build_plan_result_unsupported_mode(self):
        """_plan_b.py line 129: unsupported mode returns not-implemented payload."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            result = build_plan_result(ws, REPO_ROOT, "not-a-real-mode", None, True)
        self.assertEqual("plan", result["command"])
        self.assertEqual("not-implemented", result["status"])

    def test_build_plan_result_repair_on_not_installed_raises(self):
        """_plan_b.py lines 144-145: repair on not-installed workspace raises."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            with self.assertRaises(LifecycleCommandError) as ctx:
                build_plan_result(ws, REPO_ROOT, "repair", None, True)
        self.assertEqual("inspection_failure", ctx.exception.code)

    def test_build_plan_result_factory_restore_on_not_installed_raises(self):
        """_plan_b.py line 165: factory-restore on not-installed raises."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            with self.assertRaises(LifecycleCommandError) as ctx:
                build_plan_result(ws, REPO_ROOT, "factory-restore", None, True)
        self.assertEqual("inspection_failure", ctx.exception.code)

    def test_build_plan_result_setup_on_fresh_workspace(self):
        """_plan_b.py: setup mode on fresh workspace returns ok or approval-required payload."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            result = build_plan_result(ws, REPO_ROOT, "setup", None, True)
        self.assertEqual("plan", result["command"])
        self.assertEqual("setup", result["mode"])
        self.assertIn(result["status"], ("ok", "approval-required"))

    def test_build_planned_lockfile_with_mixed_actions(self):
        """_plan_b.py lines 67-70, 88, 97: lockfile built from mix of action types."""
        from scripts.lifecycle._xanad._plan_b import build_planned_lockfile
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        real_entry = entries[0]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            context = _minimal_context(ws)
            context["manifest"] = manifest
            retired_target = ".github/agents/old-agent.md"
            actions = [
                {
                    "id": "migration.cleanup.test",
                    "target": retired_target,
                    "action": "archive-retired",
                    "ownershipMode": None,
                    "strategy": "archive-retired",
                },
                {
                    "id": real_entry["id"],
                    "target": real_entry["target"],
                    "action": "add",
                    "strategy": real_entry.get("strategy", "copy"),
                    "ownershipMode": "local",
                },
            ]
            # archiveTargets maps the retired target so line 97 is covered
            backup_plan = {
                "required": False, "root": None, "targets": [],
                "archiveTargets": [
                    {"target": retired_target, "archivePath": f".xanad-archive/{retired_target}"},
                ],
            }
            lockfile = build_planned_lockfile(
                ws, context, {}, {}, {}, actions, [], [retired_target], backup_plan,
            )
        retired = lockfile["contents"]["retiredManagedFiles"]
        self.assertEqual(1, len(retired))
        self.assertEqual("archived", retired[0]["action"])
        file_records = lockfile["contents"]["files"]
        self.assertTrue(len(file_records) > 0)

    def test_build_lockfile_package_info_includes_ref_from_session(self):
        """_plan_b.py line 43: info['ref'] is set when session_source_info has 'ref'."""
        from scripts.lifecycle._xanad._plan_b import _build_lockfile_package_info
        from scripts.lifecycle._xanad._errors import _State
        original = _State.session_source_info
        try:
            _State.session_source_info = {
                "packageRoot": str(REPO_ROOT),
                "ref": "main",
                "source": "owner/repo",
            }
            info = _build_lockfile_package_info()
        finally:
            _State.session_source_info = original
        self.assertEqual("main", info.get("ref"))

    def test_build_plan_result_unknown_answer_ids_warns(self):
        """_plan_b.py lines 181-185: unknown answer IDs trigger warning."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_file = Path(tmp) / "answers.json"
            answers_file.write_text('{"unknown-key-xyz": "value"}', encoding="utf-8")
            result = build_plan_result(ws, REPO_ROOT, "setup", str(answers_file), True)
        warning_codes = [w["code"] for w in result.get("warnings", [])]
        self.assertIn("unknown_answer_ids_ignored", warning_codes)

    def test_build_planned_lockfile_skips_action_with_unknown_id(self):
        """_plan_b.py line 69: continue when manifest_entry is None for non-archive action."""
        from scripts.lifecycle._xanad._plan_b import build_planned_lockfile
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            context = _minimal_context(ws)
            context["manifest"] = manifest
            # Action with an ID that does NOT exist in manifest
            actions = [{
                "id": "does-not-exist-in-manifest",
                "action": "add",
                "target": "some/file.md",
                "ownershipMode": "local",
                "strategy": "copy",
            }]
            backup_plan = {"required": False, "root": None, "targets": [], "archiveTargets": []}
            lockfile = build_planned_lockfile(ws, context, {}, {}, {}, actions, [], [], backup_plan)
        self.assertEqual([], lockfile["contents"]["files"])


# ---------------------------------------------------------------------------
# _inspect_helpers.py
# ---------------------------------------------------------------------------

class InspectHelpersTests(unittest.TestCase):

    def _make_annotated_entry(self, entry: dict, status: str) -> dict:
        result = dict(entry)
        result["status"] = status
        return result

    def test_annotate_manifest_entries_skips_non_local_ownership(self):
        """_inspect_helpers.py lines 42-43: ownership != local sets condition-not-selected status."""
        from scripts.lifecycle._xanad._inspect_helpers import annotate_manifest_entries
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files")
        first_surface = entries[0]["surface"]
        ownership = {first_surface: "plugin-backed-copilot-format"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            result = annotate_manifest_entries(ws, REPO_ROOT, manifest, ownership, {}, {})
        skipped = [e for e in (result or {}).get("managedFiles", [])
                   if e.get("skipReason") == "plugin-backed-ownership"]
        self.assertTrue(len(skipped) > 0)

    def test_annotate_manifest_entries_condition_not_selected(self):
        """_inspect_helpers.py lines 42-43: condition not selected sets skip status."""
        from scripts.lifecycle._xanad._inspect_helpers import annotate_manifest_entries
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        entries = manifest.get("managedFiles", [])
        conditional = next((e for e in entries if e.get("requiredWhen")), None)
        if not conditional:
            self.skipTest("No conditional entries")
        # Set all surfaces to local, but leave resolved_answers empty
        ownership = {e["surface"]: "local" for e in entries}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            result = annotate_manifest_entries(ws, REPO_ROOT, manifest, ownership, {}, {})
        skipped = [e for e in (result or {}).get("managedFiles", [])
                   if e.get("skipReason") == "condition-not-selected"]
        self.assertTrue(len(skipped) > 0)

    def test_classify_manifest_entries_retired_file_counts(self):
        """_inspect_helpers.py lines 86-87: retired file that exists is counted."""
        from scripts.lifecycle._xanad._inspect_helpers import classify_manifest_entries
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        retired = manifest.get("retiredFiles", [])
        if not retired:
            self.skipTest("No retired files in manifest")
        # Build annotated manifest with all managed files as "clean"
        annotated = dict(manifest)
        annotated["managedFiles"] = [dict(e, status="clean") for e in manifest.get("managedFiles", [])]
        first_retired_target = retired[0]["target"]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create the retired file so it gets counted
            target = ws / first_retired_target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Retired", encoding="utf-8")
            counts, entries, managed_targets = classify_manifest_entries(ws, annotated)
        self.assertGreater(counts["retired"], 0)

    def test_collect_unmanaged_files_finds_unmanaged_in_managed_dir(self):
        """_inspect_helpers.py lines 94, 102, 112: unmanaged file is returned."""
        from scripts.lifecycle._xanad._inspect_helpers import collect_unmanaged_files
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        managed_targets = {e["target"] for e in manifest.get("managedFiles", [])}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create an unmanaged file in a managed directory
            agents_dir = ws / ".github" / "agents"
            agents_dir.mkdir(parents=True)
            unmanaged = agents_dir / "not-in-manifest.md"
            unmanaged.write_text("# Unmanaged", encoding="utf-8")
            result = collect_unmanaged_files(ws, manifest, managed_targets)
        self.assertIn(".github/agents/not-in-manifest.md", result)

    def test_collect_successor_migration_files_finds_migration_targets(self):
        """_inspect_helpers.py lines 149, 154: files in successor roots are returned."""
        from scripts.lifecycle._xanad._inspect_helpers import collect_successor_migration_files
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        lockfile_state = {"originalPackageName": "copilot-instructions-template", "data": {}}
        legacy_state = {"present": True, "malformed": False, "data": {"version": "0.9.0"}}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            agents_dir = ws / ".github" / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "old-agent.agent.md").write_text("# Old agent", encoding="utf-8")
            result = collect_successor_migration_files(ws, manifest, lockfile_state, legacy_state)
        self.assertIn(".github/agents/old-agent.agent.md", result)

    def test_collect_successor_migration_files_finds_mcp_json(self):
        """_inspect_helpers.py line 154: .mcp.json in SUCCESSOR_MIGRATION_FILES is found."""
        from scripts.lifecycle._xanad._inspect_helpers import collect_successor_migration_files
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        lockfile_state = {"originalPackageName": "copilot-instructions-template", "data": {}}
        legacy_state = {"present": False, "malformed": False, "data": None}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create .mcp.json (a SUCCESSOR_MIGRATION_FILE)
            (ws / ".mcp.json").write_text('{"mcpServers":{}}', encoding="utf-8")
            result = collect_successor_migration_files(ws, manifest, lockfile_state, legacy_state)
        self.assertIn(".mcp.json", result)

    def test_classify_manifest_entries_returns_empty_when_manifest_none(self):
        """_inspect_helpers.py line 71: early return when manifest is None."""
        from scripts.lifecycle._xanad._inspect_helpers import classify_manifest_entries
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            counts, entries, managed = classify_manifest_entries(ws, None)
        self.assertEqual(0, sum(counts.values()))
        self.assertEqual([], entries)
        self.assertEqual(set(), managed)

    def test_collect_unmanaged_files_returns_empty_when_manifest_none(self):
        """_inspect_helpers.py line 94: early return [] when manifest is None."""
        from scripts.lifecycle._xanad._inspect_helpers import collect_unmanaged_files
        result = collect_unmanaged_files(Path("/tmp"), None, set())
        self.assertEqual([], result)

    def test_collect_unmanaged_files_skips_root_candidate_dir(self):
        """_inspect_helpers.py line 102: candidate in {'', '.'} is skipped."""
        from scripts.lifecycle._xanad._inspect_helpers import collect_unmanaged_files
        # A managed target with no directory component → candidate dir = "."
        manifest = {"managedFiles": [], "retiredFiles": []}
        managed_targets = {"root-level-file.md"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create a file at root level — it should be skipped (root dir "." is excluded)
            (ws / "root-level-file.md").write_text("# Root", encoding="utf-8")
            result = collect_unmanaged_files(ws, manifest, managed_targets)
        # Root-level candidate dirs are skipped, so no files from "." are reported
        self.assertEqual([], result)



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
