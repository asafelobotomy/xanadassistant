#!/usr/bin/env python3

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path


PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "xanadTools"
SERVER_VERSION = "0.1.0"


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def parse_key_commands(instructions_path: Path) -> list[dict[str, str]]:
    if not instructions_path.exists():
        return []

    lines = instructions_path.read_text(encoding="utf-8").splitlines()
    in_key_commands = False
    commands: list[dict[str, str]] = []
    for line in lines:
        if line.strip() == "## Key Commands":
            in_key_commands = True
            continue
        if in_key_commands and line.startswith("## "):
            break
        if not in_key_commands or not line.startswith("|"):
            continue

        columns = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(columns) != 2 or columns[0] == "Task" or set(columns[0]) == {"-"}:
            continue
        commands.append({"label": columns[0], "command": columns[1].strip("`")})
    return commands


def resolve_key_command(label: str) -> str | None:
    instructions_path = workspace_root() / ".github" / "copilot-instructions.md"
    for entry in parse_key_commands(instructions_path):
        if entry["label"] == label:
            return entry["command"]
    return None


def resolve_check_loc_command() -> list[str] | None:
    root = workspace_root()
    if (root / "scripts" / "check_loc.py").exists():
        return ["python3", "scripts/check_loc.py"]
    return None


def reject_shell_metacharacters(command: str) -> str | None:
    forbidden = ["|", "&", ";", ">", "<", "\n", "\r", "`", "$((", "$("]
    for token in forbidden:
        if token in command:
            return f"command contains unsupported shell syntax: {token}"
    return None


def tail_text(text: str, *, max_lines: int = 20, max_chars: int = 4000) -> str | None:
    if not text:
        return None
    lines = text.splitlines()[-max_lines:]
    tail = "\n".join(lines)
    if len(tail) > max_chars:
        tail = tail[-max_chars:]
    return tail


def build_tool_result(*, status: str, summary: str, command: str | None = None, exit_code: int | None = None, stdout: str = "", stderr: str = "") -> dict:
    result = {
        "status": status,
        "summary": summary,
    }
    if command is not None:
        result["command"] = command
    if exit_code is not None:
        result["exitCode"] = exit_code
    stdout_tail = tail_text(stdout)
    stderr_tail = tail_text(stderr)
    if stdout_tail is not None:
        result["stdoutTail"] = stdout_tail
    if stderr_tail is not None:
        result["stderrTail"] = stderr_tail
    return result


def run_argv(argv: list[str]) -> dict:
    completed = subprocess.run(
        argv,
        cwd=workspace_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    status = "ok" if completed.returncode == 0 else "failed"
    summary = "Command completed successfully." if status == "ok" else "Command failed."
    return build_tool_result(
        status=status,
        summary=summary,
        command=shlex.join(argv),
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def tool_workspace_show_key_commands(arguments: dict) -> dict:
    del arguments
    commands = parse_key_commands(workspace_root() / ".github" / "copilot-instructions.md")
    if not commands:
        return {
            "status": "unavailable",
            "commands": [],
            "summary": "No key commands were found in .github/copilot-instructions.md.",
        }
    return {
        "status": "ok",
        "commands": commands,
        "summary": f"Discovered {len(commands)} key command(s).",
    }


def tool_workspace_run_tests(arguments: dict) -> dict:
    extra_args = arguments.get("extraArgs", [])
    if not isinstance(extra_args, list) or not all(isinstance(arg, str) for arg in extra_args):
        return build_tool_result(status="unavailable", summary="extraArgs must be a string array.")

    command = resolve_key_command("Run tests")
    if command is None:
        return build_tool_result(status="unavailable", summary="No Run tests command is declared in .github/copilot-instructions.md.")

    reason = reject_shell_metacharacters(command)
    if reason is not None:
        return build_tool_result(status="unavailable", summary=reason, command=command)

    argv = shlex.split(command) + extra_args
    return run_argv(argv)


def tool_workspace_run_check_loc(arguments: dict) -> dict:
    del arguments
    argv = resolve_check_loc_command()
    if argv is None:
        return build_tool_result(status="unavailable", summary="No repo-local LOC gate is available in this workspace.")
    return run_argv(argv)


TOOLS = {
    "workspace.show_key_commands": {
        "title": "Show Key Commands",
        "description": "Return the commands declared in .github/copilot-instructions.md.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "handler": tool_workspace_show_key_commands,
    },
    "workspace.run_tests": {
        "title": "Run Workspace Tests",
        "description": "Run the workspace test command declared in .github/copilot-instructions.md.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["default", "full"],
                },
                "extraArgs": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
        },
        "handler": tool_workspace_run_tests,
    },
    "workspace.run_check_loc": {
        "title": "Run LOC Gate",
        "description": "Run the repo-local LOC gate when this workspace defines one.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "handler": tool_workspace_run_check_loc,
    },
}


def success_response(message_id: int | str, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def error_response(message_id: int | str | None, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def handle_request(request: dict) -> dict | None:
    message_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return success_response(
            message_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return success_response(message_id, {})
    if method == "tools/list":
        tools = []
        for name, spec in TOOLS.items():
            tools.append(
                {
                    "name": name,
                    "title": spec["title"],
                    "description": spec["description"],
                    "inputSchema": spec["inputSchema"],
                }
            )
        return success_response(message_id, {"tools": tools})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name not in TOOLS:
            return error_response(message_id, -32602, f"Unknown tool: {name}")
        if not isinstance(arguments, dict):
            return error_response(message_id, -32602, "Tool arguments must be an object.")
        result = TOOLS[name]["handler"](arguments)
        return success_response(
            message_id,
            {
                "content": [{"type": "text", "text": json.dumps(result, indent=2, sort_keys=True)}],
                "structuredContent": result,
                "isError": result.get("status") not in {"ok"},
            },
        )
    return error_response(message_id, -32601, f"Method not found: {method}")


def read_message(stream) -> dict | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("utf-8").partition(":")
        headers[key.strip().lower()] = value.strip()

    content_length = headers.get("content-length")
    if content_length is None:
        raise ValueError("Missing Content-Length header")
    body = stream.read(int(content_length))
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def write_message(stream, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    stream.write(header)
    stream.write(body)
    stream.flush()


def main() -> int:
    input_stream = sys.stdin.buffer
    output_stream = sys.stdout.buffer
    while True:
        try:
            request = read_message(input_stream)
            if request is None:
                break
            response = handle_request(request)
        except Exception as exc:  # pragma: no cover - defensive protocol guard
            response = error_response(None, -32603, f"Internal error: {exc}")
        if response is not None:
            write_message(output_stream, response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())