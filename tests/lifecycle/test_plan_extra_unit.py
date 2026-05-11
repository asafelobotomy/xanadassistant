"""Unit tests for plan edge cases, successor plans, and interview extras."""
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

class PlanAExtraTests(unittest.TestCase):
    """Extra tests for _plan_a.py lines not covered by PlanATests."""

    def _get_manifest(self):
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        return load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}

    def _get_policy(self):
        from scripts.lifecycle._xanad._loader import load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        return load_json(REPO_ROOT / DEFAULT_POLICY_PATH)

    def test_build_conflict_summary_counts_by_class(self):
        """_plan_a.py lines 196-197: build_conflict_summary counts each class."""
        from scripts.lifecycle._xanad._plan_a import build_conflict_summary
        conflicts = [
            {"class": "managed-drift", "target": "a"},
            {"class": "managed-drift", "target": "b"},
            {"class": "unmanaged-lookalike", "target": "c"},
        ]
        summary = build_conflict_summary(conflicts)
        self.assertEqual(2, summary["managed-drift"])
        self.assertEqual(1, summary["unmanaged-lookalike"])

    def test_resolve_ownership_by_surface_uses_entry_first_ownership_when_not_in_defaults(self):
        """_plan_a.py line 27: surface not in policy ownershipDefaults → uses entry.ownership[0]."""
        from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        first_entry = entries[0]
        # Build policy WITHOUT the first surface in ownershipDefaults
        policy = self._get_policy()
        modified_defaults = {k: v for k, v in policy.get("ownershipDefaults", {}).items()
                             if k != first_entry["surface"]}
        modified_policy = dict(policy, ownershipDefaults=modified_defaults)
        result = resolve_ownership_by_surface(modified_policy, manifest, {}, {})
        # First surface should use entry.ownership[0]
        self.assertIn(first_entry["surface"], result)
        self.assertEqual(first_entry["ownership"][0], result[first_entry["surface"]])

    def test_build_setup_plan_actions_file_exists_checks_hash(self):
        """_plan_a.py lines 109-113: file exists with non-copy-if-missing strategy → hash check."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        copy_entry = next(
            (e for e in entries if e.get("strategy") not in {"merge-json-object", "preserve-marked-markdown-blocks", "copy-if-missing"}),
            None,
        )
        if copy_entry is None:
            self.skipTest("No suitable copy-strategy entries in manifest")
        policy = self._get_policy()
        ownership = {copy_entry["surface"]: "local"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create the target file with different content from source → hashes differ → replace action
            target = ws / copy_entry["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Different content from source", encoding="utf-8")
            writes, actions, skipped, retired = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership, {}, {},
            )
        action_ids = [a["id"] for a in actions]
        self.assertIn(copy_entry["id"], action_ids)
        # The action should be "replace" (not "add") since file exists
        entry_actions = [a for a in actions if a["id"] == copy_entry["id"]]
        self.assertTrue(all(a["action"] == "replace" for a in entry_actions))

    def test_build_setup_plan_actions_force_reinstall_replaces_matching_file(self):
        """_plan_a.py line 107: force_reinstall=True skips hash check and uses replace/merge."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        copy_entry = next(
            (e for e in entries if e.get("strategy") not in {"merge-json-object", "preserve-marked-markdown-blocks", "copy-if-missing"} and not e.get("tokens")),
            None,
        )
        if copy_entry is None:
            self.skipTest("No tokenless copy-strategy entries in manifest")
        ownership = {copy_entry["surface"]: "local"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ws / copy_entry["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            # Write identical content — but force_reinstall=True bypasses hash check
            source_path = REPO_ROOT / copy_entry["source"]
            import shutil
            shutil.copy2(source_path, target)
            writes, actions, skipped, retired = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership, {}, {}, force_reinstall=True,
            )
        action_ids = [a["id"] for a in actions]
        self.assertIn(copy_entry["id"], action_ids)
        # With force_reinstall, action should be "replace" even with identical content
        entry_actions = [a for a in actions if a["id"] == copy_entry["id"]]
        self.assertTrue(all(a["action"] == "replace" for a in entry_actions))


        """_plan_a.py line 112: continue when installed_hash == expected_hash."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        copy_entry = next(
            (e for e in entries if e.get("strategy") not in {"merge-json-object", "preserve-marked-markdown-blocks", "copy-if-missing"} and not e.get("tokens")),
            None,
        )
        if copy_entry is None:
            self.skipTest("No tokenless copy-strategy entries in manifest")
        ownership = {copy_entry["surface"]: "local"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ws / copy_entry["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            # Write the exact same content as the source
            source_path = REPO_ROOT / copy_entry["source"]
            import shutil
            shutil.copy2(source_path, target)
            writes, actions, skipped, retired = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership, {}, {},
            )
        # The entry should be skipped (hashes match)
        action_ids = [a["id"] for a in actions]
        self.assertNotIn(copy_entry["id"], action_ids)

    def test_verify_manifest_integrity_lockfile_data_not_dict(self):
        """_plan_a.py line 216: lockfile_data is not a dict → return (True, None)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        lockfile_state = {
            "present": True, "malformed": False,
            "data": "not-a-dict",
        }
        ok, reason = verify_manifest_integrity(REPO_ROOT, lockfile_state)
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_no_recorded_hash(self):
        """_plan_a.py line 219: no recorded hash → return (True, None)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        lockfile_state = {
            "present": True, "malformed": False,
            "data": {"manifest": {}},  # no "hash" key
        }
        ok, reason = verify_manifest_integrity(REPO_ROOT, lockfile_state)
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_no_policy_returns_ok(self):
        """_plan_a.py line 222: policy not found → return (True, None)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        with tempfile.TemporaryDirectory() as tmp:
            empty_root = Path(tmp)
            lockfile_state = {
                "present": True, "malformed": False,
                "data": {"manifest": {"hash": "sha256:some-hash"}},
            }
            ok, reason = verify_manifest_integrity(empty_root, lockfile_state)
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_manifest_not_found(self):
        """_plan_a.py line 225: manifest not found → return (False, reason)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            # Create a policy file but no manifest
            import json as _json
            policy = {"surfaces": [], "managedSurfaces": [], "ownershipDefaults": {},
                      "defaultProfile": "balanced", "canonicalSurfaces": []}
            policy_path = fake_root / "template" / "setup" / "install-policy.json"
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(_json.dumps(policy), encoding="utf-8")
            lockfile_state = {
                "present": True, "malformed": False,
                "data": {"manifest": {"hash": "sha256:some-hash"}},
            }
            # Patch load_manifest to return None to simulate missing manifest
            with patch("scripts.lifecycle._xanad._plan_a.load_manifest", return_value=None):
                ok, reason = verify_manifest_integrity(fake_root, lockfile_state)
        self.assertFalse(ok)
        self.assertIn("Manifest not found", reason)



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
