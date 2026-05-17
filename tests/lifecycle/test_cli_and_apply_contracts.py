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


class ApplyContractTests(unittest.TestCase):
    def _write_policy_and_manifest(self, package_root: Path, manifest_hash: str = "sha256:manifest") -> None:
        policy_path = package_root / DEFAULT_POLICY_PATH
        manifest_path = package_root / "template" / "setup" / "install-manifest.json"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(
            json.dumps({"generationSettings": {"manifestOutput": "template/setup/install-manifest.json"}}),
            encoding="utf-8",
        )
        manifest_path.write_text(
            json.dumps({
                "managedFiles": [{"id": "prompts.main", "target": ".github/prompts/main.prompt.md"}],
                "retiredFiles": [{"id": "retired.prompt", "target": ".github/prompts/retired.prompt.md"}],
                "hash": manifest_hash,
            }),
            encoding="utf-8",
        )

    def _base_result(self, backup_root: str = ".xanadAssistant/backups/<apply-timestamp>") -> dict[str, object]:
        return {
            "plannedLockfile": {"path": ".github/xanadAssistant-lock.json"},
            "backupPlan": {"root": backup_root, "targets": [], "archiveTargets": []},
        }

    def _plan_payload(self, workspace: Path, result: dict[str, object], mode: str = "repair") -> dict[str, object]:
        return {
            "command": "plan",
            "mode": mode,
            "workspace": str(workspace),
            "result": result,
        }

    def _assert_path_validation_error(self, payload: dict[str, object], package_root: Path) -> None:
        with self.assertRaises(LifecycleCommandError):
            _execute_apply.validate_apply_plan_paths(payload, package_root)

    def test_validate_apply_plan_paths_rejects_invalid_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            self._write_policy_and_manifest(package_root)
            cases = [
                {
                    "result": {
                        **self._base_result(),
                        "actions": [{"id": "prompts.main", "target": "README.md", "action": "replace"}],
                    }
                },
                {
                    "result": {
                        **self._base_result(),
                        "plannedLockfile": {"path": ".github/other-lock.json"},
                        "actions": [],
                    }
                },
            ]

            for payload in cases:
                with self.subTest(payload=payload):
                    self._assert_path_validation_error(payload, package_root)

    def test_load_apply_plan_and_validate_package_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            self._write_policy_and_manifest(package_root)
            plan_path = root / "plan.json"
            with mock.patch("scripts.lifecycle._xanad._execute_apply.sha256_json", return_value="sha256:manifest"):
                plan_path.write_text(
                    json.dumps(
                        self._plan_payload(
                            workspace,
                            {
                                "plannedLockfile": {
                                    "path": ".github/xanadAssistant-lock.json",
                                    "contents": {
                                        "package": {"name": "xanadAssistant"},
                                        "manifest": {"hash": "sha256:manifest"},
                                    },
                                },
                                "actions": [],
                                "backupPlan": {"targets": [], "archiveTargets": []},
                            },
                        )
                    ),
                    encoding="utf-8",
                )

                payload = _execute_apply.load_apply_plan(str(plan_path), workspace)
                _execute_apply.validate_apply_plan_package(payload, package_root)

        self.assertEqual(payload["mode"], "repair")

    def test_build_execution_result_success_path_and_apply_conflict_path(self) -> None:
        workspace = Path("/workspace")
        package_root = Path("/package")

        with mock.patch(
            "scripts.lifecycle._xanad._execute_apply.build_plan_result",
            return_value={"warnings": ["warn"], "result": {"conflictDetails": []}},
        ), mock.patch(
            "scripts.lifecycle._xanad._execute_apply.execute_apply_plan",
            return_value={"applied": True},
        ), mock.patch(
            "scripts.lifecycle._xanad._execute_apply.build_source_summary",
            return_value={"source": "github:owner/repo", "ref": "main"},
        ):
            payload = _execute_apply.build_execution_result("update", "update", workspace, package_root, None, False, dry_run=True)

        self.assertEqual(payload["command"], "update")
        self.assertEqual(payload["warnings"], ["warn"])
        self.assertEqual(payload["result"], {"applied": True})

        plan_payload = {
            "mode": "update",
            "warnings": [],
            "result": {"plannedLockfile": {"contents": {}}, "conflictDetails": [{"questionId": "pack.choice"}]},
        }
        with mock.patch("scripts.lifecycle._xanad._execute_apply.load_apply_plan", return_value=plan_payload), mock.patch(
            "scripts.lifecycle._xanad._execute_apply.validate_apply_plan_paths"
        ), mock.patch("scripts.lifecycle._xanad._execute_apply.validate_apply_plan_package"):
            with self.assertRaises(LifecycleCommandError) as excinfo:
                _execute_apply.build_apply_result(workspace, package_root, None, False, plan_path="plan.json")

        self.assertEqual(excinfo.exception.code, "approval_or_answers_required")

    def test_build_apply_result_rejects_resolutions_argument(self) -> None:
        with self.assertRaises(LifecycleCommandError):
            _execute_apply.build_apply_result(Path("."), Path("."), None, False, resolutions_path="resolutions.json")

    def test_build_execution_and_apply_result_cover_conflict_and_success_paths(self) -> None:
        workspace = Path("/workspace")
        package_root = Path("/package")

        with mock.patch(
            "scripts.lifecycle._xanad._execute_apply.build_plan_result",
            return_value={
                "warnings": [],
                "result": {"conflictDetails": [{"questionId": "pack.choice"}]},
            },
        ):
            with self.assertRaises(LifecycleCommandError) as excinfo:
                _execute_apply.build_execution_result("repair", "repair", workspace, package_root, None, False)

        self.assertEqual(excinfo.exception.code, "approval_or_answers_required")

        plan_payload = {"mode": "update", "warnings": ["warn"], "result": {"plannedLockfile": {"contents": {}}, "conflictDetails": []}}
        with mock.patch("scripts.lifecycle._xanad._execute_apply.load_apply_plan", return_value=plan_payload), mock.patch(
            "scripts.lifecycle._xanad._execute_apply.validate_apply_plan_paths"
        ), mock.patch("scripts.lifecycle._xanad._execute_apply.validate_apply_plan_package"), mock.patch(
            "scripts.lifecycle._xanad._execute_apply.execute_apply_plan",
            return_value={"applied": True},
        ), mock.patch(
            "scripts.lifecycle._xanad._execute_apply.build_source_summary",
            return_value={"source": "github:owner/repo", "ref": "main"},
        ):
            payload = _execute_apply.build_apply_result(workspace, package_root, None, False, dry_run=True, plan_path="plan.json")

        self.assertEqual(payload["command"], "apply")
        self.assertEqual(payload["mode"], "update")
        self.assertEqual(payload["warnings"], ["warn"])
        self.assertEqual(payload["result"], {"applied": True})

    def test_validate_apply_plan_paths_rejects_unsupported_actions_and_backup_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            self._write_policy_and_manifest(package_root)
            base_result = self._base_result(backup_root=".xanadAssistant/backups/run")
            cases = [
                {"result": {**base_result, "actions": [{"id": "x", "target": ".github/a.md", "action": "unknown"}]}},
                {
                    "result": {
                        **base_result,
                        "actions": [{"id": "delete:.github/prompts/main.prompt.md", "target": ".github/prompts/main.prompt.md", "action": "delete"}],
                        "backupPlan": {
                            "root": ".xanadAssistant/backups/run",
                            "targets": [{"target": ".github/prompts/main.prompt.md", "backupPath": "outside/main.prompt.md"}],
                            "archiveTargets": [],
                        },
                    }
                },
                {"result": {**base_result, "actions": ["bad-action"]}},
                {"result": {**base_result, "actions": [{"id": "prompts.main", "target": ".github/prompts/other.prompt.md", "action": "replace"}]}},
                {"result": {**base_result, "actions": [{"id": "delete:.github/prompts/other.prompt.md", "target": ".github/prompts/main.prompt.md", "action": "delete"}]}},
                {"result": {**base_result, "actions": [{"id": "retired.prompt", "target": ".github/prompts/other.prompt.md", "action": "archive-retired"}]}},
                {"result": {**base_result, "actions": [{"id": "unknown", "target": ".github/prompts/main.prompt.md", "action": "archive-retired"}]}},
                {
                    "result": {
                        **self._base_result(backup_root=".xanadAssistant/archive/run"),
                        "actions": [],
                    }
                },
                {
                    "result": {
                        **base_result,
                        "actions": [{"id": "delete:.github/prompts/main.prompt.md", "target": ".github/prompts/main.prompt.md", "action": "delete"}],
                        "backupPlan": {
                            "root": ".xanadAssistant/backups/run",
                            "targets": [{"target": ".github/prompts/other.prompt.md", "backupPath": ".xanadAssistant/backups/run/.github/prompts/other.prompt.md"}],
                            "archiveTargets": [],
                        },
                    }
                },
                {
                    "result": {
                        **base_result,
                        "actions": [{"id": "migration.cleanup..github/prompts/old.prompt.md", "target": ".github/prompts/old.prompt.md", "action": "archive-retired"}],
                        "backupPlan": {
                            "root": ".xanadAssistant/backups/run",
                            "archiveRoot": ".xanadAssistant/archive",
                            "targets": [],
                            "archiveTargets": [{"target": ".github/prompts/extra.prompt.md", "archivePath": ".xanadAssistant/archive/.github/prompts/extra.prompt.md"}],
                        },
                    }
                },
                {
                    "result": {
                        **base_result,
                        "actions": [{"id": "migration.cleanup..github/prompts/old.prompt.md", "target": ".github/prompts/old.prompt.md", "action": "archive-retired"}],
                        "backupPlan": {
                            "root": ".xanadAssistant/backups/run",
                            "archiveRoot": ".xanadAssistant/archive",
                            "targets": [],
                            "archiveTargets": [{"target": ".github/prompts/old.prompt.md", "archivePath": "outside/.github/prompts/old.prompt.md"}],
                        },
                    }
                },
            ]

            for payload in cases:
                with self.subTest(payload=payload):
                    self._assert_path_validation_error(payload, package_root)

    def test_load_apply_plan_rejects_invalid_payload_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            workspace.mkdir()
            plan_path = root / "plan.json"

            with self.assertRaises(LifecycleCommandError):
                _execute_apply.load_apply_plan(None, workspace)

            with self.assertRaises(LifecycleCommandError):
                _execute_apply.load_apply_plan(str(root / "missing.json"), workspace)

            plan_path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(LifecycleCommandError):
                _execute_apply.load_apply_plan(str(plan_path), workspace)

            invalid_payloads = [
                [],
                {"command": "inspect", "result": {}},
                {"command": "plan", "mode": "invalid", "workspace": str(workspace), "result": {}},
                {"command": "plan", "mode": "setup", "workspace": str(root / "other"), "result": {}},
                {"command": "plan", "mode": "setup", "workspace": str(workspace), "result": {"plannedLockfile": None}},
                {"command": "plan", "mode": "setup", "workspace": str(workspace), "result": {"plannedLockfile": []}},
                {"command": "plan", "mode": "setup", "workspace": str(workspace), "result": {"plannedLockfile": {"path": 1, "contents": []}}},
            ]

            for payload in invalid_payloads:
                plan_path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(payload=payload):
                    with self.assertRaises(LifecycleCommandError):
                        _execute_apply.load_apply_plan(str(plan_path), workspace)

    def test_validate_apply_plan_package_rejects_package_and_manifest_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            self._write_policy_and_manifest(package_root)

            bad_name = {
                "result": {
                    "plannedLockfile": {
                        "contents": {"package": {"name": "other-package"}, "manifest": {"hash": "sha256:manifest"}}
                    }
                }
            }
            with self.assertRaises(LifecycleCommandError):
                _execute_apply.validate_apply_plan_package(bad_name, package_root)

            mismatched_source = {
                "result": {
                    "plannedLockfile": {
                        "contents": {
                            "package": {"name": "xanadAssistant", "source": "github:owner/repo", "ref": "main"},
                            "manifest": {"hash": "sha256:manifest"},
                        }
                    }
                }
            }
            with mock.patch("scripts.lifecycle._xanad._execute_apply.build_source_summary", return_value={"source": "github:owner/repo", "ref": "dev"}):
                with self.assertRaises(LifecycleCommandError):
                    _execute_apply.validate_apply_plan_package(mismatched_source, package_root)

            bad_hash = {
                "result": {
                    "plannedLockfile": {
                        "contents": {"package": {"name": "xanadAssistant"}, "manifest": {"hash": "sha256:wrong"}}
                    }
                }
            }
            with mock.patch("scripts.lifecycle._xanad._execute_apply.sha256_json", return_value="sha256:current"):
                with self.assertRaises(LifecycleCommandError):
                    _execute_apply.validate_apply_plan_package(bad_hash, package_root)

            version_mismatch = {
                "result": {
                    "plannedLockfile": {
                        "contents": {
                            "package": {"name": "xanadAssistant", "version": "1.0.0"},
                            "manifest": {"hash": "sha256:manifest"},
                        }
                    }
                }
            }
            with mock.patch(
                "scripts.lifecycle._xanad._execute_apply.build_source_summary",
                return_value={"version": "2.0.0"},
            ):
                with self.assertRaises(LifecycleCommandError):
                    _execute_apply.validate_apply_plan_package(version_mismatch, package_root)


