from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._mcp_test_utils import (
    REPO_ROOT,
    call_tool,
    initialize_server,
    make_fake_cached_release,
    make_workspace,
    rpc,
    start_server,
    write_key_commands,
    write_test_runner,
)


class ToolMcpV1Tests(unittest.TestCase):
    REPO_ROOT = REPO_ROOT

    def test_initialize_and_tools_list_use_stdio_protocol(self) -> None:
        workspace = make_workspace(self)
        process = start_server(self, workspace)
        init_response = initialize_server(process)
        self.assertEqual("xanadTools", init_response["result"]["serverInfo"]["name"])
        tools_response = rpc(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tool_names = {tool["name"] for tool in tools_response["result"]["tools"]}
        self.assertEqual(
            {
                "workspace_show_key_commands",
                "workspace_run_tests",
                "workspace_run_check_loc",
                "workspace_validate_lockfile",
                "lifecycle_inspect",
                "lifecycle_check",
                "lifecycle_interview",
                "lifecycle_plan_setup",
                "lifecycle_apply",
                "lifecycle_update",
                "lifecycle_repair",
                "lifecycle_factory_restore",
            },
            tool_names,
        )

    def test_show_key_commands_reads_managed_instructions(self) -> None:
        workspace = make_workspace(self)
        write_key_commands(workspace, [("Run tests", "python3 -m unittest"), ("Check state", "python3 tool.py check")])
        process = start_server(self, workspace)
        initialize_server(process)
        response = call_tool(process, message_id=3, name="workspace_show_key_commands")
        result = response["result"]["structuredContent"]
        self.assertEqual("ok", result["status"])
        self.assertEqual("Run tests", result["commands"][0]["label"])
        self.assertEqual("python3 -m unittest", result["commands"][0]["command"])

    def test_run_tests_uses_rendered_command_and_extra_args(self) -> None:
        workspace = make_workspace(self)
        write_key_commands(workspace, [("Run tests", "python3 test_runner.py")])
        write_test_runner(workspace)
        process = start_server(self, workspace)
        initialize_server(process)
        response = call_tool(
            process,
            message_id=4,
            name="workspace_run_tests",
            arguments={"extraArgs": ["tests.test_metadata_contracts"]},
        )
        result = response["result"]["structuredContent"]
        self.assertEqual("ok", result["status"])
        self.assertIn("python3 test_runner.py tests.test_metadata_contracts", result["command"])
        self.assertIn("tests.test_metadata_contracts", result["stdoutTail"])

    def test_run_tests_scope_full_runs_declared_command_without_extra_args(self) -> None:
        workspace = make_workspace(self)
        write_key_commands(workspace, [("Run tests", "python3 test_runner.py")])
        write_test_runner(workspace)
        process = start_server(self, workspace)
        initialize_server(process)
        response = call_tool(
            process,
            message_id=4,
            name="workspace_run_tests",
            arguments={"scope": "full"},
        )
        result = response["result"]["structuredContent"]
        self.assertEqual("ok", result["status"])
        self.assertEqual("python3 test_runner.py", result["command"])
        self.assertIn('"argv": []', result["stdoutTail"])

    def test_run_tests_scope_full_rejects_extra_args(self) -> None:
        workspace = make_workspace(self)
        write_key_commands(workspace, [("Run tests", "python3 test_runner.py")])
        process = start_server(self, workspace)
        initialize_server(process)
        response = call_tool(
            process,
            message_id=4,
            name="workspace_run_tests",
            arguments={"scope": "full", "extraArgs": ["tests.test_metadata_contracts"]},
        )
        result = response["result"]["structuredContent"]
        self.assertEqual("unavailable", result["status"])
        self.assertIn("scope=full", result["summary"])

    def test_run_check_loc_is_unavailable_without_repo_contract(self) -> None:
        workspace = make_workspace(self)
        process = start_server(self, workspace)
        initialize_server(process)

        response = call_tool(process, message_id=5, name="workspace_run_check_loc")
        result = response["result"]["structuredContent"]
        self.assertEqual("unavailable", result["status"])

    def test_lifecycle_inspect_uses_explicit_package_root(self) -> None:
        workspace = make_workspace(self)
        process = start_server(self, workspace)
        initialize_server(process)
        response = call_tool(
            process,
            message_id=6,
            name="lifecycle_inspect",
            arguments={"packageRoot": str(self.REPO_ROOT)},
        )
        result = response["result"]["structuredContent"]
        self.assertEqual("ok", result["status"])
        self.assertEqual(0, result["exitCode"])
        self.assertEqual("inspect", result["payload"]["command"])
        self.assertEqual("ok", result["payload"]["status"])

    def test_lifecycle_apply_can_use_package_root_recorded_in_lockfile(self) -> None:
        workspace = make_workspace(self)
        github_dir = workspace / ".github"
        github_dir.mkdir(parents=True, exist_ok=True)
        (github_dir / "xanad-assistant-lock.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "0.1.0",
                    "package": {"name": "xanad-assistant", "packageRoot": str(self.REPO_ROOT)},
                    "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                    "timestamps": {
                        "appliedAt": "2026-05-08T00:00:00Z",
                        "updatedAt": "2026-05-08T00:00:00Z"
                    },
                    "selectedPacks": [],
                    "files": []
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        process = start_server(self, workspace)
        initialize_server(process)

        response = call_tool(
            process,
            message_id=7,
            name="lifecycle_apply",
            arguments={"nonInteractive": True},
        )
        result = response["result"]["structuredContent"]
        self.assertEqual("ok", result["status"])
        self.assertEqual(0, result["exitCode"])
        self.assertEqual("apply", result["payload"]["command"])
        self.assertTrue((workspace / ".github" / "copilot-instructions.md").exists())

    def test_lifecycle_plan_setup_is_unavailable_without_package_root(self) -> None:
        workspace = make_workspace(self)
        process = start_server(self, workspace)
        initialize_server(process)
        response = call_tool(
            process,
            message_id=8,
            name="lifecycle_plan_setup",
            arguments={"nonInteractive": True},
        )
        result = response["result"]["structuredContent"]
        self.assertEqual("unavailable", result["status"])
        self.assertIn("packageRoot", result["summary"])

    def test_lifecycle_inspect_uses_explicit_remote_release_source(self) -> None:
        workspace = make_workspace(self)
        with tempfile.TemporaryDirectory() as cache_dir:
            cache_root = Path(cache_dir)
            make_fake_cached_release(cache_root, "github:testowner/testrepo", "v1.2.3")

            process = start_server(self, workspace, env_overrides={"XANAD_PKG_CACHE": str(cache_root)})
            initialize_server(process)

            response = call_tool(
                process,
                message_id=9,
                name="lifecycle_inspect",
                arguments={"source": "github:testowner/testrepo", "version": "v1.2.3"},
            )
            result = response["result"]["structuredContent"]
            self.assertEqual("ok", result["status"])
            self.assertEqual(0, result["exitCode"])
            self.assertEqual("inspect", result["payload"]["command"])
            self.assertIn("--workspace", result["payload"]["argv"])

    def test_lifecycle_check_uses_lockfile_remote_release_source(self) -> None:
        workspace = make_workspace(self)
        github_dir = workspace / ".github"
        github_dir.mkdir(parents=True, exist_ok=True)
        (github_dir / "xanad-assistant-lock.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "0.1.0",
                    "package": {
                        "name": "xanad-assistant",
                        "source": "github:testowner/testrepo",
                        "version": "v1.2.3"
                    },
                    "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                    "timestamps": {
                        "appliedAt": "2026-05-08T00:00:00Z",
                        "updatedAt": "2026-05-08T00:00:00Z"
                    },
                    "selectedPacks": [],
                    "files": []
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        with tempfile.TemporaryDirectory() as cache_dir:
            cache_root = Path(cache_dir)
            make_fake_cached_release(cache_root, "github:testowner/testrepo", "v1.2.3")

            process = start_server(self, workspace, env_overrides={"XANAD_PKG_CACHE": str(cache_root)})
            initialize_server(process)

            response = call_tool(process, message_id=10, name="lifecycle_check")
            result = response["result"]["structuredContent"]
            self.assertEqual("ok", result["status"])
            self.assertEqual(0, result["exitCode"])
            self.assertEqual("check", result["payload"]["command"])

    def test_lifecycle_interview_emits_mode_as_named_flag(self) -> None:
        workspace = make_workspace(self)
        with tempfile.TemporaryDirectory() as cache_dir:
            cache_root = Path(cache_dir)
            make_fake_cached_release(cache_root, "github:testowner/testrepo", "v1.2.3")
            process = start_server(self, workspace, env_overrides={"XANAD_PKG_CACHE": str(cache_root)})
            initialize_server(process)
            response = call_tool(
                process,
                message_id=11,
                name="lifecycle_interview",
                arguments={"source": "github:testowner/testrepo", "version": "v1.2.3", "mode": "update"},
            )
            result = response["result"]["structuredContent"]
            self.assertEqual("ok", result["status"])
            argv = result["payload"]["argv"]
            self.assertIn("--mode", argv, "interview should emit --mode as a named flag, not a positional")
            mode_idx = argv.index("--mode")
            self.assertEqual("update", argv[mode_idx + 1])
            self.assertNotIn("update", argv[:mode_idx], "mode value must not appear before --mode")

    def test_workspace_validate_lockfile_is_unavailable_without_lockfile(self) -> None:
        workspace = make_workspace(self)
        process = start_server(self, workspace)
        initialize_server(process)
        response = call_tool(process, message_id=12, name="workspace_validate_lockfile")
        result = response["result"]["structuredContent"]
        self.assertEqual("unavailable", result["status"])

    def test_workspace_validate_lockfile_returns_ok_for_valid_lockfile(self) -> None:
        workspace = make_workspace(self)
        github_dir = workspace / ".github"
        github_dir.mkdir(parents=True, exist_ok=True)
        (github_dir / "xanad-assistant-lock.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "0.1.0",
                    "package": {"name": "xanad-assistant", "packageRoot": "/tmp/fake"},
                    "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                    "timestamps": {"appliedAt": "2026-05-10T00:00:00Z", "updatedAt": "2026-05-10T00:00:00Z"},
                    "selectedPacks": [],
                    "files": [],
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        process = start_server(self, workspace)
        initialize_server(process)
        response = call_tool(process, message_id=13, name="workspace_validate_lockfile")
        result = response["result"]["structuredContent"]
        self.assertEqual("ok", result["status"])
        self.assertIn("schemaVersion", result["lockfile"])
