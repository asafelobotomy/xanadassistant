from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad._errors import LifecycleCommandError


class ScriptAuditApplyContractRegressionsTests(unittest.TestCase):
    def test_apply_rejects_plan_with_target_outside_manifest_contract(self) -> None:
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
                            "actions": [
                                {
                                    "id": "managed.prompt",
                                    "action": "replace",
                                    "target": "README.md",
                                }
                            ],
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

            with mock.patch(
                "scripts.lifecycle._xanad._execute_apply.load_manifest",
                return_value={
                    "managedFiles": [
                        {"id": "managed.prompt", "target": ".github/prompts/managed.prompt.md"}
                    ],
                    "retiredFiles": [],
                },
            ), mock.patch(
                "scripts.lifecycle._xanad._execute_apply.load_json",
                return_value={},
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    build_apply_result(
                        workspace,
                        package_root,
                        answers_path=None,
                        non_interactive=True,
                        plan_path=str(plan_path),
                    )

        self.assertEqual(excinfo.exception.code, "contract_input_failure")
        self.assertEqual(excinfo.exception.exit_code, 4)

    def test_apply_uses_serialized_plan_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            plan_path = Path(tmpdir) / "plan.json"
            plan_payload = {
                "command": "plan",
                "mode": "repair",
                "workspace": str(workspace),
                "warnings": [],
                "result": {
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {"package": {}, "manifest": {"hash": "sha256:abc"}},
                    },
                    "actions": [],
                    "backupPlan": {},
                    "skippedActions": [],
                    "writes": {},
                    "factoryRestore": False,
                },
            }
            plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

            with mock.patch(
                "scripts.lifecycle._xanad._execute_apply.execute_apply_plan",
                return_value={"validation": {"status": "passed"}},
            ) as execute_apply, mock.patch(
                "scripts.lifecycle._xanad._execute_apply.load_manifest",
                return_value={"managedFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._execute_apply.load_json",
                return_value={},
            ), mock.patch(
                "scripts.lifecycle._xanad._execute_apply.sha256_json",
                return_value="sha256:abc",
            ):
                from scripts.lifecycle._xanad._execute_apply import build_apply_result

                result = build_apply_result(
                    workspace,
                    package_root,
                    answers_path=None,
                    non_interactive=True,
                    plan_path=str(plan_path),
                )

        execute_apply.assert_called_once()
        self.assertEqual(result["mode"], "repair")

    def test_apply_rejects_plan_from_different_package_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            plan_path = Path(tmpdir) / "plan.json"
            plan_payload = {
                "command": "plan",
                "mode": "repair",
                "workspace": str(workspace),
                "warnings": [],
                "result": {
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"source": "github:owner/repo", "ref": "main"},
                            "manifest": {"hash": "sha256:planned"},
                        },
                    },
                    "actions": [],
                    "backupPlan": {},
                    "skippedActions": [],
                    "writes": {},
                    "factoryRestore": False,
                },
            }
            plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

            from scripts.lifecycle._xanad._execute_apply import build_apply_result

            with mock.patch(
                "scripts.lifecycle._xanad._execute_apply.build_source_summary",
                return_value={
                    "kind": "package-root",
                    "packageRoot": str(package_root),
                    "source": "github:owner/repo",
                    "ref": "feature-branch",
                },
            ), mock.patch(
                "scripts.lifecycle._xanad._execute_apply.load_manifest",
                return_value={"managedFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._execute_apply.load_json",
                return_value={},
            ), mock.patch(
                "scripts.lifecycle._xanad._execute_apply.sha256_json",
                return_value="sha256:current",
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    build_apply_result(
                        workspace,
                        package_root,
                        answers_path=None,
                        non_interactive=True,
                        plan_path=str(plan_path),
                    )

        self.assertEqual(excinfo.exception.code, "contract_input_failure")
        self.assertEqual(excinfo.exception.exit_code, 4)

    def test_apply_rejects_plan_from_predecessor_package_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            plan_path = Path(tmpdir) / "plan.json"
            plan_payload = {
                "command": "plan",
                "mode": "repair",
                "workspace": str(workspace),
                "warnings": [],
                "result": {
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "copilot-instructions-template"},
                            "manifest": {"hash": "sha256:current"},
                        },
                    },
                    "actions": [],
                    "backupPlan": {},
                    "skippedActions": [],
                    "writes": {},
                    "factoryRestore": False,
                },
            }
            plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

            from scripts.lifecycle._xanad._execute_apply import build_apply_result

            with self.assertRaises(LifecycleCommandError) as excinfo:
                build_apply_result(
                    workspace,
                    package_root,
                    answers_path=None,
                    non_interactive=True,
                    plan_path=str(plan_path),
                )

        self.assertEqual(excinfo.exception.code, "contract_input_failure")
        self.assertEqual(excinfo.exception.exit_code, 4)


if __name__ == "__main__":
    unittest.main()