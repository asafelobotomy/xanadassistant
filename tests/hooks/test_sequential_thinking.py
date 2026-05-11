"""Behavioral tests for hooks/scripts/mcp-sequential-thinking-server.py.

Tests are skipped unless the 'mcp' package is importable. Install it with:
    pip install 'mcp[cli]'

FastMCP 1.x uses newline-delimited JSON for stdio transport.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = REPO_ROOT / "hooks" / "scripts" / "mcp-sequential-thinking-server.py"

_MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


def _encode(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"


def _decode_next(stream) -> dict:
    """Read the next JSON line from stream, skipping blank lines."""
    while True:
        line = stream.readline()
        if not line:
            raise EOFError("Server closed stdout")
        line = line.strip()
        if not line:
            continue
        return json.loads(line.decode("utf-8"))


def _rpc(process: subprocess.Popen, payload: dict) -> dict:
    """Send a JSON-RPC request and return the response (skip notifications)."""
    assert process.stdin is not None
    assert process.stdout is not None
    request_id = payload.get("id")
    process.stdin.write(_encode(payload))
    process.stdin.flush()
    for _ in range(20):
        msg = _decode_next(process.stdout)
        if msg.get("id") == request_id:
            return msg
    raise RuntimeError("No response with matching id received")


def _start_server(test_case: unittest.TestCase) -> subprocess.Popen:
    process = subprocess.Popen(
        [sys.executable, str(SERVER_PATH)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    test_case.addCleanup(_stop_server, process)
    return process


def _stop_server(process: subprocess.Popen) -> None:
    if process.stdin and not process.stdin.closed:
        process.stdin.close()
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def _initialize(process: subprocess.Popen) -> None:
    _rpc(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"},
    }})
    assert process.stdin is not None
    process.stdin.write(_encode({"jsonrpc": "2.0", "method": "notifications/initialized"}))
    process.stdin.flush()


def _call_tool(process: subprocess.Popen, *, message_id: int, name: str, arguments: dict) -> dict:
    return _rpc(process, {
        "jsonrpc": "2.0", "id": message_id, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })


def _think(process: subprocess.Popen, message_id: int, **kwargs) -> dict:
    defaults = {"thought": "test", "next_thought_needed": False, "thought_number": 1, "total_thoughts": 1}
    defaults.update(kwargs)
    return _call_tool(process, message_id=message_id, name="sequentialthinking", arguments=defaults)


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class SequentialThinkingBehavioralTests(unittest.TestCase):

    def test_basic_thought_returns_expected_structure(self) -> None:
        process = _start_server(self)
        _initialize(process)
        response = _think(process, 2, thought="step one", thought_number=1, total_thoughts=3, next_thought_needed=True)
        self.assertFalse(response["result"].get("isError"))
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(1, content["thought_number"])
        self.assertEqual(3, content["total_thoughts"])
        self.assertTrue(content["next_thought_needed"])
        self.assertEqual(1, content["thought_history_length"])
        self.assertEqual([], content["branches"])

    def test_thought_content_too_long_returns_error(self) -> None:
        process = _start_server(self)
        _initialize(process)
        oversized = "x" * (32_768 + 1)
        response = _think(process, 2, thought=oversized)
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual("failed", content["status"])
        self.assertIn("exceeds maximum length", content["error"])

    def test_thought_number_below_one_returns_error(self) -> None:
        process = _start_server(self)
        _initialize(process)
        response = _think(process, 2, thought_number=0, total_thoughts=1)
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual("failed", content["status"])
        self.assertIn("thought_number", content["error"])

    def test_total_thoughts_below_one_returns_error(self) -> None:
        process = _start_server(self)
        _initialize(process)
        response = _think(process, 2, thought_number=1, total_thoughts=0)
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual("failed", content["status"])
        self.assertIn("total_thoughts", content["error"])

    def test_revises_thought_must_reference_recorded_thought(self) -> None:
        process = _start_server(self)
        _initialize(process)
        # Record thought #1
        _think(process, 2, thought_number=1, total_thoughts=3, next_thought_needed=True)
        # Revise thought #99 which was never recorded
        response = _think(process, 3, thought_number=2, total_thoughts=3,
                          next_thought_needed=False, is_revision=True, revises_thought=99)
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual("failed", content["status"])
        self.assertIn("revises_thought", content["error"])

    def test_branch_id_with_invalid_characters_returns_error(self) -> None:
        process = _start_server(self)
        _initialize(process)
        # Record thought #1 first so branch_from_thought=1 is valid
        _think(process, 2, thought_number=1, total_thoughts=2, next_thought_needed=True)
        response = _think(process, 3, thought_number=2, total_thoughts=2,
                          next_thought_needed=False, branch_from_thought=1, branch_id="bad branch!")
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual("failed", content["status"])
        self.assertIn("branch_id", content["error"])

    def test_branch_id_exceeding_max_length_returns_error(self) -> None:
        process = _start_server(self)
        _initialize(process)
        _think(process, 2, thought_number=1, total_thoughts=2, next_thought_needed=True)
        long_id = "a" * 65
        response = _think(process, 3, thought_number=2, total_thoughts=2,
                          next_thought_needed=False, branch_from_thought=1, branch_id=long_id)
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual("failed", content["status"])
        self.assertIn("branch_id", content["error"])

    def test_valid_branch_appears_in_branches_list(self) -> None:
        process = _start_server(self)
        _initialize(process)
        _think(process, 2, thought_number=1, total_thoughts=3, next_thought_needed=True)
        response = _think(process, 3, thought_number=2, total_thoughts=3, next_thought_needed=True,
                          branch_from_thought=1, branch_id="alt-path")
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual("ok", content.get("status", "ok"))
        self.assertIn("alt-path", content["branches"])

    def test_reset_clears_history_and_branches(self) -> None:
        process = _start_server(self)
        _initialize(process)
        _think(process, 2, thought_number=1, total_thoughts=2, next_thought_needed=True)
        _think(process, 3, thought_number=2, total_thoughts=2, next_thought_needed=True,
               branch_from_thought=1, branch_id="some-branch")
        # Reset
        reset_response = _call_tool(process, message_id=4, name="reset_thinking_session", arguments={})
        reset_content = json.loads(reset_response["result"]["content"][0]["text"])
        self.assertEqual("ok", reset_content["status"])
        # After reset, revises_thought=1 should fail (thought #1 is gone)
        response = _think(process, 5, thought_number=2, total_thoughts=2,
                          next_thought_needed=False, is_revision=True, revises_thought=1)
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual("failed", content["status"])

    def test_total_thoughts_auto_adjusted_to_thought_number(self) -> None:
        """effective_total = max(total_thoughts, thought_number) — caller's dict not mutated."""
        process = _start_server(self)
        _initialize(process)
        # thought_number=5 > total_thoughts=3 → effective_total should be 5
        response = _think(process, 2, thought_number=5, total_thoughts=3, next_thought_needed=False)
        content = json.loads(response["result"]["content"][0]["text"])
        self.assertNotIn("error", content)
        self.assertEqual(5, content["total_thoughts"])


if __name__ == "__main__":
    unittest.main()
