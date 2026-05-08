from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def encode_message(payload: dict) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8") + body


def decode_message(stream) -> dict:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("utf-8").partition(":")
        headers[key.strip().lower()] = value.strip()
    body = stream.read(int(headers["content-length"]))
    return json.loads(body.decode("utf-8"))


class ToolMcpV1Tests(unittest.TestCase):
    REPO_ROOT = Path(__file__).resolve().parents[1]
    SOURCE_SERVER = REPO_ROOT / "hooks" / "scripts" / "xanad-workspace-mcp.py"

    def make_workspace(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        workspace = Path(temp_dir.name)
        server_path = workspace / ".github" / "hooks" / "scripts" / "xanad-workspace-mcp.py"
        server_path.parent.mkdir(parents=True, exist_ok=True)
        server_path.write_text(self.SOURCE_SERVER.read_text(encoding="utf-8"), encoding="utf-8")
        return workspace

    def start_server(self, workspace: Path) -> subprocess.Popen[bytes]:
        server_path = workspace / ".github" / "hooks" / "scripts" / "xanad-workspace-mcp.py"
        process = subprocess.Popen(
            [sys.executable, str(server_path)],
            cwd=workspace,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.addCleanup(self.stop_server, process)
        return process

    def stop_server(self, process: subprocess.Popen[bytes]) -> None:
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if process.stdout is not None and not process.stdout.closed:
            process.stdout.close()
        if process.stderr is not None and not process.stderr.closed:
            process.stderr.close()

    def rpc(self, process: subprocess.Popen[bytes], payload: dict) -> dict:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(encode_message(payload))
        process.stdin.flush()
        return decode_message(process.stdout)

    def test_initialize_and_tools_list_use_stdio_protocol(self) -> None:
        workspace = self.make_workspace()
        process = self.start_server(workspace)

        init_response = self.rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            },
        )
        self.assertEqual("xanadTools", init_response["result"]["serverInfo"]["name"])

        assert process.stdin is not None
        process.stdin.write(encode_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        process.stdin.flush()

        tools_response = self.rpc(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tool_names = {tool["name"] for tool in tools_response["result"]["tools"]}
        self.assertEqual(
            {"workspace.show_key_commands", "workspace.run_tests", "workspace.run_check_loc"},
            tool_names,
        )

    def test_show_key_commands_reads_managed_instructions(self) -> None:
        workspace = self.make_workspace()
        instructions_path = workspace / ".github" / "copilot-instructions.md"
        instructions_path.parent.mkdir(parents=True, exist_ok=True)
        instructions_path.write_text(
            "# Example\n\n"
            "## Key Commands\n\n"
            "| Task | Command |\n"
            "|------|---------|\n"
            "| Run tests | `python3 -m unittest` |\n"
            "| Check state | `python3 tool.py check` |\n",
            encoding="utf-8",
        )

        process = self.start_server(workspace)
        self.rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            },
        )
        assert process.stdin is not None
        process.stdin.write(encode_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        process.stdin.flush()

        response = self.rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "workspace.show_key_commands", "arguments": {}},
            },
        )
        result = response["result"]["structuredContent"]
        self.assertEqual("ok", result["status"])
        self.assertEqual("Run tests", result["commands"][0]["label"])
        self.assertEqual("python3 -m unittest", result["commands"][0]["command"])

    def test_run_tests_uses_rendered_command_and_extra_args(self) -> None:
        workspace = self.make_workspace()
        instructions_path = workspace / ".github" / "copilot-instructions.md"
        instructions_path.parent.mkdir(parents=True, exist_ok=True)
        instructions_path.write_text(
            "# Example\n\n"
            "## Key Commands\n\n"
            "| Task | Command |\n"
            "|------|---------|\n"
            "| Run tests | `python3 test_runner.py` |\n",
            encoding="utf-8",
        )
        (workspace / "test_runner.py").write_text(
            "import json\n"
            "import sys\n"
            "print(json.dumps({'argv': sys.argv[1:]}))\n",
            encoding="utf-8",
        )

        process = self.start_server(workspace)
        self.rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            },
        )
        assert process.stdin is not None
        process.stdin.write(encode_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        process.stdin.flush()

        response = self.rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "workspace.run_tests",
                    "arguments": {"extraArgs": ["tests.test_metadata_contracts"]},
                },
            },
        )
        result = response["result"]["structuredContent"]
        self.assertEqual("ok", result["status"])
        self.assertIn("python3 test_runner.py tests.test_metadata_contracts", result["command"])
        self.assertIn("tests.test_metadata_contracts", result["stdoutTail"])

    def test_run_check_loc_is_unavailable_without_repo_contract(self) -> None:
        workspace = self.make_workspace()
        process = self.start_server(workspace)
        self.rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            },
        )
        assert process.stdin is not None
        process.stdin.write(encode_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        process.stdin.flush()

        response = self.rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "workspace.run_check_loc", "arguments": {}},
            },
        )
        result = response["result"]["structuredContent"]
        self.assertEqual("unavailable", result["status"])
