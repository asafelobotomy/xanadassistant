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


