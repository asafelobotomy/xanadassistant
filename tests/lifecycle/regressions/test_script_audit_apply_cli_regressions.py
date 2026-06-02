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

    def test_apply_from_missing_plan_returns_retired_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            workspace = package_root / "workspace"
            workspace.mkdir()
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                exit_code = main([
                    "apply",
                    "--workspace",
                    str(workspace),
                    "--plan",
                    str(package_root / "missing-plan.json"),
                    "--json",
                ])

        self.assertEqual(exit_code, 4)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["errors"][0]["code"], "retired_command")

    def test_apply_retirement_payload_uses_mode_from_serialized_plan(self) -> None:
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

            with redirect_stdout(stdout):
                exit_code = main([
                    "apply",
                    "--workspace",
                    str(workspace),
                    "--plan",
                    str(plan_path),
                    "--json",
                ])

        self.assertEqual(exit_code, 4)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "repair")
        self.assertEqual(payload["errors"][0]["code"], "retired_command")

    def test_apply_retirement_payload_ignores_malformed_plan_payload(self) -> None:
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

            with redirect_stdout(stdout):
                exit_code = main([
                    "apply",
                    "--workspace",
                    str(workspace),
                    "--plan",
                    str(plan_path),
                    "--json",
                ])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 4)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["errors"][0]["code"], "retired_command")
        self.assertIsNone(payload["mode"])

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
                    non_interactive=False,
                    resolutions_path=str(Path(tmpdir) / "resolutions.json"),
                    plan_path=str(plan_path),
                )

        self.assertEqual(excinfo.exception.code, "contract_input_failure")
        self.assertEqual(excinfo.exception.exit_code, 4)

    def test_sanitize_flag_only_accepted_by_repair_and_factory_restore(self) -> None:
        parser = build_parser()

        # --sanitize should be accepted for repair and factory-restore
        for command in ("repair", "factory-restore"):
            with self.subTest(command=command):
                args = parser.parse_args([command, "--workspace", ".", "--package-root", ".", "--sanitize"])
                self.assertTrue(args.sanitize)

        # --sanitize should NOT be accepted for other write commands
        for command in ("setup", "update"):
            with self.subTest(command=command):
                with self.assertRaises(SystemExit):
                    parser.parse_args([command, "--workspace", ".", "--package-root", ".", "--sanitize"])


if __name__ == "__main__":
    unittest.main()
