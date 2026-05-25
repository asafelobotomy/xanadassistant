from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.mcp_servers._xanad_workspace_mcp_support import XanadWorkspaceMcpTestCaseMixin


class XanadWorkspaceMcpLifecycleTests(XanadWorkspaceMcpTestCaseMixin, unittest.TestCase):
    def test_run_lifecycle_command_rejects_invalid_boolean_and_answers_path(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module), mock.patch.object(
                    module,
                    "resolve_lifecycle_package_root",
                    return_value=(Path("/tmp/pkg"), None),
                ), mock.patch.object(module, "resolve_lifecycle_cli", return_value=(["python3", "xanadAssistant.py"], None)):
                    invalid_answers = module.run_lifecycle_command("plan", answers_path="/missing/answers.json")
                    invalid_bool = module.run_lifecycle_command("apply", dry_run="yes")

                self.assertEqual(invalid_answers["status"], "unavailable")
                self.assertIn("answersPath", invalid_answers["summary"])
                self.assertEqual(invalid_bool["status"], "unavailable")
                self.assertIn("dryRun", invalid_bool["summary"])

    def test_run_lifecycle_command_rejects_answers_path_outside_workspace(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
                    outside_path = f.name
                try:
                    with self._workspace_ready(module), mock.patch.object(
                        module,
                        "resolve_lifecycle_package_root",
                        return_value=(Path("/tmp/pkg"), None),
                    ), mock.patch.object(module, "resolve_lifecycle_cli", return_value=(["python3", "xanadAssistant.py"], None)):
                        result = module.run_lifecycle_command("plan", answers_path=outside_path)
                    self.assertEqual(result["status"], "unavailable")
                    self.assertIn("workspace", result["summary"].lower())
                finally:
                    Path(outside_path).unlink(missing_ok=True)

    def test_run_lifecycle_command_rejects_symlinked_answers_path_outside_workspace(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as workspace_dir, tempfile.TemporaryDirectory() as outside_dir:
                    workspace_root = Path(workspace_dir)
                    outside_file = Path(outside_dir) / "answers.json"
                    outside_file.write_text("{}", encoding="utf-8")
                    symlink_path = workspace_root / "answers-link.json"
                    symlink_path.symlink_to(outside_file)

                    with self._workspace_ready(module), mock.patch.object(module, "WORKSPACE_ROOT", workspace_root), mock.patch.object(
                        module, "resolve_lifecycle_package_root", return_value=(Path("/tmp/pkg"), None)
                    ), mock.patch.object(module, "resolve_lifecycle_cli", return_value=(["python3", "xanadAssistant.py"], None)):
                        result = module.run_lifecycle_command("plan", answers_path=str(symlink_path))

                    self.assertEqual(result["status"], "unavailable")
                    self.assertIn("workspace", result["summary"].lower())

    def test_run_lifecycle_command_resolves_relative_workspace_paths_from_workspace_root(self) -> None:
        original_cwd = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as workspace_dir, tempfile.TemporaryDirectory() as other_dir:
                workspace_root = Path(workspace_dir)
                plan_path = workspace_root / "plans" / "apply.json"
                answers_path = workspace_root / "answers" / "setup.json"
                plan_path.parent.mkdir(parents=True, exist_ok=True)
                answers_path.parent.mkdir(parents=True, exist_ok=True)
                plan_path.write_text("{}", encoding="utf-8")
                answers_path.write_text("{}", encoding="utf-8")
                os.chdir(other_dir)

                for module in self.MODULES:
                    with self.subTest(module=module.__name__):
                        with self._workspace_ready(module), mock.patch.object(module, "WORKSPACE_ROOT", workspace_root), mock.patch.object(
                            module,
                            "resolve_lifecycle_package_root",
                            return_value=(Path("/tmp/pkg"), None),
                        ), mock.patch.object(module, "resolve_lifecycle_cli", return_value=(["python3", "xanadAssistant.py"], None)), mock.patch.object(
                            module,
                            "run_argv",
                            return_value={"status": "ok", "summary": "done"},
                        ) as runner:
                            result = module.run_lifecycle_command(
                                "apply",
                                plan_path="plans/apply.json",
                                answers_path="answers/setup.json",
                            )

                        self.assertEqual(result["status"], "ok")
                        argv = runner.call_args.args[0]
                        self.assertIn(str(plan_path.resolve()), argv)
                        self.assertIn(str(answers_path.resolve()), argv)
        finally:
            os.chdir(original_cwd)

    def test_workspace_show_install_state_uses_check_status_for_drift(self) -> None:
        lifecycle_result = {
            "status": "ok",
            "summary": "Lifecycle command check completed.",
            "payload": {
                "status": "drift",
                "result": {
                    "installState": "installed",
                    "summary": {"missing": 1},
                },
            },
        }

        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module), mock.patch.object(
                    module, "run_lifecycle_command", return_value=lifecycle_result
                ):
                    result = module.tool_workspace_show_install_state({})

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["installState"], "installed")
                self.assertEqual(result["drift"], "drift")

    def test_run_argv_and_tool_wrappers_surface_payload_and_mode_validation(self) -> None:
        payload = {"command": "inspect", "status": "ok", "result": {"installState": "installed"}}

        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                completed = mock.Mock(returncode=0, stdout=json.dumps(payload), stderr="")
                with mock.patch.object(module.subprocess, "run", return_value=completed):
                    result = module.run_argv(["python3", "xanadAssistant.py", "inspect"], parse_payload=True)

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["payload"]["command"], "inspect")

                with mock.patch.object(module, "run_lifecycle_command", return_value={"status": "ok", "summary": "done"}):
                    inspect_result = module.lifecycle_inspect(packageRoot="/tmp/pkg")
                    check_result = module.lifecycle_check(packageRoot="/tmp/pkg")
                    plan_result = module.lifecycle_plan_setup(packageRoot="/tmp/pkg", answersPath=None)
                    setup_result = module.lifecycle_setup(packageRoot="/tmp/pkg", dryRun=True)
                    update_result = module.lifecycle_update(packageRoot="/tmp/pkg", dryRun=False)
                    repair_result = module.lifecycle_repair(packageRoot="/tmp/pkg")
                    restore_result = module.lifecycle_factory_restore(packageRoot="/tmp/pkg")

                apply_result = module.lifecycle_apply(packageRoot="/tmp/pkg", dryRun=True)

                self.assertEqual(inspect_result.status, "ok")
                self.assertEqual(check_result.status, "ok")
                self.assertEqual(plan_result.status, "ok")
                self.assertEqual(setup_result.status, "ok")
                self.assertEqual(apply_result.status, "unavailable")
                self.assertEqual(update_result.status, "ok")
                self.assertEqual(repair_result.status, "ok")
                self.assertEqual(restore_result.status, "ok")

                invalid_mode = module.lifecycle_interview(mode="bad")
                self.assertEqual(invalid_mode.status, "unavailable")

    def test_run_argv_json_error_and_non_dict_payload_branches(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                completed = mock.Mock(returncode=0, stdout=json.dumps({"status": "error", "command": "inspect"}), stderr="")
                with mock.patch.object(module.subprocess, "run", return_value=completed):
                    result = module.run_argv(["python3", "x.py"], parse_payload=True)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["payload"]["status"], "error")

                completed = mock.Mock(returncode=0, stdout="[]", stderr="")
                with mock.patch.object(module.subprocess, "run", return_value=completed):
                    result = module.run_argv(["python3", "x.py"], parse_payload=True)
                self.assertEqual(result["status"], "ok")
                self.assertNotIn("payload", result)

    def test_run_argv_failure_and_install_state_without_payload(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                completed = mock.Mock(returncode=1, stdout="plain stdout\n", stderr="plain stderr\n")
                with mock.patch.object(module.subprocess, "run", return_value=completed):
                    result = module.run_argv(["python3", "x.py"], parse_payload=False)

                self.assertEqual(result["status"], "failed")
                self.assertIn("stderrTail", result)

                with self._workspace_ready(module), mock.patch.object(
                    module,
                    "run_lifecycle_command",
                    return_value={"status": "failed", "summary": "broken"},
                ):
                    passthrough = module.tool_workspace_show_install_state({})

                self.assertEqual(passthrough["status"], "failed")

    def test_lifecycle_wrappers_forward_arguments_and_unavailable_package_root(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with mock.patch.object(module, "run_lifecycle_command", return_value={"status": "ok", "summary": "ok"}) as runner:
                    module.lifecycle_interview(packageRoot="/tmp/pkg", mode="setup")
                    module.lifecycle_plan_setup(packageRoot="/tmp/pkg", answersPath="/tmp/answers.json", nonInteractive=True)
                    module.lifecycle_setup(packageRoot="/tmp/pkg", dryRun=True, planPath="/tmp/setup-plan.json")
                    module.lifecycle_update(packageRoot="/tmp/pkg", dryRun=False)
                    module.lifecycle_repair(packageRoot="/tmp/pkg", nonInteractive=False)
                    module.lifecycle_factory_restore(packageRoot="/tmp/pkg", nonInteractive=True)

                apply_result = module.lifecycle_apply(packageRoot="/tmp/pkg", dryRun=True)

                self.assertEqual(runner.call_args_list[0].kwargs["mode"], "setup")
                self.assertTrue(runner.call_args_list[1].kwargs["non_interactive"])
                self.assertEqual(runner.call_args_list[2].kwargs["plan_path"], "/tmp/setup-plan.json")
                self.assertTrue(runner.call_args_list[2].kwargs["dry_run"])
                self.assertFalse(runner.call_args_list[3].kwargs["dry_run"])
                self.assertEqual(apply_result.status, "unavailable")

                with self._workspace_ready(module), mock.patch.object(
                    module,
                    "resolve_lifecycle_package_root",
                    return_value=(None, "missing package root"),
                ):
                    unavailable = module.run_lifecycle_command("inspect")

                self.assertEqual(unavailable["status"], "unavailable")

                with self._workspace_ready(module), mock.patch.object(
                    module,
                    "resolve_lifecycle_package_root",
                    return_value=(Path("/tmp/pkg"), None),
                ), mock.patch.object(
                    module,
                    "resolve_lifecycle_cli",
                    return_value=(None, "cli missing"),
                ):
                    unavailable_cli = module.run_lifecycle_command("inspect")

                self.assertEqual(unavailable_cli["status"], "unavailable")
                self.assertIn("cli missing", unavailable_cli["summary"])

    def test_run_lifecycle_command_uses_explicit_cli_resolution_without_remote_fallback(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module), mock.patch.object(
                    module,
                    "resolve_lifecycle_package_root",
                    return_value=(Path("/tmp/pkg"), None),
                ), mock.patch.object(
                    module,
                    "resolve_lifecycle_cli",
                    return_value=(None, "cli missing"),
                ) as resolve_cli, mock.patch.object(
                    module,
                    "run_argv",
                    side_effect=AssertionError("should not execute a guessed shell fallback"),
                ):
                    result = module.run_lifecycle_command("inspect")

                self.assertEqual(result["status"], "unavailable")
                self.assertIn("cli missing", result["summary"])
                resolve_cli.assert_called_once_with(Path("/tmp/pkg"))

    def test_run_lifecycle_command_rejects_invalid_plan_path(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module), mock.patch.object(
                    module,
                    "resolve_lifecycle_package_root",
                    return_value=(Path("/tmp/pkg"), None),
                ), mock.patch.object(module, "resolve_lifecycle_cli", return_value=(["python3", "xanadAssistant.py"], None)):
                    result = module.run_lifecycle_command("apply", plan_path="/missing/plan.json")
                self.assertEqual(result["status"], "unavailable")
                self.assertIn("planPath", result["summary"])

    def test_run_lifecycle_command_rejects_plan_path_outside_workspace(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
                    outside_path = f.name
                try:
                    with self._workspace_ready(module), mock.patch.object(
                        module, "resolve_lifecycle_package_root", return_value=(Path("/tmp/pkg"), None)
                    ), mock.patch.object(module, "resolve_lifecycle_cli", return_value=(["python3", "xanadAssistant.py"], None)):
                        result = module.run_lifecycle_command("apply", plan_path=outside_path)
                    self.assertEqual(result["status"], "unavailable")
                    self.assertIn("workspace", result["summary"].lower())
                finally:
                    Path(outside_path).unlink(missing_ok=True)

    def test_lifecycle_setup_accepts_plan_path_parameter_and_apply_is_retired(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with mock.patch.object(module, "run_lifecycle_command", return_value={"status": "ok", "summary": "ok"}) as runner:
                    module.lifecycle_setup(packageRoot="/tmp/pkg", planPath="/tmp/setup-plan.json")
                apply_result = module.lifecycle_apply(packageRoot="/tmp/pkg", planPath="/tmp/plan.json")
                self.assertEqual(runner.call_args_list[0].kwargs["plan_path"], "/tmp/setup-plan.json")
                self.assertEqual(apply_result.status, "unavailable")


if __name__ == "__main__":
    unittest.main()