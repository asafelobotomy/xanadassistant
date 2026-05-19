from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import release_decision


class ReleaseDecisionTests(unittest.TestCase):
    def test_main_writes_should_publish_true_for_unreleased_head_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            output_path = repo_root / "github-output.txt"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with mock.patch("scripts.release_decision.release_exists", return_value=False):
                exit_code = release_decision.main([
                    "--repo-root",
                    str(repo_root),
                    "--github-output",
                    str(output_path),
                ], stdout=stdout, stderr=stderr)

            output = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("version=1.2.3", output)
        self.assertIn("tag=v1.2.3", output)
        self.assertIn("should_publish=true", output)

    def test_main_writes_should_publish_false_when_release_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            output_path = repo_root / "github-output.txt"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with mock.patch("scripts.release_decision.release_exists", return_value=True):
                exit_code = release_decision.main([
                    "--repo-root",
                    str(repo_root),
                    "--github-output",
                    str(output_path),
                ], stdout=stdout, stderr=stderr)

            output = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("should_publish=false", output)
        self.assertIn("reason=release_exists", output)

    def test_failed_bump_then_repair_sequence_still_publishes_head_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)

            (repo_root / "VERSION").write_text("0.3.3\n", encoding="utf-8")
            subprocess.run(["git", "add", "VERSION"], cwd=repo_root, check=True)
            subprocess.run(["git", "commit", "-m", "initial version"], cwd=repo_root, check=True, capture_output=True, text=True)

            (repo_root / "VERSION").write_text("0.3.4\n", encoding="utf-8")
            subprocess.run(["git", "add", "VERSION"], cwd=repo_root, check=True)
            subprocess.run(["git", "commit", "-m", "bump version"], cwd=repo_root, check=True, capture_output=True, text=True)

            (repo_root / "repair.txt").write_text("sync lockfile\n", encoding="utf-8")
            subprocess.run(["git", "add", "repair.txt"], cwd=repo_root, check=True)
            subprocess.run(["git", "commit", "-m", "repair drift"], cwd=repo_root, check=True, capture_output=True, text=True)

            with mock.patch("scripts.release_decision.release_exists", return_value=False):
                decision = release_decision.build_decision(repo_root)

        self.assertEqual(decision["version"], "0.3.4")
        self.assertEqual(decision["tag"], "v0.3.4")
        self.assertTrue(decision["should_publish"])

    def test_release_exists_treats_missing_release_as_false(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["gh", "release", "view", "v1.2.3"],
            returncode=1,
            stdout="",
            stderr="release not found",
        )
        with mock.patch("scripts.release_decision.subprocess.run", return_value=completed):
            exists = release_decision.release_exists("v1.2.3", "owner/repo")

        self.assertFalse(exists)

    def test_main_returns_exit_2_when_version_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = release_decision.main(["--repo-root", tmpdir], stdout=io.StringIO(), stderr=io.StringIO())

        self.assertEqual(exit_code, 2)