class MainDispatchTests(unittest.TestCase):
    def _resolved_package_root(self, tmpdir: str) -> tuple[Path, dict[str, str]]:
        return Path(tmpdir), {"kind": "package-root"}

    def test_run_execution_command_covers_success_and_apply_error_paths(self) -> None:
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

    def test_main_returns_drift_exit_code_for_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._main.build_check_result",
            return_value={"status": "drift", "warnings": [], "errors": [], "result": {}},
        ), mock.patch("scripts.lifecycle._xanad._main.emit_payload"):
            exit_code = main(["check", "--workspace", tmpdir, "--package-root", tmpdir])

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

    def test_main_handles_log_file_open_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "pathlib.Path.open",
            side_effect=OSError("permission denied"),
        ), mock.patch("scripts.lifecycle._xanad._main.emit_payload") as emit_payload:
            exit_code = main(["inspect", "--workspace", tmpdir, "--package-root", tmpdir, "--log-file", str(Path(tmpdir) / "run.log")])

        self.assertEqual(exit_code, 4)
        self.assertTrue(emit_payload.called)

    def test_main_dispatches_apply_and_handles_source_resolution_failure(self) -> None:
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
                exit_code = main(["apply", "--workspace", tmpdir, "--package-root", tmpdir, "--plan", str(plan_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(run_exec.called)

            with mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                side_effect=LifecycleCommandError("contract_input_failure", "bad source", 4),
            ), mock.patch("scripts.lifecycle._xanad._main.emit_payload") as emit_payload:
                failed = main(["inspect", "--workspace", tmpdir, "--package-root", tmpdir])

            self.assertEqual(failed, 4)
            self.assertTrue(emit_payload.called)

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
            (["check", "--workspace", None, "--package-root", None], "scripts.lifecycle._xanad._main.build_check_result", "check failed"),
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


if __name__ == "__main__":
    unittest.main()