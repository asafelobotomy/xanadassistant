from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class InspectCheckTests(XanadTestBase):
    def test_inspect_emits_json_summary(self) -> None:
        result = self.run_command("inspect", "--json")

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("inspect", payload["command"])
        self.assertEqual("package-root", payload["source"]["kind"])
        self.assertEqual("ok", payload["status"])
        self.assertTrue(payload["result"]["contracts"]["policy"]["loaded"])
        self.assertTrue(payload["result"]["contracts"]["manifestSchema"]["loaded"])
        self.assertGreater(payload["result"]["manifestSummary"]["declared"], 0)

    def test_inspect_emits_json_lines_and_agent_progress(self) -> None:
        result = self.run_command("inspect", "--json-lines", "--ui", "agent")

        self.assertEqual(0, result.returncode)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(["phase", "inspect-summary", "receipt"], [event["type"] for event in events])
        self.assertIn("Preflight", result.stderr)
        self.assertIn("Manifest entries", result.stderr)

    def test_check_reports_missing_targets_in_empty_workspace(self) -> None:
        result = self.run_command("check", "--json")

        self.assertEqual(7, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("check", payload["command"])
        self.assertEqual("drift", payload["status"])
        self.assertGreater(payload["result"]["summary"]["missing"], 0)
        self.assertEqual(10, payload["result"]["summary"]["skipped"])
        self.assertEqual(0, payload["result"]["summary"]["unmanaged"])

    def test_inspect_does_not_create_missing_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "missing-workspace"

            result = self.run_command_in_workspace(workspace, "inspect", "--json")

            self.assertEqual(0, result.returncode)
            self.assertFalse(workspace.exists())
            payload = json.loads(result.stdout)
            self.assertEqual(str(workspace.resolve()), payload["workspace"])

    def test_check_does_not_double_count_skipped_targets_from_lockfile(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "xanadAssistant-lock.json").write_text(
                json.dumps(
                    self.make_minimal_lockfile(
                        skippedManagedFiles=[".github/agents/commit.agent.md"],
                    ),
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("check", "--json", workspace_setup=workspace_setup)

        self.assertEqual(7, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual(10, payload["result"]["summary"]["skipped"])
        skipped_entries = [
            entry for entry in payload["result"]["entries"]
            if entry["target"] == ".github/agents/commit.agent.md"
        ]
        self.assertEqual(1, len(skipped_entries))

    def test_inspect_rejects_conflicting_json_output_flags(self) -> None:
        result = self.run_command("inspect", "--json", "--json-lines")

        self.assertEqual(2, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("error", payload["status"])
        self.assertEqual("invalid_invocation", payload["errors"][0]["code"])

    def test_check_detects_clean_and_unmanaged_targets(self) -> None:
        def workspace_setup(workspace: Path, repo_root: Path) -> None:
            target_one = workspace / ".github" / "copilot-instructions.md"
            target_one.parent.mkdir(parents=True, exist_ok=True)
            target_one.write_text(self.render_copilot_instructions(repo_root, workspace), encoding="utf-8")

            target_two = workspace / ".github" / "prompts" / "setup.md"
            target_two.parent.mkdir(parents=True, exist_ok=True)
            target_two.write_text(self.render_setup_prompt(repo_root, workspace), encoding="utf-8")

            unmanaged = workspace / ".github" / "prompts" / "custom.md"
            unmanaged.write_text("custom\n", encoding="utf-8")

        result = self.run_command("check", "--json", workspace_setup=workspace_setup)

        self.assertEqual(7, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual(2, payload["result"]["summary"]["clean"])
        self.assertEqual(1, payload["result"]["summary"]["unmanaged"])
        self.assertIn(".github/prompts/custom.md", payload["result"]["unmanagedFiles"])

    def test_check_ignores_repo_owned_files_in_root_container_dirs(self) -> None:
        def workspace_setup(workspace: Path, repo_root: Path) -> None:
            target_one = workspace / ".github" / "copilot-instructions.md"
            target_one.parent.mkdir(parents=True, exist_ok=True)
            target_one.write_text(self.render_copilot_instructions(repo_root, workspace), encoding="utf-8")

            prompt = workspace / ".github" / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text(self.render_setup_prompt(repo_root, workspace), encoding="utf-8")

            vscode_dir = workspace / ".vscode"
            vscode_dir.mkdir(parents=True, exist_ok=True)
            (vscode_dir / "mcp.json").write_text(
                json.dumps(
                    json.loads((repo_root / "template" / "vscode" / "mcp.json").read_text(encoding="utf-8")),
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            workflows = workspace / ".github" / "workflows"
            workflows.mkdir(parents=True, exist_ok=True)
            (workflows / "validate.yml").write_text("name: Validate\n", encoding="utf-8")

            starter_kit = workspace / ".github" / "starter-kits" / "cpp"
            starter_kit.mkdir(parents=True, exist_ok=True)
            (starter_kit / "plugin.json").write_text("{}\n", encoding="utf-8")

            (vscode_dir / "settings.json").write_text("{}\n", encoding="utf-8")
            (vscode_dir / "extensions.json").write_text("{}\n", encoding="utf-8")

        result = self.run_command("check", "--json", workspace_setup=workspace_setup)

        self.assertEqual(7, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual(0, payload["result"]["summary"]["unmanaged"])
        self.assertNotIn(".github/workflows/validate.yml", payload["result"]["unmanagedFiles"])
        self.assertNotIn(".github/starter-kits/cpp/plugin.json", payload["result"]["unmanagedFiles"])
        self.assertNotIn(".vscode/settings.json", payload["result"]["unmanagedFiles"])
        self.assertNotIn(".vscode/extensions.json", payload["result"]["unmanagedFiles"])

    def test_check_reports_clean_when_all_targets_match(self) -> None:
        def workspace_setup(workspace: Path, repo_root: Path) -> None:
            target_one = workspace / ".github" / "copilot-instructions.md"
            target_one.parent.mkdir(parents=True, exist_ok=True)
            target_one.write_text(self.render_copilot_instructions(repo_root, workspace), encoding="utf-8")

            target_two = workspace / ".github" / "prompts" / "setup.md"
            target_two.parent.mkdir(parents=True, exist_ok=True)
            target_two.write_text(self.render_setup_prompt(repo_root, workspace), encoding="utf-8")

            instructions_dir = workspace / ".github" / "instructions"
            instructions_dir.mkdir(parents=True, exist_ok=True)
            (instructions_dir / "tests.instructions.md").write_text(
                self.render_instructions_file(repo_root / "template" / "instructions" / "tests.instructions.md"),
                encoding="utf-8",
            )
            (instructions_dir / "scripts.instructions.md").write_text(
                self.render_instructions_file(repo_root / "template" / "instructions" / "scripts.instructions.md"),
                encoding="utf-8",
            )

            hooks_dir = workspace / ".github" / "hooks" / "scripts"
            hooks_dir.mkdir(parents=True, exist_ok=True)
            (hooks_dir / "xanadWorkspaceMcp.py").write_text(
                (repo_root / "hooks" / "scripts" / "xanadWorkspaceMcp.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (hooks_dir / "mcpSequentialThinkingServer.py").write_text(
                (repo_root / "hooks" / "scripts" / "mcpSequentialThinkingServer.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (hooks_dir / "_xanad_mcp_source.py").write_text(
                (repo_root / "hooks" / "scripts" / "_xanad_mcp_source.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (hooks_dir / "gitMcp.py").write_text(
                (repo_root / "hooks" / "scripts" / "gitMcp.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (hooks_dir / "webMcp.py").write_text(
                (repo_root / "hooks" / "scripts" / "webMcp.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (hooks_dir / "timeMcp.py").write_text(
                (repo_root / "hooks" / "scripts" / "timeMcp.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (hooks_dir / "securityMcp.py").write_text(
                (repo_root / "hooks" / "scripts" / "securityMcp.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (hooks_dir / "githubMcp.py").write_text(
                (repo_root / "hooks" / "scripts" / "githubMcp.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (hooks_dir / "sqliteMcp.py").write_text(
                (repo_root / "hooks" / "scripts" / "sqliteMcp.py").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            vscode_dir = workspace / ".vscode"
            vscode_dir.mkdir(parents=True, exist_ok=True)
            (vscode_dir / "mcp.json").write_text(
                json.dumps(
                    json.loads((repo_root / "template" / "vscode" / "mcp.json").read_text(encoding="utf-8")),
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("check", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("clean", payload["status"])
        self.assertEqual(0, payload["result"]["summary"]["missing"])
        self.assertEqual(10, payload["result"]["summary"]["skipped"])
        self.assertEqual(0, payload["result"]["summary"]["stale"])

    def test_check_reports_stale_when_target_content_differs(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            target_one = workspace / ".github" / "copilot-instructions.md"
            target_one.parent.mkdir(parents=True, exist_ok=True)
            target_one.write_text("modified\n", encoding="utf-8")

            target_two = workspace / ".github" / "prompts" / "setup.md"
            target_two.parent.mkdir(parents=True, exist_ok=True)
            target_two.write_text("modified\n", encoding="utf-8")

        result = self.run_command("check", "--json", workspace_setup=workspace_setup)

        self.assertEqual(7, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual(2, payload["result"]["summary"]["stale"])

    def test_inspect_parses_legacy_version_and_lockfile_state(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-version.md").write_text("Version: 0.9.0\n", encoding="utf-8")
            (github_dir / "xanadAssistant-lock.json").write_text(
                json.dumps(
                    self.make_minimal_lockfile(
                        selectedPacks=["review"],
                        ownershipBySurface={
                            "agents": "plugin-backed-copilot-format",
                            "prompts": "local",
                        },
                        skippedManagedFiles=[".github/prompts/setup.md"],
                        unknownValues={"legacy": True},
                    ),
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("inspect", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("installed", payload["result"]["installState"])
        self.assertFalse(payload["result"]["legacyVersionState"]["malformed"])
        self.assertEqual("0.9.0", payload["result"]["legacyVersionState"]["data"]["version"])
        self.assertFalse(payload["result"]["lockfileState"]["malformed"])
        self.assertEqual(["review"], payload["result"]["lockfileState"]["selectedPacks"])
        self.assertEqual("balanced", payload["result"]["lockfileState"]["profile"])
        self.assertTrue(payload["result"]["discoveryMetadata"]["packRegistry"]["loaded"])
        self.assertTrue(payload["result"]["discoveryMetadata"]["profileRegistry"]["loaded"])
        self.assertTrue(payload["result"]["discoveryMetadata"]["catalog"]["loaded"])

    def test_check_marks_malformed_legacy_and_unknown_lockfile_values(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-version.md").write_text("broken legacy metadata\n", encoding="utf-8")
            (github_dir / "xanadAssistant-lock.json").write_text(
                json.dumps(
                    self.make_minimal_lockfile(
                        files=[
                            {
                                "id": "prompt.setup",
                                "target": ".github/prompts/setup.md",
                                "sourceHash": "sha256:test",
                                "installedHash": "unknown",
                                "status": "unknown",
                            }
                        ],
                        unknownValues={"legacyOwnership": True},
                    ),
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("check", "--json", workspace_setup=workspace_setup)

        self.assertEqual(7, result.returncode)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["result"]["summary"]["malformed"], 1)
        self.assertGreaterEqual(payload["result"]["summary"]["unknown"], 2)


if __name__ == "__main__":
    unittest.main()
