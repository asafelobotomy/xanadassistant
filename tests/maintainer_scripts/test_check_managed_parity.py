from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts import check_managed_parity


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _write_manifest(root: Path, managed_files: list[dict]) -> None:
    manifest = {
        "schemaVersion": "1",
        "packageVersion": "0.0.0",
        "managedFiles": managed_files,
    }
    manifest_dir = root / "template" / "setup"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "install-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


class ParityPassTests(unittest.TestCase):
    def test_passes_when_source_and_target_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            content = b"hello world\n"
            (root / "mcp").mkdir()
            (root / "mcp" / "server.py").write_bytes(content)
            github_mcp = root / ".github" / "mcp"
            github_mcp.mkdir(parents=True)
            (github_mcp / "server.py").write_bytes(content)
            _write_manifest(root, [
                {
                    "id": "mcp.server.py",
                    "source": "mcp/server.py",
                    "target": ".github/mcp/server.py",
                    "strategy": "replace-verbatim",
                    "tokens": [],
                }
            ])

            exit_code = check_managed_parity.run(root)

        self.assertEqual(exit_code, 0)

    def test_skips_entry_when_target_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "agents").mkdir()
            (root / "agents" / "foo.agent.md").write_bytes(b"agent content")
            _write_manifest(root, [
                {
                    "id": "agents.foo.agent.md",
                    "source": "agents/foo.agent.md",
                    "target": ".github/agents/foo.agent.md",
                    "strategy": "replace-verbatim",
                    "tokens": [],
                }
            ])

            exit_code = check_managed_parity.run(root)

        self.assertEqual(exit_code, 0)

    def test_passes_for_token_replaced_entry_when_rendered_target_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "agents").mkdir()
            (root / "agents" / "foo.agent.md").write_bytes(b"style: {{pack:style}}")
            github_agents = root / ".github" / "agents"
            github_agents.mkdir(parents=True)
            (github_agents / "foo.agent.md").write_bytes(b"style: inline")
            _write_manifest(root, [
                {
                    "id": "agents.foo.agent.md",
                    "source": "agents/foo.agent.md",
                    "target": ".github/agents/foo.agent.md",
                    "strategy": "token-replace",
                    "tokens": ["{{pack:style}}"],
                }
            ])

            with mock.patch("scripts.check_managed_parity._build_token_values", return_value={"{{pack:style}}": "inline"}):
                exit_code = check_managed_parity.run(root)

        self.assertEqual(exit_code, 0)

    def test_fails_for_token_replaced_entry_when_rendered_target_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "agents").mkdir()
            (root / "agents" / "foo.agent.md").write_bytes(b"style: {{pack:style}}")
            github_agents = root / ".github" / "agents"
            github_agents.mkdir(parents=True)
            (github_agents / "foo.agent.md").write_bytes(b"style: stale")
            _write_manifest(root, [
                {
                    "id": "agents.foo.agent.md",
                    "source": "agents/foo.agent.md",
                    "target": ".github/agents/foo.agent.md",
                    "strategy": "token-replace",
                    "tokens": ["{{pack:style}}"],
                }
            ])

            with mock.patch("scripts.check_managed_parity._build_token_values", return_value={"{{pack:style}}": "inline"}):
                exit_code = check_managed_parity.run(root)

        self.assertEqual(exit_code, 1)

    def test_fails_for_token_replaced_entry_when_tokens_remain_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "agents").mkdir()
            (root / "agents" / "foo.agent.md").write_bytes(b"style: {{pack:style}}")
            github_agents = root / ".github" / "agents"
            github_agents.mkdir(parents=True)
            (github_agents / "foo.agent.md").write_bytes(b"style: {{pack:style}}")
            _write_manifest(root, [
                {
                    "id": "agents.foo.agent.md",
                    "source": "agents/foo.agent.md",
                    "target": ".github/agents/foo.agent.md",
                    "strategy": "token-replace",
                    "tokens": ["{{pack:style}}"],
                }
            ])

            with mock.patch("scripts.check_managed_parity._build_token_values", return_value={}):
                exit_code = check_managed_parity.run(root)

        self.assertEqual(exit_code, 1)

    def test_skips_entry_with_merge_json_object_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "template" / "vscode").mkdir(parents=True)
            (root / "template" / "vscode" / "mcp.json").write_bytes(b'{"servers":{}}')
            vscode_dir = root / ".vscode"
            vscode_dir.mkdir()
            (vscode_dir / "mcp.json").write_bytes(b'{"servers":{"extra":{}}}')
            _write_manifest(root, [
                {
                    "id": "mcp-config.mcp.json",
                    "source": "template/vscode/mcp.json",
                    "target": ".vscode/mcp.json",
                    "strategy": "merge-json-object",
                    "tokens": [],
                }
            ])

            exit_code = check_managed_parity.run(root)

        self.assertEqual(exit_code, 0)

    def test_passes_with_empty_managed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_manifest(root, [])

            exit_code = check_managed_parity.run(root)

        self.assertEqual(exit_code, 0)


