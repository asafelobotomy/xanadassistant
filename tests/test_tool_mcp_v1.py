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
                "workspace_show_install_state",
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
