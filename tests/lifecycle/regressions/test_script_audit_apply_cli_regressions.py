from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad._cli import build_parser
from scripts.lifecycle._xanad._errors import LifecycleCommandError
from scripts.lifecycle._xanad._main import main


class ScriptAuditApplyCliRegressionsTests(unittest.TestCase):
    def test_apply_requires_explicit_plan_and_plan_is_not_abbreviated(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit) as excinfo:
            parser.parse_args([
                "apply",
                "--workspace",
                ".",
                "--package-root",
                ".",
                "--pla",
                "plan.json",
            ])

        self.assertEqual(excinfo.exception.code, 2)

    def test_plan_setup_does_not_accept_abbreviated_plan_out_flag(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit) as excinfo:
            parser.parse_args([
                "plan",
                "setup",
                "--workspace",
                ".",
                "--package-root",
                ".",
                "--pla",
                "plan.json",
            ])

        self.assertEqual(excinfo.exception.code, 2)

    def test_apply_from_missing_plan_returns_contract_input_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            workspace = package_root / "workspace"
            workspace.mkdir()

            with mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                return_value=(package_root, {"kind": "package-root", "packageRoot": str(package_root)}),
            ):
                exit_code = main([
                    "apply",
                    "--workspace",
                    str(workspace),
                    "--package-root",
                    str(package_root),
                    "--plan",
                    str(package_root / "missing-plan.json"),
                    "--json",
                ])

        self.assertEqual(exit_code, 4)

    def test_apply_error_payload_uses_mode_from_serialized_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            workspace = package_root / "workspace"
            workspace.mkdir()
            plan_path = package_root / "repair-plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "command": "plan",
                        "mode": "repair",
                        "workspace": str(workspace),
                        "warnings": [],
                        "result": {
                            "plannedLockfile": {
                                "path": ".github/xanadAssistant-lock.json",
                                "contents": {
                                    "package": {"name": "copilot-instructions-template"},
                                    "manifest": {"hash": "sha256:abc"},
                                },
                            },
                            "actions": [],
                            "backupPlan": {},
                            "skippedActions": [],
                            "writes": {},
                            "factoryRestore": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            with mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                return_value=(package_root, {"kind": "package-root", "packageRoot": str(package_root)}),
            ), redirect_stdout(stdout):
                exit_code = main([
                    "apply",
                    "--workspace",
                    str(workspace),
                    "--package-root",
                    str(package_root),
                    "--plan",
                    str(plan_path),
                    "--json",
                ])

        self.assertEqual(exit_code, 4)
        self.assertEqual(json.loads(stdout.getvalue())["mode"], "repair")

    def test_apply_rejects_malformed_planned_lockfile_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            workspace = package_root / "workspace"
            workspace.mkdir()
            plan_path = package_root / "bad-plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "command": "plan",
                        "mode": "repair",
                        "workspace": str(workspace),
                        "warnings": [],
                        "result": {
                            "plannedLockfile": {},
                            "actions": [],
                            "backupPlan": {},
                            "skippedActions": [],
                            "writes": {},
                            "factoryRestore": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()

            with mock.patch(
                "scripts.lifecycle._xanad._main.resolve_effective_package_root",
                return_value=(package_root, {"kind": "package-root", "packageRoot": str(package_root)}),
            ), redirect_stdout(stdout):
                exit_code = main([
                    "apply",
                    "--workspace",
                    str(workspace),
                    "--package-root",
                    str(package_root),
                    "--plan",
                    str(plan_path),
                    "--json",
                ])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 4)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["errors"][0]["code"], "contract_input_failure")

    def test_apply_rejects_resolutions_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            plan_path = Path(tmpdir) / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "command": "plan",
                        "mode": "repair",
                        "workspace": str(workspace),
                        "warnings": [],
                        "result": {
                            "plannedLockfile": {
                                "path": ".github/xanadAssistant-lock.json",
                                "contents": {
                                    "package": {"name": "xanadAssistant"},
                                    "manifest": {"hash": "sha256:abc"},
                                },
                            },
                            "actions": [],
                            "backupPlan": {},
                            "skippedActions": [],
                            "writes": {},
                            "factoryRestore": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            from scripts.lifecycle._xanad._execute_apply import build_apply_result

            with self.assertRaises(LifecycleCommandError) as excinfo:
                build_apply_result(
                    workspace,
                    package_root,
                    answers_path=None,
                    non_interactive=True,
                    resolutions_path=str(Path(tmpdir) / "resolutions.json"),
                    plan_path=str(plan_path),
                )

        self.assertEqual(excinfo.exception.code, "contract_input_failure")
        self.assertEqual(excinfo.exception.exit_code, 4)


if __name__ == "__main__":
    unittest.main()