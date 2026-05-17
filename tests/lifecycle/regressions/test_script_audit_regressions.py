from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _pack_conflicts
from scripts.lifecycle._xanad import _resolutions
from scripts.lifecycle._xanad._errors import LifecycleCommandError
from scripts.lifecycle._xanad._inspect_helpers import collect_successor_migration_files
from scripts.lifecycle._xanad._source_remote import resolve_github_ref, resolve_github_release


class ScriptAuditRegressionsTests(unittest.TestCase):
    def test_load_resolutions_raises_structured_contract_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "resolutions.json"
            path.write_text("{not-json", encoding="utf-8")

            with self.assertRaises(LifecycleCommandError) as excinfo:
                _resolutions.load_resolutions(str(path))

        self.assertEqual(excinfo.exception.code, "contract_input_failure")
        self.assertEqual(excinfo.exception.exit_code, 4)

    def test_successor_cleanup_ignores_current_copilot_version_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            extra_file = workspace / ".github" / "prompts" / "extra.prompt.md"
            extra_file.parent.mkdir(parents=True, exist_ok=True)
            extra_file.write_text("extra\n", encoding="utf-8")
            predecessor_marker = workspace / ".github" / "hooks" / "copilot-hooks.json"
            predecessor_marker.parent.mkdir(parents=True, exist_ok=True)
            predecessor_marker.write_text("{}\n", encoding="utf-8")
            summary = workspace / ".github" / "copilot-version.md"
            summary.write_text("current summary\n", encoding="utf-8")

            cleanup_targets = collect_successor_migration_files(
                workspace,
                {"managedFiles": [], "retiredFiles": []},
                {"present": True, "data": {"package": {"name": "copilot-instructions-template"}}},
                {"present": True},
            )

        self.assertIn(".github/prompts/extra.prompt.md", cleanup_targets)
        self.assertNotIn(".github/copilot-version.md", cleanup_targets)

    def test_successor_cleanup_uses_legacy_summary_when_lockfile_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            extra_file = workspace / ".github" / "prompts" / "legacy.prompt.md"
            extra_file.parent.mkdir(parents=True, exist_ok=True)
            extra_file.write_text("legacy\n", encoding="utf-8")
            summary = workspace / ".github" / "copilot-version.md"
            summary.write_text("legacy summary\n", encoding="utf-8")

            cleanup_targets = collect_successor_migration_files(
                workspace,
                {"managedFiles": [], "retiredFiles": []},
                {"present": False, "data": {}},
                {"present": True},
            )

        self.assertIn(".github/prompts/legacy.prompt.md", cleanup_targets)
        self.assertNotIn(".github/copilot-version.md", cleanup_targets)

    def test_pack_conflict_questions_match_interview_schema(self) -> None:
        questions = _pack_conflicts.build_conflict_questions([
            {
                "token": "pack:output-style",
                "questionId": "resolvedTokenConflicts.pack:output-style",
                "packs": ["alpha", "beta"],
                "candidates": {"alpha": "A", "beta": "B"},
            }
        ])

        self.assertEqual(questions[0]["id"], "resolvedTokenConflicts.pack:output-style")
        self.assertEqual(questions[0]["kind"], "choice")
        self.assertIn("Choose which pack's value to use", questions[0]["prompt"])
        self.assertEqual(questions[0]["options"], ["alpha", "beta"])

    def test_remote_source_failures_use_exit_code_three(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)

            with mock.patch("urllib.request.urlopen", side_effect=RuntimeError("network down")):
                with self.assertRaises(LifecycleCommandError) as release_exc:
                    resolve_github_release("owner", "repo", "v1.0.0", cache_root)

            self.assertEqual(release_exc.exception.exit_code, 3)

            error = subprocess.CalledProcessError(1, ["git"], stderr=b"fatal: nope")
            with mock.patch("subprocess.run", side_effect=error):
                with self.assertRaises(LifecycleCommandError) as ref_exc:
                    resolve_github_ref("owner", "repo", "main", cache_root)

            self.assertEqual(ref_exc.exception.exit_code, 3)


if __name__ == "__main__":
    unittest.main()