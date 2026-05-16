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
    def test_main_lists_available_checks(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = drift_preflight.main(["--list"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("attention-budget", output)
        self.assertIn("freshness", output)

    def test_run_executes_selected_checks_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            calls: list[tuple[str, ...]] = []

            def fake_run(command: tuple[str, ...], cwd: Path):
                calls.append(command)
                self.assertEqual(cwd, repo_root)
                return subprocess.CompletedProcess(command, 0)

            with mock.patch("scripts.drift_preflight.subprocess.run", side_effect=fake_run):
                exit_code = drift_preflight.run(repo_root, ["loc", "tests"])

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
                exit_code = drift_preflight.run(repo_root, ["loc", "tests"])

        self.assertEqual(exit_code, 7)
        self.assertEqual(run_mock.call_count, 1)

    def test_main_rejects_missing_repo_root(self) -> None:
        exit_code = drift_preflight.main(["--repo-root", "/path/that/does/not/exist"])

        self.assertEqual(exit_code, 2)

    def test_ci_workflow_invokes_each_registered_check(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        check_names = {check.name for check in drift_preflight.CHECKS}
        workflow_checks = set(re.findall(r"python3 scripts/drift_preflight.py --check ([a-z-]+)", workflow))

        self.assertEqual(workflow_checks, check_names)