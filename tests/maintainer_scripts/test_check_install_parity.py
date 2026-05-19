from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import check_install_parity


class CheckInstallParityTests(unittest.TestCase):
    def test_run_builds_setup_plan_applies_it_and_checks_parity_in_temp_workspace(self) -> None:
        package_root = Path("/package")

        with mock.patch("scripts.check_install_parity.build_plan_result", return_value={"result": {"conflictDetails": []}}) as build_plan, mock.patch(
            "scripts.check_install_parity.build_setup_result",
            return_value={"result": {"applied": True}},
        ) as build_setup, mock.patch(
            "scripts.check_install_parity.check_managed_parity.run",
            return_value=0,
        ) as parity_run:
            exit_code = check_install_parity.run(package_root)

        self.assertEqual(exit_code, 0)
        plan_workspace = build_plan.call_args.args[0]
        self.assertIsInstance(plan_workspace, Path)
        self.assertEqual(build_plan.call_args.args[1], package_root)
        self.assertEqual(build_plan.call_args.args[2], "setup")
        self.assertEqual(Path(build_plan.call_args.args[3]).name, "setup-answers.json")
        self.assertTrue(build_plan.call_args.args[4])
        build_setup.assert_called_once()
        self.assertEqual(build_setup.call_args.args[0], plan_workspace)
        self.assertEqual(build_setup.call_args.args[1], package_root)
        parity_run.assert_called_once_with(package_root, plan_workspace)

    def test_run_returns_exit_4_when_plan_requires_conflict_resolution(self) -> None:
        with mock.patch(
            "scripts.check_install_parity.build_plan_result",
            return_value={"result": {"conflictDetails": [{"questionId": "token.choice"}]}},
        ), mock.patch("scripts.check_install_parity.build_setup_result") as build_setup, mock.patch(
            "scripts.check_install_parity.check_managed_parity.run"
        ) as parity_run:
            exit_code = check_install_parity.run(Path("/package"))

        self.assertEqual(exit_code, 4)
        build_setup.assert_not_called()
        parity_run.assert_not_called()

    def test_main_returns_exit_2_for_missing_package_root(self) -> None:
        exit_code = check_install_parity.main(["--package-root", "/no/such/path"])

        self.assertEqual(exit_code, 2)

    def test_main_uses_current_directory_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch("scripts.check_install_parity.run", return_value=0) as run_mock:
            previous_cwd = Path.cwd()
            try:
                import os

                os.chdir(tmpdir)
                exit_code = check_install_parity.main([])
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(exit_code, 0)
        run_mock.assert_called_once_with(Path(tmpdir).resolve())