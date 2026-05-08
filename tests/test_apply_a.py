from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class ApplyTests(XanadTestBase):
    def test_apply_setup_writes_files_lockfile_and_report(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            report_out_path = workspace / "apply-report.json"
            repo_root = Path(__file__).resolve().parents[1]

            result = self.run_command_in_workspace(
                workspace,
                "apply",
                "--json",
                "--report-out",
                str(report_out_path),
            )

            self.assertEqual(0, result.returncode)
            payload = json.loads(result.stdout)
            written_report = json.loads(report_out_path.read_text(encoding="utf-8"))

            self.assertEqual("apply", payload["command"])
            self.assertEqual("setup", payload["mode"])
            self.assertEqual("ok", payload["status"])
            self.assertTrue(payload["result"]["backup"]["created"])
            self.assertEqual(6, payload["result"]["writes"]["added"])
            self.assertEqual(0, payload["result"]["writes"]["replaced"])
            self.assertTrue(payload["result"]["summary"]["written"])
            self.assertEqual(".github/copilot-version.md", payload["result"]["summary"]["path"])
            self.assertEqual("passed", payload["result"]["validation"]["status"])
            self.assertEqual(payload["command"], written_report["command"])
            self.assertTrue(payload["result"]["reportOut"].endswith("apply-report.json"))
            self.assertEqual(
                self.render_setup_prompt(repo_root, workspace),
                (workspace / ".github" / "prompts" / "setup.md").read_text(encoding="utf-8"),
            )
            self.assertTrue((workspace / ".github" / "copilot-instructions.md").exists())
            self.assertTrue((workspace / ".github" / "xanad-assistant-lock.json").exists())
            summary_text = (workspace / ".github" / "copilot-version.md").read_text(encoding="utf-8")
            self.assertIn("Version: 0.1.0", summary_text)
            self.assertIn("```json", summary_text)

            check_result = self.run_command_in_workspace(workspace, "check", "--json")
            self.assertEqual(0, check_result.returncode)
            check_payload = json.loads(check_result.stdout)
            self.assertEqual("clean", check_payload["status"])

    def test_apply_setup_emits_json_lines_and_agent_progress(self) -> None:
        result = self.run_command("apply", "--json-lines", "--ui", "agent")

        self.assertEqual(0, result.returncode)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual("phase", events[0]["type"])
        self.assertEqual("Apply", events[0]["phase"])
        self.assertEqual("apply-report", events[1]["type"])
        self.assertIn("summary", events[1])
        self.assertEqual("receipt", events[-1]["type"])
        self.assertIn("Apply", result.stderr)
        self.assertIn("Summary written", result.stderr)
        self.assertIn("Validate", result.stderr)

    def test_apply_setup_with_mcp_enabled_merges_existing_mcp_config(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            answers_path = workspace / "answers.json"
            answers_path.write_text(json.dumps({"mcp.enabled": True}) + "\n", encoding="utf-8")

            existing_mcp_path = workspace / ".vscode" / "mcp.json"
            existing_mcp_path.parent.mkdir(parents=True, exist_ok=True)
            existing_mcp_path.write_text(
                json.dumps(
                    {
                        "servers": {
                            "custom-server": {
                                "type": "stdio",
                                "command": "python3",
                                "args": ["custom.py"],
                            }
                        },
                        "workspaceSetting": True,
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            result = self.run_command_in_workspace(
                workspace,
                "apply",
                "--json",
                "--answers",
                str(answers_path),
            )

            self.assertEqual(0, result.returncode)
            payload = json.loads(result.stdout)
            self.assertEqual(5, payload["result"]["writes"]["added"])
            self.assertEqual(1, payload["result"]["writes"]["merged"])

            merged_mcp = json.loads(existing_mcp_path.read_text(encoding="utf-8"))
            self.assertTrue(merged_mcp["workspaceSetting"])
            self.assertIn("custom-server", merged_mcp["servers"])
            self.assertIn("xanad-workspace", merged_mcp["servers"])

            check_result = self.run_command_in_workspace(workspace, "check", "--json")
            self.assertEqual(0, check_result.returncode)
            self.assertEqual("clean", json.loads(check_result.stdout)["status"])

    def test_apply_setup_preserves_marked_instruction_blocks(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            repo_root = Path(__file__).resolve().parents[1]

            instructions_path = workspace / ".github" / "copilot-instructions.md"
            instructions_path.parent.mkdir(parents=True, exist_ok=True)
            instructions_path.write_text(
                "# Local Instructions\n\n"
                "<!-- user-added -->\n"
                "Keep this user note.\n"
                "<!-- /user-added -->\n\n"
                "## §10 - Project-Specific Overrides\n\n"
                "- Preserve this project override.\n",
                encoding="utf-8",
            )

            result = self.run_command_in_workspace(workspace, "apply", "--json")

            self.assertEqual(0, result.returncode)
            payload = json.loads(result.stdout)
            self.assertGreaterEqual(payload["result"]["writes"]["merged"], 1)

            installed_instructions = instructions_path.read_text(encoding="utf-8")
            self.assertIn("Lifecycle authority", installed_instructions)
            self.assertIn("<!-- user-added -->", installed_instructions)
            self.assertIn("Keep this user note.", installed_instructions)
            self.assertIn("## §10 - Project-Specific Overrides", installed_instructions)
            self.assertIn("Preserve this project override.", installed_instructions)

            check_result = self.run_command_in_workspace(workspace, "check", "--json")
            self.assertEqual(0, check_result.returncode)
            self.assertEqual("clean", json.loads(check_result.stdout)["status"])

    def test_update_applies_stale_install_and_returns_clean_state(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-instructions.md").write_text("modified\n", encoding="utf-8")

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

            (github_dir / "xanad-assistant-lock.json").write_text(
                json.dumps(
                    self.make_minimal_lockfile(
                        selectedPacks=["review"],
                        ownershipBySurface={
                            "instructions": "local",
                            "prompts": "local",
                        },
                    ),
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("update", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("update", payload["command"])
        self.assertEqual("update", payload["mode"])
        self.assertEqual("ok", payload["status"])
        self.assertEqual(1, payload["result"]["writes"]["replaced"])
        self.assertEqual(1, payload["result"]["writes"]["merged"])
        self.assertEqual("passed", payload["result"]["validation"]["status"])



if __name__ == "__main__":
    unittest.main()
