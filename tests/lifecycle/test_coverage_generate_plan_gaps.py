"""Tests for generate-manifest, plan-utils, and source coverage gaps."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]


class GenerateManifestGapTests(unittest.TestCase):
    def _load_real_policy(self) -> dict:
        import copy
        return copy.deepcopy(json.loads(
            (REPO_ROOT / "template" / "setup" / "install-policy.json").read_text()
        ))

    def test_validate_unmanaged_sources_skips_unused_source_root(self):
        """Line 100: source root in sourceRoots but not referenced by any surface → continue."""
        from scripts.lifecycle.generate_manifest import validate_unmanaged_sources
        policy = self._load_real_policy()
        # Add an extra source root that is not referenced by any canonical surface
        policy["sourceRoots"]["orphan-root"] = "docs"
        # Should not raise (the orphan root gets a 'continue' at line 100)
        validate_unmanaged_sources(REPO_ROOT, policy)

    def test_validate_unmanaged_sources_skips_nonexistent_dir(self):
        """Line 103: source root referenced by a surface but directory doesn't exist → continue."""
        from scripts.lifecycle.generate_manifest import validate_unmanaged_sources
        policy = self._load_real_policy()
        # Point an existing surface's source root to a nonexistent dir
        # We need a source root that IS in root_to_surfaces
        # root_to_surfaces is built from canonicalSurfaces
        # Let's find the first canonical surface and point its root to nonexistent path
        first_surface = policy["canonicalSurfaces"][0]
        source_root_key = policy["surfaceSources"][first_surface]["sourceRoot"]
        # Change that source root path to a nonexistent directory
        policy["sourceRoots"][source_root_key] = "nonexistent-dir-xyz"
        # Should not raise (the nonexistent dir gets a 'continue' at line 103)
        validate_unmanaged_sources(REPO_ROOT, policy)

    def test_generate_manifest_raises_on_invalid_ownership_mode(self):
        """Line 151: generate_manifest raises ValueError for unknown ownershipMode."""
        from scripts.lifecycle.generate_manifest import generate_manifest
        policy = self._load_real_policy()
        first_surface = policy["canonicalSurfaces"][0]
        policy["ownershipDefaults"][first_surface] = "invalid-mode-xyz"
        with self.assertRaises(ValueError) as ctx:
            generate_manifest(REPO_ROOT, policy)
        self.assertIn("Unsupported ownership mode", str(ctx.exception))

    def test_generate_manifest_raises_on_invalid_strategy(self):
        """Line 153: generate_manifest raises ValueError for unknown write strategy."""
        from scripts.lifecycle.generate_manifest import generate_manifest
        policy = self._load_real_policy()
        first_surface = policy["canonicalSurfaces"][0]
        policy["strategyDefaults"][first_surface] = "invalid-strategy-xyz"
        with self.assertRaises(ValueError) as ctx:
            generate_manifest(REPO_ROOT, policy)
        self.assertIn("Unsupported write strategy", str(ctx.exception))


# ---------------------------------------------------------------------------
# _plan_utils.py
# ---------------------------------------------------------------------------

