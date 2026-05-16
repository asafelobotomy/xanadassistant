from __future__ import annotations

import json
import io
import subprocess
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _pack_conflicts
from scripts.lifecycle._xanad import _resolutions
from scripts.lifecycle._xanad._cli import build_parser
from scripts.lifecycle._xanad._errors import LifecycleCommandError
from scripts.lifecycle._xanad._inspect_helpers import collect_successor_migration_files
from scripts.lifecycle._xanad._main import main
from scripts.lifecycle._xanad._source_remote import resolve_github_ref, resolve_github_release


class ScriptAuditRegressionsTests(unittest.TestCase):
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

    def test_load_resolutions_raises_structured_contract_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "resolutions.json"
            path.write_text("{not-json", encoding="utf-8")

            with self.assertRaises(LifecycleCommandError) as excinfo:
                _resolutions.load_resolutions(str(path))

        self.assertEqual(excinfo.exception.code, "contract_input_failure")
        self.assertEqual(excinfo.exception.exit_code, 4)

    def test_successor_cleanup_ignores_current_copilot_version_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            extra_file = workspace / ".github" / "prompts" / "extra.prompt.md"
            extra_file.parent.mkdir(parents=True, exist_ok=True)
            extra_file.write_text("extra\n", encoding="utf-8")
            predecessor_marker = workspace / ".github" / "hooks" / "copilot-hooks.json"
            predecessor_marker.parent.mkdir(parents=True, exist_ok=True)
            predecessor_marker.write_text("{}\n", encoding="utf-8")
            summary = workspace / ".github" / "copilot-version.md"
            summary.write_text("current summary\n", encoding="utf-8")

            cleanup_targets = collect_successor_migration_files(
                workspace,
                {"managedFiles": [], "retiredFiles": []},
                {"present": True, "data": {"package": {"name": "copilot-instructions-template"}}},
                {"present": True},
            )

        self.assertIn(".github/prompts/extra.prompt.md", cleanup_targets)
        self.assertNotIn(".github/copilot-version.md", cleanup_targets)

    def test_successor_cleanup_uses_legacy_summary_when_lockfile_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            extra_file = workspace / ".github" / "prompts" / "legacy.prompt.md"
            extra_file.parent.mkdir(parents=True, exist_ok=True)
            extra_file.write_text("legacy\n", encoding="utf-8")
            summary = workspace / ".github" / "copilot-version.md"
            summary.write_text("legacy summary\n", encoding="utf-8")

            cleanup_targets = collect_successor_migration_files(
                workspace,
                {"managedFiles": [], "retiredFiles": []},
                {"present": False, "data": {}},
                {"present": True},
            )

        self.assertIn(".github/prompts/legacy.prompt.md", cleanup_targets)
        self.assertNotIn(".github/copilot-version.md", cleanup_targets)

    def test_pack_conflict_questions_match_interview_schema(self) -> None:
        questions = _pack_conflicts.build_conflict_questions([
            {
                "token": "pack:output-style",
                "questionId": "resolvedTokenConflicts.pack:output-style",
                "packs": ["alpha", "beta"],
                "candidates": {"alpha": "A", "beta": "B"},
            }
        ])

        self.assertEqual(questions[0]["id"], "resolvedTokenConflicts.pack:output-style")
        self.assertEqual(questions[0]["kind"], "choice")
        self.assertIn("Choose which pack's value to use", questions[0]["prompt"])
        self.assertEqual(questions[0]["options"], ["alpha", "beta"])

    def test_remote_source_failures_use_exit_code_three(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)

            with mock.patch("urllib.request.urlopen", side_effect=RuntimeError("network down")):
                with self.assertRaises(LifecycleCommandError) as release_exc:
                    resolve_github_release("owner", "repo", "v1.0.0", cache_root)

            self.assertEqual(release_exc.exception.exit_code, 3)

            error = subprocess.CalledProcessError(1, ["git"], stderr=b"fatal: nope")
            with mock.patch("subprocess.run", side_effect=error):
                with self.assertRaises(LifecycleCommandError) as ref_exc:
                    resolve_github_ref("owner", "repo", "main", cache_root)

            self.assertEqual(ref_exc.exception.exit_code, 3)

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
                "result": {"plannedLockfile": {"path": ".github/xanadAssistant-lock.json", "contents": {"package": {}, "manifest": {"hash": "sha256:abc"}}}, "actions": [], "backupPlan": {}, "skippedActions": [], "writes": {}, "factoryRestore": False},
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
                return_value={"kind": "package-root", "packageRoot": str(package_root), "source": "github:owner/repo", "ref": "feature-branch"},
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

    def test_apply_rolls_back_lockfile_and_summary_when_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            github_dir = workspace / ".github"
            github_dir.mkdir()
            original_lockfile = github_dir / "xanadAssistant-lock.json"
            original_summary = github_dir / "copilot-version.md"
            original_lockfile.write_text('{"previous": true}\n', encoding="utf-8")
            original_summary.write_text("previous summary\n", encoding="utf-8")

            plan_payload = {
                "result": {
                    "actions": [],
                    "backupPlan": {},
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "setupAnswers": {},
                        },
                    },
                    "factoryRestore": False,
                    "skippedActions": [],
                    "writes": {},
                }
            }

            from scripts.lifecycle._xanad._execute_apply import execute_apply_plan

            with mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_manifest",
                return_value={"managedFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_json",
                return_value={},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.build_copilot_version_summary",
                return_value="new summary\n",
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor._check.build_check_result",
                return_value={"status": "drift", "result": {"summary": {"missing": 1}}},
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

                self.assertEqual(excinfo.exception.code, "apply_failure")
                self.assertEqual(excinfo.exception.exit_code, 9)
                self.assertTrue(excinfo.exception.details["rolledBack"])
                self.assertEqual(original_lockfile.read_text(encoding="utf-8"), '{"previous": true}\n')
                self.assertEqual(original_summary.read_text(encoding="utf-8"), "previous summary\n")

    def test_apply_restores_retired_file_when_validation_fails_after_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            retired_file = workspace / ".github" / "prompts" / "legacy.prompt.md"
            retired_file.parent.mkdir(parents=True, exist_ok=True)
            retired_file.write_text("legacy\n", encoding="utf-8")

            plan_payload = {
                "result": {
                    "actions": [
                        {
                            "id": "retired.legacy",
                            "action": "archive-retired",
                            "target": ".github/prompts/legacy.prompt.md",
                        }
                    ],
                    "backupPlan": {
                        "root": ".xanadAssistant/backups/<apply-timestamp>",
                        "targets": [],
                        "archiveTargets": [
                            {
                                "target": ".github/prompts/legacy.prompt.md",
                                "archivePath": ".xanadAssistant/archive/.github/prompts/legacy.prompt.md",
                            }
                        ],
                    },
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "setupAnswers": {},
                        },
                    },
                    "factoryRestore": False,
                    "skippedActions": [],
                    "writes": {"archiveRetired": 1},
                }
            }

            from scripts.lifecycle._xanad._execute_apply import execute_apply_plan

            with mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_manifest",
                return_value={"managedFiles": [], "retiredFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_json",
                return_value={},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.build_copilot_version_summary",
                return_value="new summary\n",
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor._check.build_check_result",
                return_value={"status": "drift", "result": {"summary": {"retired": 1}}},
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

                self.assertEqual(excinfo.exception.code, "apply_failure")
                self.assertTrue(excinfo.exception.details["rolledBack"])
                self.assertEqual(retired_file.read_text(encoding="utf-8"), "legacy\n")
                self.assertFalse((workspace / ".xanadAssistant" / "archive" / ".github" / "prompts" / "legacy.prompt.md").exists())

    def test_apply_wraps_backup_copy_failure_in_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            target = workspace / "managed.txt"
            target.write_text("managed\n", encoding="utf-8")
            plan_payload = {
                "result": {
                    "actions": [{"id": "managed.txt", "action": "delete", "target": "managed.txt"}],
                    "backupPlan": {
                        "root": ".xanadAssistant/backups/<apply-timestamp>",
                        "targets": [{"target": "managed.txt", "backupPath": ".xanadAssistant/backups/<apply-timestamp>/managed.txt"}],
                        "archiveTargets": [],
                    },
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "setupAnswers": {},
                        },
                    },
                    "factoryRestore": False,
                    "skippedActions": [],
                    "writes": {"deleted": 1},
                }
            }

            from scripts.lifecycle._xanad._execute_apply import execute_apply_plan

            with mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_manifest",
                return_value={"managedFiles": [], "retiredFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_json",
                return_value={},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor._copy_backup_file",
                side_effect=OSError("backup copy failed"),
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

                self.assertEqual(excinfo.exception.code, "apply_failure")
                self.assertEqual(excinfo.exception.exit_code, 9)
                self.assertTrue(excinfo.exception.details["rolledBack"])
                self.assertEqual(target.read_text(encoding="utf-8"), "managed\n")

    def test_apply_wraps_lockfile_write_failure_in_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            plan_payload = {
                "result": {
                    "actions": [],
                    "backupPlan": {},
                    "plannedLockfile": {
                        "path": ".github/xanadAssistant-lock.json",
                        "contents": {
                            "package": {"name": "xanadAssistant"},
                            "manifest": {"hash": "sha256:abc"},
                            "setupAnswers": {},
                        },
                    },
                    "factoryRestore": False,
                    "skippedActions": [],
                    "writes": {},
                }
            }

            from scripts.lifecycle._xanad._execute_apply import execute_apply_plan

            with mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_manifest",
                return_value={"managedFiles": [], "retiredFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor.load_json",
                return_value={},
            ), mock.patch(
                "scripts.lifecycle._xanad._apply_executor._write_lockfile",
                side_effect=OSError("disk full"),
            ):
                with self.assertRaises(LifecycleCommandError) as excinfo:
                    execute_apply_plan(workspace, package_root, plan_payload)

                self.assertEqual(excinfo.exception.code, "apply_failure")
                self.assertEqual(excinfo.exception.exit_code, 9)
                self.assertTrue(excinfo.exception.details["rolledBack"])
                self.assertFalse((workspace / ".github" / "xanadAssistant-lock.json").exists())


if __name__ == "__main__":
    unittest.main()