"""Unit tests for _prescan.py — scan_existing_copilot_files and scan_consumer_kept_updates."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class ScanExistingCopilotFilesTests(unittest.TestCase):

    def _scan(self, workspace: Path, manifest: dict | None):
        from scripts.lifecycle._xanad._prescan import scan_existing_copilot_files
        return scan_existing_copilot_files(workspace, manifest)

    def test_returns_empty_when_manifest_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            results = self._scan(ws, None)
        self.assertEqual([], results)

    def test_returns_empty_when_no_managed_dirs_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            results = self._scan(ws, {"managedFiles": []})
        self.assertEqual([], results)

    def test_collision_file_yields_collision_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ".github/agents/my-agent.md"
            (ws / ".github" / "agents").mkdir(parents=True)
            (ws / target).write_text("existing content", encoding="utf-8")
            manifest = {
                "managedFiles": [{
                    "id": "agents/my-agent",
                    "target": target,
                    "source": "agents/my-agent.agent.md",
                    "strategy": "token-replace",
                    "hash": "sha256:abc",
                }]
            }
            results = self._scan(ws, manifest)
        self.assertEqual(1, len(results))
        rec = results[0]
        self.assertEqual("collision", rec["type"])
        self.assertEqual(target, rec["path"])
        self.assertEqual("agents/my-agent", rec["conflictsWith"])
        self.assertFalse(rec["mergeSupported"])
        self.assertIn("keep", rec["availableDecisions"])
        self.assertIn("replace", rec["availableDecisions"])
        self.assertNotIn("merge", rec["availableDecisions"])

    def test_collision_with_merge_strategy_includes_merge_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ".github/prompts/setup.md"
            (ws / ".github" / "prompts").mkdir(parents=True)
            (ws / target).write_text("content", encoding="utf-8")
            manifest = {
                "managedFiles": [{
                    "id": "prompts/setup",
                    "target": target,
                    "source": "template/prompts/setup.md",
                    "strategy": "preserve-marked-markdown-blocks",
                    "hash": "sha256:abc",
                }]
            }
            results = self._scan(ws, manifest)
        self.assertEqual(1, len(results))
        rec = results[0]
        self.assertTrue(rec["mergeSupported"])
        self.assertEqual("preserve-marked-markdown-blocks", rec["mergeStrategy"])
        self.assertIn("merge", rec["availableDecisions"])

    def test_unmanaged_file_yields_unmanaged_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / ".github" / "agents").mkdir(parents=True)
            (ws / ".github" / "agents" / "old-agent.md").write_text("old", encoding="utf-8")
            manifest = {"managedFiles": []}
            results = self._scan(ws, manifest)
        self.assertEqual(1, len(results))
        rec = results[0]
        self.assertEqual("unmanaged", rec["type"])
        self.assertIsNone(rec["conflictsWith"])
        self.assertFalse(rec["mergeSupported"])
        self.assertIn("keep", rec["availableDecisions"])
        self.assertIn("remove", rec["availableDecisions"])

    def test_copy_if_missing_collision_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ".github/agents/my-agent.md"
            (ws / ".github" / "agents").mkdir(parents=True)
            (ws / target).write_text("content", encoding="utf-8")
            manifest = {
                "managedFiles": [{
                    "id": "agents/my-agent",
                    "target": target,
                    "source": "agents/my-agent.agent.md",
                    "strategy": "copy-if-missing",
                    "hash": "sha256:abc",
                }]
            }
            results = self._scan(ws, manifest)
        self.assertEqual([], results)

    def test_excluded_filename_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / ".github" / "agents").mkdir(parents=True)
            (ws / ".github" / "agents" / "copilot-version.md").write_text("v", encoding="utf-8")
            results = self._scan(ws, {"managedFiles": []})
        self.assertEqual([], results)

    def test_surface_inferred_from_github_subdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / ".github" / "skills").mkdir(parents=True)
            (ws / ".github" / "skills" / "custom.md").write_text("x", encoding="utf-8")
            results = self._scan(ws, {"managedFiles": []})
        self.assertEqual(1, len(results))
        self.assertEqual("skills", results[0]["surface"])


class ScanConsumerKeptUpdatesTests(unittest.TestCase):

    def _scan(self, workspace: Path, manifest, lockfile_state):
        from scripts.lifecycle._xanad._prescan import scan_consumer_kept_updates
        return scan_consumer_kept_updates(workspace, manifest, lockfile_state)

    def _lockfile(self, resolutions: dict, files: list) -> dict:
        return {
            "present": True,
            "consumerResolutions": resolutions,
            "files": files,
        }

    def test_returns_empty_when_manifest_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            result = self._scan(ws, None, self._lockfile({"a": "keep"}, []))
        self.assertEqual([], result)

    def test_returns_empty_when_no_consumer_resolutions(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            result = self._scan(ws, {"managedFiles": []}, self._lockfile({}, []))
        self.assertEqual([], result)

    def test_source_unchanged_is_not_reported(self):
        """When source hash matches lockfile hash, file is silently re-kept."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ".github/agents/my-agent.md"
            lockfile = self._lockfile(
                {"target": "keep"},
                [{"target": target, "sourceHash": "sha256:same"}],
            )
            manifest = {
                "managedFiles": [{
                    "id": "agents/my-agent",
                    "target": target,
                    "source": "agents/my-agent.agent.md",
                    "strategy": "token-replace",
                    "hash": "sha256:same",
                }]
            }
            # Use the correct target key for the resolution
            lockfile = self._lockfile(
                {target: "keep"},
                [{"target": target, "sourceHash": "sha256:same"}],
            )
            result = self._scan(ws, manifest, lockfile)
        self.assertEqual([], result)

    def test_source_changed_is_re_offered(self):
        """When manifest hash differs from stored sourceHash, re-offer the file."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ".github/agents/my-agent.md"
            lockfile = self._lockfile(
                {target: "keep"},
                [{"target": target, "sourceHash": "sha256:old"}],
            )
            manifest = {
                "managedFiles": [{
                    "id": "agents/my-agent",
                    "target": target,
                    "source": "agents/my-agent.agent.md",
                    "strategy": "token-replace",
                    "hash": "sha256:new",
                }]
            }
            result = self._scan(ws, manifest, lockfile)
        self.assertEqual(1, len(result))
        rec = result[0]
        self.assertEqual("consumer-kept-updated", rec["type"])
        self.assertEqual(target, rec["path"])
        self.assertIn("keep", rec["availableDecisions"])
        self.assertIn("update", rec["availableDecisions"])

    def test_entry_removed_from_manifest_is_skipped(self):
        """When target no longer exists in manifest, do not re-offer it."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            lockfile = self._lockfile(
                {".github/agents/gone.md": "keep"},
                [],
            )
            result = self._scan(ws, {"managedFiles": []}, lockfile)
        self.assertEqual([], result)


if __name__ == "__main__":
    unittest.main()
