"""Unit tests for build_setup_plan_actions and related functions."""
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

class PlanATests(unittest.TestCase):

    def _get_manifest(self):
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        return load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}

    def _get_policy(self):
        from scripts.lifecycle._xanad._loader import load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        return load_json(REPO_ROOT / DEFAULT_POLICY_PATH)

    def test_resolve_ownership_by_surface_returns_empty_when_manifest_none(self):
        """_plan_a.py line 73: early return when manifest is None."""
        from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface
        result = resolve_ownership_by_surface({}, None, {}, {})
        self.assertEqual({}, result)

    def test_resolve_ownership_by_surface_raises_for_invalid_ownership(self):
        """_plan_a.py line 40: raise when resolved_ownership not in entry['ownership']."""
        from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        # Force invalid ownership via policy default
        policy = self._get_policy()
        first_surface = entries[0]["surface"]
        policy["ownershipDefaults"][first_surface] = "invalid-ownership-xyz"
        with self.assertRaises(LifecycleCommandError):
            resolve_ownership_by_surface(policy, manifest, {}, {})

    def test_resolve_ownership_by_surface_uses_existing_ownership(self):
        """_plan_a.py line 27: existing_ownership from lockfile_state is used."""
        from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        policy = self._get_policy()
        first_entry = entries[0]
        lockfile_state = {"ownershipBySurface": {first_entry["surface"]: first_entry["ownership"][0]}}
        result = resolve_ownership_by_surface(policy, manifest, lockfile_state, {})
        self.assertIn(first_entry["surface"], result)

    def test_build_setup_plan_actions_returns_empty_when_manifest_none(self):
        """_plan_a.py line 73: early return when manifest is None."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            writes, actions, skipped, retired = build_setup_plan_actions(
                ws, REPO_ROOT, None, {}, {}, {},
            )
        self.assertEqual([], actions)

    def test_build_setup_plan_actions_skips_non_local_ownership(self):
        """_plan_a.py lines 87-93: entry with non-local ownership mode is skipped."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        first_surface = entries[0]["surface"]
        # Map the first surface to non-local ownership
        ownership_by_surface = {first_surface: "plugin-backed-copilot-format"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            writes, actions, skipped, retired = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership_by_surface, {}, {},
            )
        # At least one action should be skipped due to non-local ownership
        skipped_ids = [s["id"] for s in skipped if s.get("reason") == "plugin-backed-ownership"]
        self.assertTrue(len(skipped_ids) > 0)

    def test_build_setup_plan_actions_skips_condition_not_selected(self):
        """_plan_a.py lines 106-113: entry whose requiredWhen condition fails is skipped."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        entries = manifest.get("managedFiles", []) if manifest else []
        # Find entry with requiredWhen condition
        conditional_entry = next((e for e in entries if e.get("requiredWhen")), None)
        if not conditional_entry:
            self.skipTest("No conditional entries in manifest")
        # Set all surfaces to local ownership, but leave resolved_answers empty
        # so the requiredWhen condition fails
        ownership_by_surface = {conditional_entry["surface"]: "local"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _, _, skipped, _ = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership_by_surface, {}, {},
            )
        skipped_ids = [s["id"] for s in skipped if s.get("reason") == "condition-not-selected"]
        self.assertTrue(len(skipped_ids) > 0)

    def test_build_setup_plan_actions_copy_if_missing_present_skips(self):
        """_plan_a.py lines 126-128: copy-if-missing entry skipped when target exists."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        # Build a synthetic manifest with a copy-if-missing entry
        synthetic_manifest = {
            "managedFiles": [
                {
                    "id": "test.copy-if-missing",
                    "surface": "test",
                    "target": ".github/test-file.md",
                    "source": "template/copilot-instructions.md",
                    "strategy": "copy-if-missing",
                    "ownership": ["local"],
                    "hash": "sha256:fake",
                    "tokens": [],
                    "chmod": "none",
                }
            ],
            "retiredFiles": [],
        }
        ownership = {"test": "local"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create the target file so copy-if-missing skips it
            target = ws / ".github" / "test-file.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Existing content", encoding="utf-8")
            _, _, skipped, _ = build_setup_plan_actions(
                ws, REPO_ROOT, synthetic_manifest, ownership, {}, {},
            )
        skipped_ids = [s["id"] for s in skipped if s.get("reason") == "copy-if-missing-present"]
        self.assertIn("test.copy-if-missing", skipped_ids)

    def test_build_setup_plan_actions_includes_retired_files(self):
        """_plan_a.py lines 148-150: retired file that exists is included in actions."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        retired = manifest.get("retiredFiles", []) if manifest else []
        if not retired:
            self.skipTest("No retired files in manifest")
        first_retired = retired[0]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create the retired file in workspace
            target = ws / first_retired["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Retired content", encoding="utf-8")
            _, actions, _, retired_targets = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, {}, {}, {},
            )
        archive_actions = [a for a in actions if a["action"] == "archive-retired"]
        self.assertTrue(len(archive_actions) > 0)
        self.assertIn(first_retired["target"], retired_targets)

    def test_classify_plan_conflicts_managed_drift(self):
        """_plan_a.py lines 161-163: managed drift conflict when replace/merge actions exist."""
        from scripts.lifecycle._xanad._plan_a import classify_plan_conflicts
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            context = _minimal_context(ws)
            actions = [
                {"action": "replace", "target": ".github/copilot-instructions.md", "id": "test"},
            ]
            conflicts, warnings = classify_plan_conflicts(ws, context, actions, [])
        conflict_classes = [c["class"] for c in conflicts]
        self.assertIn("managed-drift", conflict_classes)

    def test_classify_plan_conflicts_unmanaged_lookalike(self):
        """_plan_a.py lines 170-175: unmanaged file in managed dir creates conflict."""
        from scripts.lifecycle._xanad._plan_a import classify_plan_conflicts
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create an unmanaged file in a managed directory
            agents_dir = ws / ".github" / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "unmanaged-file.md").write_text("# Unmanaged", encoding="utf-8")
            context = _minimal_context(ws)
            context["manifest"] = manifest
            conflicts, warnings = classify_plan_conflicts(ws, context, [], [])
        conflict_classes = [c["class"] for c in conflicts]
        self.assertIn("unmanaged-lookalike", conflict_classes)

    def test_classify_plan_conflicts_malformed_state(self):
        """_plan_a.py lines 182-184: malformed lockfile creates malformed-managed-state conflict."""
        from scripts.lifecycle._xanad._plan_a import classify_plan_conflicts
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            context = _minimal_context(ws)
            context["lockfileState"]["malformed"] = True
            conflicts, warnings = classify_plan_conflicts(ws, context, [], [])
        conflict_classes = [c["class"] for c in conflicts]
        self.assertIn("malformed-managed-state", conflict_classes)

    def test_classify_plan_conflicts_retired_file_present(self):
        """_plan_a.py lines 196-197: retired file in workspace creates conflict."""
        from scripts.lifecycle._xanad._plan_a import classify_plan_conflicts
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            context = _minimal_context(ws)
            conflicts, warnings = classify_plan_conflicts(ws, context, [], [".github/old-file.md"])
        conflict_classes = [c["class"] for c in conflicts]
        self.assertIn("retired-file-present", conflict_classes)

    def test_verify_manifest_integrity_lockfile_not_present(self):
        """_plan_a.py: lockfile not present → (True, None)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        ok, reason = verify_manifest_integrity(REPO_ROOT, {"present": False, "malformed": False})
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_manifest_hash_mismatch(self):
        """_plan_a.py line 225: hash mismatch returns (False, reason)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        lockfile_state = {
            "present": True, "malformed": False,
            "data": {"manifest": {"hash": "sha256:totally-wrong-hash"}},
        }
        ok, reason = verify_manifest_integrity(REPO_ROOT, lockfile_state)
        self.assertFalse(ok)
        self.assertIn("mismatch", reason)

    def test_verify_manifest_integrity_hash_matches(self):
        """_plan_a.py line 229: hash match returns (True, None)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        from scripts.lifecycle._xanad._merge import sha256_json
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        current_hash = sha256_json(manifest) if manifest else ""
        lockfile_state = {
            "present": True, "malformed": False,
            "data": {"manifest": {"hash": current_hash}},
        }
        ok, reason = verify_manifest_integrity(REPO_ROOT, lockfile_state)
        self.assertTrue(ok)
        self.assertIsNone(reason)


# ---------------------------------------------------------------------------
# _plan_b.py — build_plan_result edge cases and build_planned_lockfile
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
