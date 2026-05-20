from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _main
from scripts.lifecycle._xanad import _execute_apply
from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH, LifecycleCommandError
from scripts.lifecycle._xanad._main import main


class MainDispatchTests(unittest.TestCase):
    def _resolved_package_root(self, tmpdir: str) -> tuple[Path, dict[str, str]]:
        return Path(tmpdir), {"kind": "package-root"}

    def test_run_execution_command_covers_success_and_serialized_plan_error_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            package_root = Path(tmpdir)
            args = mock.Mock(
                answers=None,
                non_interactive=False,
                dry_run=True,
                resolutions=None,
                plan=None,
                report_out=str(workspace / "report.json"),
                ui="quiet",
            )

            with mock.patch.object(
                _main,
                "build_execution_result",
                return_value={"command": "update", "mode": "update", "result": {}},
            ), mock.patch.object(
                _main,
                "write_plan_output",
                return_value=str(workspace / "report.json"),
            ), mock.patch.object(_main, "emit_payload") as emit_payload:
                exit_code = _main._run_execution_command(args, workspace, package_root, False, "update", "update")

            self.assertEqual(exit_code, 0)
            self.assertEqual(emit_payload.call_args.args[0]["result"]["reportOut"], str(workspace / "report.json"))

            args.plan = str(workspace / "plan.json")
            with mock.patch.object(
                _main,
                "build_setup_result",
                side_effect=LifecycleCommandError("apply_failure", "setup failed", 5, details={"x": 1}),
            ), mock.patch.object(
                _main,
                "load_apply_plan",
                return_value={"mode": "setup"},
            ), mock.patch.object(
                _main,
                "build_error_payload",
                return_value=({"command": "setup", "result": {}}, 5),
            ) as build_error_payload, mock.patch.object(
                _main,
                "write_plan_output",
                return_value=None,
            ), mock.patch.object(_main, "emit_payload"):
                exit_code = _main._run_execution_command(args, workspace, package_root, False, "setup", None)

            self.assertEqual(exit_code, 5)
            self.assertEqual(build_error_payload.call_args.kwargs["mode"], "setup")

            with mock.patch.object(
                _main,
                "build_apply_result",
                side_effect=LifecycleCommandError("apply_failure", "apply failed", 5, details={"x": 1}),
            ), mock.patch.object(
                _main,
                "load_apply_plan",
                return_value={"mode": "repair"},
            ), mock.patch.object(
                _main,
                "build_error_payload",
                return_value=({"command": "apply", "result": {}}, 5),
            ) as build_error_payload, mock.patch.object(
                _main,
                "write_plan_output",
                return_value=None,
            ), mock.patch.object(_main, "emit_payload"):
                exit_code = _main._run_execution_command(args, workspace, package_root, False, "apply", None)

            self.assertEqual(exit_code, 5)
            self.assertEqual(build_error_payload.call_args.kwargs["mode"], "repair")

    def test_main_rejects_json_and_json_lines_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._main.emit_payload"
        ) as emit_payload:
            exit_code = main(["inspect", "--workspace", tmpdir, "--package-root", tmpdir, "--json", "--json-lines"])

        self.assertEqual(exit_code, 2)
        self.assertTrue(emit_payload.called)

    def test_main_returns_drift_exit_code_for_health_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._main.build_check_result",
            return_value={"status": "drift", "warnings": [], "errors": [], "result": {}},
        ), mock.patch("scripts.lifecycle._xanad._main.emit_payload"):
            exit_code = main(["health-check", "--workspace", tmpdir, "--package-root", tmpdir])

        self.assertEqual(exit_code, 7)

    def test_main_plan_attaches_plan_out_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._main.build_plan_result",
            return_value={"command": "plan", "mode": "setup", "workspace": tmpdir, "warnings": [], "errors": [], "result": {}},
        ), mock.patch("scripts.lifecycle._xanad._main.emit_payload") as emit_payload:
            plan_out = str(Path(tmpdir) / "plan.json")
            exit_code = main(["plan", "setup", "--workspace", tmpdir, "--package-root", tmpdir, "--plan-out", plan_out])

        self.assertEqual(exit_code, 0)
        payload = emit_payload.call_args.args[0]
        self.assertEqual(payload["result"]["planOut"], str(Path(plan_out).resolve()))

    def test_main_health_report_attaches_report_out_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._health_check.build_health_check_result",
            return_value={"command": "health-report", "workspace": tmpdir, "warnings": [], "errors": [], "result": {}},
        ), mock.patch("scripts.lifecycle._xanad._main.emit_payload") as emit_payload:
            report_out = str(Path(tmpdir) / "health-report.json")
            exit_code = main(["health-report", "--workspace", tmpdir, "--package-root", tmpdir, "--report-out", report_out])

        self.assertEqual(exit_code, 0)
        payload = emit_payload.call_args.args[0]
        self.assertEqual(payload["result"]["reportOut"], str(Path(report_out).resolve()))

    def test_main_handles_log_file_open_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "pathlib.Path.open",
            side_effect=OSError("permission denied"),
        ), mock.patch("scripts.lifecycle._xanad._main.emit_payload") as emit_payload:
            exit_code = main(["inspect", "--workspace", tmpdir, "--package-root", tmpdir, "--log-file", str(Path(tmpdir) / "run.log")])

        self.assertEqual(exit_code, 4)
        self.assertTrue(emit_payload.called)

    def test_main_dispatches_setup_retires_apply_and_handles_source_resolution_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "command": "plan",
                        "mode": "setup",
                        "workspace": tmpdir,
                        "result": {
                            "plannedLockfile": {
                                "path": ".github/xanadAssistant-lock.json",
                                "contents": {},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                return_value=self._resolved_package_root(tmpdir),
            ), mock.patch(
                "scripts.lifecycle._xanad._main._run_execution_command",
                return_value=0,
            ) as run_exec:
                setup_exit = main(["setup", "--workspace", tmpdir, "--package-root", tmpdir, "--plan", str(plan_path)])

            self.assertEqual(setup_exit, 0)
            self.assertTrue(run_exec.called)

            with mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                side_effect=AssertionError("apply should be retired before package-root resolution"),
            ), mock.patch(
                "scripts.lifecycle._xanad._main._run_execution_command",
                side_effect=AssertionError("apply should not dispatch to execution"),
            ), mock.patch("scripts.lifecycle._xanad._main.emit_payload") as emit_payload:
                exit_code = main(["apply", "--workspace", tmpdir, "--plan", str(plan_path)])

            self.assertEqual(exit_code, 4)
            payload = emit_payload.call_args.args[0]
            self.assertEqual(payload["command"], "apply")
            self.assertEqual(payload["mode"], "setup")
            self.assertEqual(payload["errors"][0]["code"], "retired_command")

    def test_retired_apply_does_not_create_missing_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._main.emit_payload"
        ) as emit_payload:
            workspace = Path(tmpdir) / "missing-workspace"

            exit_code = main(["apply", "--workspace", str(workspace), "--json"])

        self.assertEqual(exit_code, 4)
        self.assertFalse(workspace.exists())
        payload = emit_payload.call_args.args[0]
        self.assertEqual(payload["errors"][0]["code"], "retired_command")

    def test_main_handles_source_resolution_failure_for_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._main.resolve_effective_package_root",
            side_effect=LifecycleCommandError("contract_input_failure", "bad source", 4),
        ), mock.patch("scripts.lifecycle._xanad._main.emit_payload") as emit_payload:
            failed = main(["inspect", "--workspace", tmpdir, "--package-root", tmpdir])

        self.assertEqual(failed, 4)
        self.assertTrue(emit_payload.called)

    def test_main_dispatches_setup_before_source_resolution_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.json"
            plan_path.write_text("{}", encoding="utf-8")

            with mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                return_value=self._resolved_package_root(tmpdir),
            ), mock.patch(
                "scripts.lifecycle._xanad._main._run_execution_command",
                return_value=0,
            ) as run_exec:
                setup_exit = main(["setup", "--workspace", tmpdir, "--package-root", tmpdir, "--plan", str(plan_path)])

        self.assertEqual(setup_exit, 0)
        self.assertTrue(run_exec.called)

    def test_main_handles_inspect_and_interview_errors(self) -> None:
        cases = [
            (
                ["inspect", "--workspace", None, "--package-root", None],
                "scripts.lifecycle._xanad._main.build_inspect_result",
                "inspect failed",
            ),
            (
                ["interview", "--mode", "setup", "--workspace", None, "--package-root", None],
                "scripts.lifecycle._xanad._main.build_interview_result",
                "interview failed",
            ),
        ]

        for argv_template, target, message in cases:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmpdir, mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                return_value=self._resolved_package_root(tmpdir),
            ), mock.patch(
                target,
                side_effect=LifecycleCommandError("contract_input_failure", message, 4),
            ), mock.patch("scripts.lifecycle._xanad._main.emit_payload") as emit_payload:
                argv = [tmpdir if value is None else value for value in argv_template]
                exit_code = main(argv)

            self.assertEqual(exit_code, 4)
            self.assertTrue(emit_payload.called)

    def test_main_handles_check_and_plan_errors_and_nonzero_plan_results(self) -> None:
        cases = [
            (["health-check", "--workspace", None, "--package-root", None], "scripts.lifecycle._xanad._main.build_check_result", "check failed"),
            (["plan", "setup", "--workspace", None, "--package-root", None], "scripts.lifecycle._xanad._main.build_plan_result", "plan failed"),
        ]

        for argv_template, target, message in cases:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmpdir, mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                return_value=self._resolved_package_root(tmpdir),
            ), mock.patch(
                target,
                side_effect=LifecycleCommandError("contract_input_failure", message, 4),
            ), mock.patch("scripts.lifecycle._xanad._main.emit_payload") as emit_payload:
                argv = [tmpdir if value is None else value for value in argv_template]
                exit_code = main(argv)

            self.assertEqual(exit_code, 4)
            self.assertTrue(emit_payload.called)

        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._main.build_plan_result",
            return_value={"command": "plan", "mode": "setup", "workspace": tmpdir, "warnings": [], "errors": [{"code": "x"}], "result": {}},
        ), mock.patch("scripts.lifecycle._xanad._main.emit_payload"):
            plan_exit = main(["plan", "setup", "--workspace", tmpdir, "--package-root", tmpdir])

        self.assertEqual(plan_exit, 4)

    def test_main_dispatches_remaining_execution_commands(self) -> None:
        for command in ("update", "repair", "factory-restore"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmpdir, mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                return_value=self._resolved_package_root(tmpdir),
            ), mock.patch(
                "scripts.lifecycle._xanad._main._run_execution_command",
                return_value=0,
            ) as run_exec:
                exit_code = main([command, "--workspace", tmpdir, "--package-root", tmpdir])

            self.assertEqual(exit_code, 0)
            self.assertEqual(run_exec.call_args.args[4], command)

    def test_main_does_not_create_missing_workspace_for_non_setup_write_commands(self) -> None:
        for command in ("update", "repair", "factory-restore"):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmpdir, mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                return_value=self._resolved_package_root(tmpdir),
            ), mock.patch(
                "scripts.lifecycle._xanad._main._run_execution_command",
                return_value=0,
            ):
                workspace = Path(tmpdir) / "missing-workspace"
                exit_code = main([command, "--workspace", str(workspace), "--package-root", tmpdir])

            self.assertEqual(exit_code, 0)
            self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
