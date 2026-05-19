from __future__ import annotations

import io
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import drift_preflight


class DriftPreflightTests(unittest.TestCase):
    @staticmethod
    def _read_ci_workflow() -> str:
        return (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    def test_main_lists_available_checks(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = drift_preflight.main(["--list"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("attention-budget", output)
        self.assertIn("version-bump", output)
        self.assertIn("freshness", output)
        self.assertIn("workspace-drift", output)
        self.assertIn("parity", output)

    def test_run_executes_selected_checks_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            calls: list[tuple[str, ...]] = []

            def fake_run(command: tuple[str, ...], cwd: Path):
                calls.append(command)
                self.assertEqual(cwd, repo_root)
                return subprocess.CompletedProcess(command, 0)

            with mock.patch("scripts.drift_preflight.subprocess.run", side_effect=fake_run):
                exit_code = drift_preflight.run(repo_root, ["loc", "tests"], stderr=io.StringIO())

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            calls,
            [
                ("python3", "scripts/check_loc.py"),
                ("python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"),
            ],
        )

    def test_run_stops_at_first_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            def fake_run(command: tuple[str, ...], cwd: Path):
                if command[1] == "scripts/check_loc.py":
                    return subprocess.CompletedProcess(command, 7)
                return subprocess.CompletedProcess(command, 0)

            with mock.patch("scripts.drift_preflight.subprocess.run", side_effect=fake_run) as run_mock:
                exit_code = drift_preflight.run(repo_root, ["loc", "tests"], stderr=io.StringIO())

        self.assertEqual(exit_code, 7)
        self.assertEqual(run_mock.call_count, 1)

    def test_main_rejects_missing_repo_root(self) -> None:
        exit_code = drift_preflight.main(["--repo-root", "/path/that/does/not/exist"], stderr=io.StringIO())

        self.assertEqual(exit_code, 2)

    def test_ci_workflow_invokes_each_registered_check(self) -> None:
        workflow = self._read_ci_workflow()
        check_names = {check.name for check in drift_preflight.CHECKS}
        workflow_checks = set(re.findall(r"python3 scripts/drift_preflight.py --check ([a-z-]+)", workflow))

        self.assertEqual(workflow_checks, check_names)

    def test_release_job_waits_for_all_quality_gates(self) -> None:
        workflow = self._read_ci_workflow()

        release_block_match = re.search(
            r"\n  release:\n(?P<body>(?:    .*\n)+)",
            workflow,
        )
        self.assertIsNotNone(release_block_match)
        release_block = release_block_match.group("body")

        for required_job in (
            "attention-budget",
            "version-bump",
            "loc-gate",
            "test",
            "freshness",
            "workspace-drift",
            "parity",
        ):
            with self.subTest(job=required_job):
                self.assertIn(f"      - {required_job}", release_block)

    def test_release_job_targets_head_version_and_skips_existing_releases(self) -> None:
        workflow = self._read_ci_workflow()

        self.assertIn("if: github.event_name == 'push' && github.ref == 'refs/heads/main'", workflow)
        self.assertIn("python3 scripts/release_decision.py --repo-root . --github-output \"$GITHUB_OUTPUT\"", workflow)
        self.assertNotIn("git diff --name-only \"$before\" \"$GITHUB_SHA\"", workflow)
        self.assertNotIn("version_changed=false", workflow)
        self.assertIn("if: steps.release_decision.outputs.should_publish == 'true'", workflow)

    def test_release_job_builds_changelog_from_previous_tag(self) -> None:
        workflow = self._read_ci_workflow()

        self.assertIn("git tag --sort=-version:refname | grep -Fxv \"$TAG\" | head -n 1 || true", workflow)
        self.assertIn("git log --reverse --pretty='- %s (%h)' \"$previous_tag..$GITHUB_SHA\"", workflow)
        self.assertIn("Full diff: https://github.com/${GITHUB_REPOSITORY}/compare/${previous_tag}...${TAG}", workflow)

    def test_parity_check_uses_fresh_install_script(self) -> None:
        parity_check = next(check for check in drift_preflight.CHECKS if check.name == "parity")

        self.assertEqual(parity_check.command, ("python3", "scripts/check_install_parity.py"))