class ParityFailTests(unittest.TestCase):
    def test_fails_when_target_differs_from_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "mcp").mkdir()
            (root / "mcp" / "server.py").write_bytes(b"source content\n")
            github_mcp = root / ".github" / "mcp"
            github_mcp.mkdir(parents=True)
            (github_mcp / "server.py").write_bytes(b"stale installed content\n")
            _write_manifest(root, [
                {
                    "id": "mcp.server.py",
                    "source": "mcp/server.py",
                    "target": ".github/mcp/server.py",
                    "strategy": "replace-verbatim",
                    "tokens": [],
                }
            ])

            exit_code = check_managed_parity.run(root)

        self.assertEqual(exit_code, 1)

    def test_reports_all_mismatched_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "mcp").mkdir()
            (root / "mcp" / "a.py").write_bytes(b"source a")
            (root / "mcp" / "b.py").write_bytes(b"source b")
            github_mcp = root / ".github" / "mcp"
            github_mcp.mkdir(parents=True)
            (github_mcp / "a.py").write_bytes(b"stale a")
            (github_mcp / "b.py").write_bytes(b"stale b")
            _write_manifest(root, [
                {
                    "id": "mcp.a.py",
                    "source": "mcp/a.py",
                    "target": ".github/mcp/a.py",
                    "strategy": "replace-verbatim",
                    "tokens": [],
                },
                {
                    "id": "mcp.b.py",
                    "source": "mcp/b.py",
                    "target": ".github/mcp/b.py",
                    "strategy": "replace-verbatim",
                    "tokens": [],
                },
            ])

            exit_code = check_managed_parity.run(root)

        self.assertEqual(exit_code, 1)


class ParityErrorTests(unittest.TestCase):
    def test_returns_exit_2_when_manifest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            exit_code = check_managed_parity.run(root)

        self.assertEqual(exit_code, 2)

    def test_main_returns_exit_2_for_missing_package_root(self) -> None:
        exit_code = check_managed_parity.main(["--package-root", "/no/such/path"])

        self.assertEqual(exit_code, 2)

    def test_main_returns_exit_2_for_missing_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = check_managed_parity.main(["--package-root", tmpdir, "--workspace", "/no/such/path"])

        self.assertEqual(exit_code, 2)


class ParityWorkspaceTests(unittest.TestCase):
    def test_checks_targets_in_explicit_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as package_tmpdir, tempfile.TemporaryDirectory() as workspace_tmpdir:
            package_root = Path(package_tmpdir)
            workspace_root = Path(workspace_tmpdir)
            (package_root / "mcp").mkdir()
            (package_root / "mcp" / "server.py").write_bytes(b"source content\n")
            github_mcp = workspace_root / ".github" / "mcp"
            github_mcp.mkdir(parents=True)
            (github_mcp / "server.py").write_bytes(b"source content\n")
            _write_manifest(package_root, [
                {
                    "id": "mcp.server.py",
                    "source": "mcp/server.py",
                    "target": ".github/mcp/server.py",
                    "strategy": "replace-verbatim",
                    "tokens": [],
                }
            ])

            exit_code = check_managed_parity.run(package_root, workspace_root)

        self.assertEqual(exit_code, 0)


class ParityIntegrationTests(unittest.TestCase):
    def test_passes_against_real_repo(self) -> None:
        """The live repo must be in parity — all installed targets match source."""
        repo_root = Path(__file__).resolve().parents[2]

        exit_code = check_managed_parity.run(repo_root)

        self.assertEqual(exit_code, 0)