class PlanUtilsGapTests(unittest.TestCase):
    def _make_entry(self, strategy: str, source_rel: str = "source.json") -> dict:
        return {
            "strategy": strategy,
            "source": source_rel,
        }

    def test_expected_entry_bytes_merge_json_not_dict_returns_none(self):
        """Line 33: merge-json-object source that is not a dict → None."""
        from scripts.lifecycle._xanad._plan_utils import expected_entry_bytes
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            # Source file is a list, not a dict
            (pkg_root / "source.json").write_text("[1, 2, 3]", encoding="utf-8")
            entry = self._make_entry("merge-json-object")
            result = expected_entry_bytes(pkg_root, entry, {}, target_path=None)
        self.assertIsNone(result)

    def test_expected_entry_bytes_merge_json_target_not_dict_returns_none(self):
        """_plan_utils.py line 41: merge-json-object when target JSON is not a dict → None."""
        from scripts.lifecycle._xanad._plan_utils import expected_entry_bytes
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            (pkg_root / "source.json").write_text('{"a": 1}', encoding="utf-8")
            target = Path(tmp) / "target.json"
            # Target file contains a list (not a dict)
            target.write_text('[1, 2, 3]', encoding="utf-8")
            entry = self._make_entry("merge-json-object")
            result = expected_entry_bytes(pkg_root, entry, {}, target_path=target)
        self.assertIsNone(result)

    def test_expected_entry_bytes_merge_json_json_decode_error_returns_none(self):
        """Lines 38-39: merge-json-object with corrupted target → None."""
        from scripts.lifecycle._xanad._plan_utils import expected_entry_bytes
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            (pkg_root / "source.json").write_text('{"key": "val"}', encoding="utf-8")
            corrupt_target = Path(tmp) / "corrupt.json"
            corrupt_target.write_text("{not valid json", encoding="utf-8")
            entry = self._make_entry("merge-json-object")
            result = expected_entry_bytes(pkg_root, entry, {}, target_path=corrupt_target)
        self.assertIsNone(result)

    def test_expected_entry_bytes_merge_json_existing_and_source_valid(self):
        """Line 41: merge-json-object when both target and source are valid dicts."""
        from scripts.lifecycle._xanad._plan_utils import expected_entry_bytes
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            (pkg_root / "source.json").write_text('{"a": 1}', encoding="utf-8")
            target = Path(tmp) / "target.json"
            target.write_text('{"b": 2}', encoding="utf-8")
            entry = self._make_entry("merge-json-object")
            result = expected_entry_bytes(pkg_root, entry, {}, target_path=target)
        self.assertIsNotNone(result)
        data = json.loads(result)
        self.assertIn("a", data)
        self.assertIn("b", data)

    def test_expected_entry_hash_returns_none_when_bytes_none(self):
        """Line 63: expected_entry_hash returns None when expected_entry_bytes returns None."""
        from scripts.lifecycle._xanad._plan_utils import expected_entry_hash
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            # merge-json-object with non-dict source → bytes is None → hash is None
            (pkg_root / "source.json").write_text("[1, 2]", encoding="utf-8")
            entry = self._make_entry("merge-json-object")
            result = expected_entry_hash(pkg_root, entry, {}, target_path=None)
        self.assertIsNone(result)

    def test_build_backup_plan_not_required(self):
        """Line 91: backup_required=False returns empty backup plan."""
        from scripts.lifecycle._xanad._plan_utils import build_backup_plan
        result = build_backup_plan({}, [], backup_required=False)
        self.assertFalse(result["required"])
        self.assertIsNone(result["root"])
        self.assertEqual([], result["targets"])

    def test_build_backup_plan_with_archive_retired_action(self):
        """Lines 105+: archive-retired action with archive_root → archive_targets populated."""
        from scripts.lifecycle._xanad._plan_utils import build_backup_plan
        policy = {"retiredFilePolicy": {"archiveRoot": ".archive"}}
        actions = [
            {"action": "archive-retired", "target": "old-file.md"},
        ]
        result = build_backup_plan(policy, actions, backup_required=True)
        self.assertTrue(result["required"])
        self.assertEqual(1, len(result["archiveTargets"]))

    def test_build_backup_plan_with_replace_action_adds_backup_target(self):
        """_plan_utils.py line 105: replace action → backup_targets populated."""
        from scripts.lifecycle._xanad._plan_utils import build_backup_plan
        policy = {}
        actions = [
            {"action": "replace", "target": ".github/copilot-instructions.md"},
        ]
        result = build_backup_plan(policy, actions, backup_required=True)
        self.assertTrue(result["required"])
        self.assertEqual(1, len(result["targets"]))

    def test_build_backup_plan_with_archive_retired_report_only(self):
        """Line 105: archive-retired with report-retired strategy → NOT in archive_targets."""
        from scripts.lifecycle._xanad._plan_utils import build_backup_plan
        policy = {"retiredFilePolicy": {"archiveRoot": ".archive"}}
        actions = [
            {"action": "archive-retired", "target": "old-file.md", "strategy": "report-retired"},
        ]
        result = build_backup_plan(policy, actions, backup_required=True)
        self.assertEqual(0, len(result["archiveTargets"]))

    def test_build_token_plan_summary_populated(self):
        """Line 117+: build_token_plan_summary with matching tokens."""
        from scripts.lifecycle._xanad._plan_utils import build_token_plan_summary
        policy = {
            "tokenRules": [
                {"token": "{{WORKSPACE_NAME}}", "required": True},
            ]
        }
        actions = [
            {"action": "add", "target": ".github/copilot-instructions.md",
             "tokens": ["{{WORKSPACE_NAME}}"]},
        ]
        token_values = {"{{WORKSPACE_NAME}}": "my-project"}
        result = build_token_plan_summary(policy, actions, token_values)
        self.assertEqual(1, len(result))
        self.assertEqual("{{WORKSPACE_NAME}}", result[0]["token"])
        self.assertEqual("my-project", result[0]["value"])
        self.assertTrue(result[0]["required"])


# ---------------------------------------------------------------------------
# _source.py line 167 — parse_github_source called when source_arg is not None
# ---------------------------------------------------------------------------

class SourceGapTests(unittest.TestCase):
    def test_resolve_effective_package_root_calls_parse_github_source(self):
        """_source.py line 167: owner/repo = parse_github_source(source_arg) is executed."""
        from unittest.mock import patch as _patch
        from scripts.lifecycle._xanad._source import resolve_effective_package_root
        with tempfile.TemporaryDirectory() as tmp:
            with _patch("scripts.lifecycle._xanad._source.resolve_github_ref") as mock_ref:
                mock_ref.return_value = REPO_ROOT
                result = resolve_effective_package_root(
                    None, "github:owner/repo", None, None,
                )
        # The function should return (REPO_ROOT, {...}) via the pragma'd else branch
        self.assertIsNotNone(result)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
