from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SERVER = REPO_ROOT / "hooks" / "scripts" / "xanad-workspace-mcp.py"


def encode_message(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"


def decode_message(stream) -> dict:
    while True:
        line = stream.readline()
        if not line:
            raise EOFError("Server closed stdout before sending a response")
        line = line.strip()
        if not line:
            continue
        return json.loads(line.decode("utf-8"))


def make_workspace(test_case: unittest.TestCase, source_server: Path = SOURCE_SERVER) -> Path:
    temp_dir = tempfile.TemporaryDirectory()
    test_case.addCleanup(temp_dir.cleanup)
    workspace = Path(temp_dir.name)
    server_dir = workspace / ".github" / "hooks" / "scripts"
    server_dir.mkdir(parents=True, exist_ok=True)
    for companion in SOURCE_SERVER.parent.glob("_*.py"):
        (server_dir / companion.name).write_text(companion.read_text(encoding="utf-8"), encoding="utf-8")
    server_path = server_dir / source_server.name
    server_path.write_text(source_server.read_text(encoding="utf-8"), encoding="utf-8")
    return workspace


def start_server(
    test_case: unittest.TestCase,
    workspace: Path,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    server_path = workspace / ".github" / "hooks" / "scripts" / "xanad-workspace-mcp.py"
    env = dict(os.environ)
    if env_overrides is not None:
        env.update(env_overrides)
    process = subprocess.Popen(
        [sys.executable, str(server_path)],
        cwd=workspace,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    test_case.addCleanup(stop_server, process)
    return process


def stop_server(process: subprocess.Popen[bytes]) -> None:
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


def rpc(process: subprocess.Popen[bytes], payload: dict) -> dict:
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(encode_message(payload))
    process.stdin.flush()
    return decode_message(process.stdout)


def call_tool(
    process: subprocess.Popen[bytes],
    *,
    message_id: int,
    name: str,
    arguments: dict | None = None,
) -> dict:
    return rpc(
        process,
        {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )


def initialize_server(process: subprocess.Popen[bytes], *, message_id: int = 1) -> dict:
    response = rpc(
        process,
        {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        },
    )
    assert process.stdin is not None
    process.stdin.write(encode_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))
    process.stdin.flush()
    return response


def make_fake_cached_release(cache_root: Path, source: str, version: str) -> Path:
    owner, repo = source[len("github:"):].split("/", 1)
    safe_version = version.replace("/", "-")
    package_root = cache_root / "github" / f"{owner}-{repo}" / f"release-{safe_version}"
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / ".complete").write_text("ok\n", encoding="utf-8")
    (package_root / "xanadAssistant.py").write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "payload = {\n"
        "  'command': sys.argv[1],\n"
        "  'status': 'ok',\n"
        "  'argv': sys.argv[2:],\n"
        "  'result': {}\n"
        "}\n"
        "print(json.dumps(payload))\n",
        encoding="utf-8",
    )
    return package_root


def write_key_commands(workspace: Path, rows: list[tuple[str, str]]) -> None:
    instructions_path = workspace / ".github" / "copilot-instructions.md"
    instructions_path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"| {label} | `{command}` |\n" for label, command in rows)
    instructions_path.write_text(
        "# Example\n\n"
        "## Key Commands\n\n"
        "| Task | Command |\n"
        "|------|---------|\n"
        f"{body}",
        encoding="utf-8",
    )


def write_test_runner(workspace: Path) -> None:
    (workspace / "test_runner.py").write_text(
        "import json\n"
        "import sys\n"
        "print(json.dumps({'argv': sys.argv[1:]}))\n",
        encoding="utf-8",
    )