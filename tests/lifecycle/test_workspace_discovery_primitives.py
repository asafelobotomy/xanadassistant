from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad import _prescan
from scripts.lifecycle._xanad import _workspace_scan


class WorkspaceScanTests(unittest.TestCase):
    def test_detects_python_workspace_and_makefile_test_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
            (workspace / "requirements.txt").write_text("coverage\n", encoding="utf-8")
            (workspace / "Makefile").write_text("test:\n\tpython3 -m unittest\n", encoding="utf-8")

            result = _workspace_scan.scan_workspace_stack(workspace)

        self.assertEqual(
            result,
            {
                "{{PRIMARY_LANGUAGE}}": "Python",
                "{{PACKAGE_MANAGER}}": "pip",
                "{{TEST_COMMAND}}": "make test",
            },
        )

    def test_detects_javascript_workspace_and_ignores_placeholder_test_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "package.json").write_text(
                json.dumps({"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}),
                encoding="utf-8",
            )
            (workspace / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")

            result = _workspace_scan.scan_workspace_stack(workspace)

        self.assertEqual(
            result,
            {
                "{{PRIMARY_LANGUAGE}}": "JavaScript",
                "{{PACKAGE_MANAGER}}": "pnpm",
            },
        )

    def test_prefers_python_and_pytest_for_polyglot_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "package.json").write_text(json.dumps({"scripts": {"test": "npm test"}}), encoding="utf-8")
            (workspace / "tsconfig.json").write_text("{}", encoding="utf-8")
            (workspace / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")

            result = _workspace_scan.scan_workspace_stack(workspace)

        self.assertEqual(result["{{PRIMARY_LANGUAGE}}"], "Python")
        self.assertEqual(result["{{TEST_COMMAND}}"], "pytest")

    def test_detects_go_and_cargo_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            go_workspace = Path(tmpdir) / "go"
            cargo_workspace = Path(tmpdir) / "cargo"
            go_workspace.mkdir()
            cargo_workspace.mkdir()
            (go_workspace / "go.mod").write_text("module example.com/demo\n", encoding="utf-8")
            (cargo_workspace / "Cargo.toml").write_text("[package]\nname='demo'\n", encoding="utf-8")

            go_result = _workspace_scan.scan_workspace_stack(go_workspace)
            cargo_result = _workspace_scan.scan_workspace_stack(cargo_workspace)

        self.assertEqual(go_result["{{PRIMARY_LANGUAGE}}"], "Go")
        self.assertEqual(go_result["{{PACKAGE_MANAGER}}"], "go modules")
        self.assertEqual(go_result["{{TEST_COMMAND}}"], "go test ./...")
        self.assertEqual(cargo_result["{{PRIMARY_LANGUAGE}}"], "Rust")
        self.assertEqual(cargo_result["{{PACKAGE_MANAGER}}"], "Cargo")
        self.assertEqual(cargo_result["{{TEST_COMMAND}}"], "cargo test")


class PrescanTests(unittest.TestCase):
    def test_scan_existing_copilot_files_reports_collisions_and_unmanaged_files(self) -> None:
        manifest = {
            "managedFiles": [
                {
                    "id": "agents.cleaner",
                    "target": ".github/agents/cleaner.agent.md",
                    "surface": "agents",
                    "strategy": "replace",
                },
                {
                    "id": "instructions.main",
                    "target": ".github/instructions/main.instructions.md",
                    "surface": "instructions",
                    "strategy": "preserve-marked-markdown-blocks",
                },
                {
                    "id": "hook.script",
                    "target": ".github/mcp/scripts/gitMcp.py",
                    "surface": "hooks",
                    "strategy": "copy-if-missing",
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / ".github" / "agents").mkdir(parents=True)
            (workspace / ".github" / "instructions").mkdir(parents=True)
            (workspace / ".github" / "mcp" / "scripts").mkdir(parents=True)
            (workspace / ".github" / "agents" / "cleaner.agent.md").write_text("x", encoding="utf-8")
            (workspace / ".github" / "instructions" / "main.instructions.md").write_text("x", encoding="utf-8")
            (workspace / ".github" / "mcp" / "scripts" / "gitMcp.py").write_text("x", encoding="utf-8")
            (workspace / ".github" / "mcp" / "scripts" / "custom.py").write_text("x", encoding="utf-8")

            result = _prescan.scan_existing_copilot_files(workspace, manifest)

        self.assertEqual([entry["type"] for entry in result], ["collision", "collision", "unmanaged"])
        self.assertEqual(result[0]["availableDecisions"], ["keep", "replace"])
        self.assertEqual(result[1]["availableDecisions"], ["keep", "replace", "merge"])
        self.assertEqual(result[1]["mergeStrategy"], "preserve-marked-markdown-blocks")
        self.assertEqual(result[2]["path"], ".github/mcp/scripts/custom.py")

    def test_scan_existing_copilot_files_covers_manifest_none_excludes_and_vscode_surface(self) -> None:
        self.assertEqual(_prescan.scan_existing_copilot_files(Path("."), None), [])

        manifest = {
            "managedFiles": [
                {
                    "id": "mcp.config",
                    "target": ".vscode/mcp.json",
                    "surface": "mcp",
                    "strategy": "merge-json-object",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / ".vscode").mkdir()
            (workspace / ".github" / "prompts").mkdir(parents=True)
            (workspace / ".vscode" / "mcp.json").write_text("{}", encoding="utf-8")
            (workspace / ".vscode" / ".complete").write_text("ok\n", encoding="utf-8")
            (workspace / ".github" / "prompts" / "copilot-version.md").write_text("ignore\n", encoding="utf-8")

            result = _prescan.scan_existing_copilot_files(workspace, manifest)

        self.assertEqual(result, [{
            "path": ".vscode/mcp.json",
            "type": "collision",
            "conflictsWith": "mcp.config",
            "surface": "mcp",
            "mergeSupported": True,
            "mergeStrategy": "merge-json-object",
            "availableDecisions": ["keep", "replace", "merge"],
        }])

    def test_scan_consumer_kept_updates_only_returns_changed_kept_targets(self) -> None:
        manifest = {
            "managedFiles": [
                {
                    "id": "instructions.main",
                    "target": ".github/instructions/main.instructions.md",
                    "surface": "instructions",
                    "strategy": "merge-json-object",
                    "hash": "sha256:new",
                },
                {
                    "id": "prompt.main",
                    "target": ".github/prompts/main.prompt.md",
                    "surface": "prompts",
                    "strategy": "replace",
                    "hash": "sha256:same",
                },
            ]
        }
        lockfile_state = {
            "consumerResolutions": {
                ".github/instructions/main.instructions.md": "keep",
                ".github/prompts/main.prompt.md": "keep",
                ".github/agents/unused.agent.md": "replace",
            },
            "files": [
                {"target": ".github/instructions/main.instructions.md", "sourceHash": "sha256:old"},
                {"target": ".github/prompts/main.prompt.md", "sourceHash": "sha256:same"},
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _prescan.scan_consumer_kept_updates(Path(tmpdir), manifest, lockfile_state)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["path"], ".github/instructions/main.instructions.md")
        self.assertEqual(result[0]["availableDecisions"], ["keep", "update"])
        self.assertTrue(result[0]["mergeSupported"])

    def test_scan_consumer_kept_updates_covers_empty_and_silent_ignore_paths(self) -> None:
        manifest = {
            "managedFiles": [
                {
                    "id": "instructions.main",
                    "target": ".github/instructions/main.instructions.md",
                    "surface": "instructions",
                    "strategy": "replace",
                    "hash": "sha256:same",
                }
            ]
        }

        self.assertEqual(_prescan.scan_consumer_kept_updates(Path("."), None, {}), [])
        self.assertEqual(_prescan.scan_consumer_kept_updates(Path("."), manifest, {"consumerResolutions": {}}), [])

        result = _prescan.scan_consumer_kept_updates(
            Path("."),
            manifest,
            {
                "consumerResolutions": {
                    ".github/instructions/main.instructions.md": "keep",
                    ".github/prompts/removed.prompt.md": "keep",
                    ".github/instructions/ignored.instructions.md": "replace",
                },
                "files": [{"target": ".github/instructions/main.instructions.md", "sourceHash": "sha256:same"}],
            },
        )

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()