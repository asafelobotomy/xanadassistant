"""Integration tests for per-file conflict resolution (--resolutions flag)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class PlanResolutionsTests(XanadTestBase):

    def test_plan_setup_applies_keep_resolution_to_collision_file(self) -> None:
        """A 'keep' resolution moves the collision action to skippedActions."""
        with tempfile.TemporaryDirectory() as res_dir:
            # Use a local-ownership prompts file (always local, not plugin-backed).
            target = ".github/prompts/setup.md"
            res_path = Path(res_dir) / "resolutions.json"
            res_path.write_text(json.dumps({target: "keep"}), encoding="utf-8")

            def _setup(ws: Path, _repo: Path) -> None:
                (ws / ".github" / "prompts").mkdir(parents=True)
                (ws / target).write_text("my custom content", encoding="utf-8")

            result = self.run_command(
                "plan", "setup",
                "--resolutions", str(res_path),
                "--json",
                workspace_setup=_setup,
            )

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        skipped_targets = [a["target"] for a in payload["result"]["skippedActions"]]
        action_targets = [a["target"] for a in payload["result"]["actions"]]
        self.assertIn(target, skipped_targets)
        self.assertNotIn(target, action_targets)
        skipped = next(a for a in payload["result"]["skippedActions"] if a["target"] == target)
        self.assertEqual("consumer-keep", skipped["reason"])

    def test_plan_setup_produces_delete_action_for_remove_resolution(self) -> None:
        """A 'remove' resolution for an unmanaged file creates a delete action."""
        with tempfile.TemporaryDirectory() as res_dir:
            target = ".github/agents/my-old-agent.md"
            res_path = Path(res_dir) / "resolutions.json"
            res_path.write_text(json.dumps({target: "remove"}), encoding="utf-8")

            def _setup(ws: Path, _repo: Path) -> None:
                (ws / ".github" / "agents").mkdir(parents=True)
                (ws / target).write_text("old content", encoding="utf-8")

            result = self.run_command(
                "plan", "setup",
                "--resolutions", str(res_path),
                "--json",
                workspace_setup=_setup,
            )

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        action_targets = [a["target"] for a in payload["result"]["actions"]]
        self.assertIn(target, action_targets)
        delete_action = next(a for a in payload["result"]["actions"] if a["target"] == target)
        self.assertEqual("delete", delete_action["action"])
        self.assertEqual("delete", delete_action["strategy"])

    def test_interview_setup_reports_existing_files_in_managed_dirs(self) -> None:
        """Interview result includes existingFiles and existingFileCount."""
        def _setup(ws: Path, _repo: Path) -> None:
            (ws / ".github" / "agents").mkdir(parents=True)
            (ws / ".github" / "agents" / "stale.md").write_text("stale", encoding="utf-8")

        result = self.run_command(
            "interview",
            "--mode", "setup",
            "--json",
            workspace_setup=_setup,
        )

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertIn("existingFiles", payload["result"])
        self.assertIn("existingFileCount", payload["result"])
        self.assertIsInstance(payload["result"]["existingFiles"], list)
        self.assertGreaterEqual(payload["result"]["existingFileCount"], 1)

    def test_plan_setup_warn_on_unknown_resolution_path(self) -> None:
        """Resolutions for paths not in existingFiles produce a warning."""
        with tempfile.TemporaryDirectory() as res_dir:
            res_path = Path(res_dir) / "resolutions.json"
            res_path.write_text(
                json.dumps({".github/agents/nonexistent.md": "keep"}),
                encoding="utf-8",
            )
            result = self.run_command(
                "plan", "setup",
                "--resolutions", str(res_path),
                "--json",
            )

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        warning_codes = [w["code"] for w in payload["warnings"]]
        self.assertIn("resolution_unknown_path", warning_codes)

    def test_plan_update_reoffers_previously_kept_file_when_source_changed(self) -> None:
        """Update mode re-offers kept files whose source has changed (H-1 regression guard)."""
        target = ".github/prompts/setup.md"
        lockfile = self.make_minimal_lockfile(
            consumerResolutions={target: "keep"},
            files=[{
                "id": "prompts.setup",
                "target": target,
                "sourceHash": "sha256:old-hash-that-differs-from-manifest",
                "installedHash": "sha256:some-installed-hash",
                "ownershipMode": "local",
                "status": "applied",
            }],
            setupAnswers={"profile.selected": "balanced", "packs.selected": []},
        )

        def _setup(ws: Path, _repo: Path) -> None:
            (ws / ".github" / "prompts").mkdir(parents=True)
            (ws / target).write_text("my custom content", encoding="utf-8")
            (ws / ".github" / "xanadAssistant-lock.json").write_text(
                json.dumps(lockfile), encoding="utf-8"
            )

        result = self.run_command("plan", "update", "--json", workspace_setup=_setup)

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        types = [f["type"] for f in payload["result"]["existingFiles"]]
        self.assertIn("consumer-kept-updated", types)
        kept = next(f for f in payload["result"]["existingFiles"] if f["type"] == "consumer-kept-updated")
        self.assertEqual(target, kept["path"])


if __name__ == "__main__":
    unittest.main()
