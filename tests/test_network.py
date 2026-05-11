"""Network integration tests for GitHub source resolution.

These tests verify GitHub release and ref resolution against live endpoints.
They are gated by the XANAD_NETWORK_TESTS environment variable and are skipped
unless that variable is set to a non-empty value.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "lifecycle" / "xanadAssistant.py"
NETWORK_TESTS = bool(os.getenv("XANAD_NETWORK_TESTS"))


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


def _run(command: str, *extra_args: str, workspace: Path) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT), command]
    if command == "plan" and extra_args and not extra_args[0].startswith("-"):
        cmd.append(extra_args[0])
        extra_args = extra_args[1:]
    cmd += ["--workspace", str(workspace), "--package-root", str(REPO_ROOT)]
    return subprocess.run(
        cmd + list(extra_args),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _apply_fresh(workspace: Path) -> subprocess.CompletedProcess[str]:
    return _run("apply", "--json", "--non-interactive", workspace=workspace)


def _normalise_lockfile(lockfile: dict) -> dict:
    """Strip timestamp and backup fields so two lockfiles can be compared structurally."""
    result = dict(lockfile)
    result.pop("timestamps", None)
    result.pop("lastBackup", None)
    result.get("package", {}).pop("version", None)
    result.get("package", {}).pop("packageRoot", None)
    return result


@unittest.skipUnless(NETWORK_TESTS, "Set XANAD_NETWORK_TESTS=1 to enable network integration tests")
class GitHubSourceResolutionNetworkTests(unittest.TestCase):
    """Integration tests for live GitHub release/ref resolution paths."""

    CACHE_ROOT = Path(tempfile.gettempdir()) / "xanad-test-network-cache"

    def setUp(self) -> None:
        self.CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    def start_mcp_server(self, workspace: Path) -> subprocess.Popen[bytes]:
        source_server = REPO_ROOT / "hooks" / "scripts" / "xanad-workspace-mcp.py"
        server_path = workspace / ".github" / "hooks" / "scripts" / "xanad-workspace-mcp.py"
        server_path.parent.mkdir(parents=True, exist_ok=True)
        server_path.write_text(source_server.read_text(encoding="utf-8"), encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, str(server_path)],
            cwd=workspace,
            env={**os.environ, "XANAD_PKG_CACHE": str(self.CACHE_ROOT)},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.addCleanup(self.stop_process, process)
        return process

    def stop_process(self, process: subprocess.Popen[bytes]) -> None:
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

    def test_resolve_github_ref_clones_main_branch(self) -> None:
        from scripts.lifecycle.xanadAssistant import resolve_github_ref

        pkg_root = resolve_github_ref("asafelobotomy", "xanadassistant", "main", self.CACHE_ROOT)
        self.assertTrue(pkg_root.exists(), "Cloned package root should exist")
        self.assertTrue(
            (pkg_root / "scripts" / "lifecycle" / "generate_manifest.py").exists(),
            "Cloned repo should contain generate_manifest.py",
        )

    def test_resolve_github_ref_result_is_cached(self) -> None:
        from scripts.lifecycle.xanadAssistant import resolve_github_ref

        pkg_root_1 = resolve_github_ref("asafelobotomy", "xanadassistant", "main", self.CACHE_ROOT)
        pkg_root_2 = resolve_github_ref("asafelobotomy", "xanadassistant", "main", self.CACHE_ROOT)
        self.assertEqual(pkg_root_1, pkg_root_2, "Repeated calls should return the same path")

    def test_resolve_github_ref_package_is_usable(self) -> None:
        from scripts.lifecycle.xanadAssistant import resolve_github_ref

        pkg_root = resolve_github_ref("asafelobotomy", "xanadassistant", "main", self.CACHE_ROOT)

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            cmd = [
                sys.executable, str(SCRIPT),
                "inspect",
                "--workspace", str(workspace),
                "--package-root", str(pkg_root),
                "--json",
            ]
            result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("inspect", payload["command"])
            self.assertEqual("ok", payload["status"])

    def test_local_and_github_ref_installs_converge(self) -> None:
        from scripts.lifecycle.xanadAssistant import resolve_github_ref

        with tempfile.TemporaryDirectory() as local_tmp:
            local_ws = Path(local_tmp)
            local_result = _apply_fresh(local_ws)
            self.assertEqual(0, local_result.returncode, local_result.stderr)
            local_lockfile = json.loads(
                (local_ws / ".github" / "xanadAssistant-lock.json").read_text(encoding="utf-8")
            )

        pkg_root = resolve_github_ref("asafelobotomy", "xanadassistant", "main", self.CACHE_ROOT)
        with tempfile.TemporaryDirectory() as remote_tmp:
            remote_ws = Path(remote_tmp)
            cmd = [
                sys.executable, str(SCRIPT),
                "apply",
                "--workspace", str(remote_ws),
                "--package-root", str(pkg_root),
                "--json", "--non-interactive",
            ]
            remote_result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(0, remote_result.returncode, remote_result.stderr)
            remote_lockfile = json.loads(
                (remote_ws / ".github" / "xanadAssistant-lock.json").read_text(encoding="utf-8")
            )

        local_norm = _normalise_lockfile(local_lockfile)
        remote_norm = _normalise_lockfile(remote_lockfile)

        self.assertEqual(
            local_norm.get("selectedPacks"),
            remote_norm.get("selectedPacks"),
        )
        self.assertEqual(
            local_norm.get("manifest", {}).get("hash"),
            remote_norm.get("manifest", {}).get("hash"),
            "Manifest hash must match between local and GitHub-ref installs",
        )

    def test_mcp_lifecycle_inspect_supports_github_ref_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            process = self.start_mcp_server(workspace)

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
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "lifecycle.inspect",
                        "arguments": {
                            "source": "github:asafelobotomy/xanadassistant",
                            "ref": "main",
                        },
                    },
                },
            )
            result = response["result"]["structuredContent"]
            self.assertEqual("ok", result["status"])
            self.assertEqual(0, result["exitCode"])
            self.assertEqual("inspect", result["payload"]["command"])
            self.assertEqual("ok", result["payload"]["status"])


if __name__ == "__main__":
    unittest.main()
