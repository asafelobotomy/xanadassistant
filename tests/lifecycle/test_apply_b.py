from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class ApplyTests(XanadTestBase):
    def test_repair_applies_malformed_legacy_install_and_returns_clean_state(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-version.md").write_text("broken legacy metadata\n", encoding="utf-8")

            instructions = github_dir / "copilot-instructions.md"
            instructions.write_text("modified\n", encoding="utf-8")

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

        result = self.run_command("repair", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("repair", payload["command"])
        self.assertEqual("repair", payload["mode"])
        self.assertEqual("ok", payload["status"])
        self.assertEqual(1, payload["result"]["writes"]["replaced"])
        self.assertEqual(1, payload["result"]["writes"]["merged"])
        self.assertEqual("passed", payload["result"]["validation"]["status"])

    def test_factory_restore_applies_customized_workspace_and_returns_clean_state(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-instructions.md").write_text("modified\n", encoding="utf-8")

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

            unmanaged = github_dir / "prompts" / "custom.md"
            unmanaged.write_text("custom\n", encoding="utf-8")

            (github_dir / "xanadAssistant-lock.json").write_text(
                json.dumps(
                    self.make_minimal_lockfile(
                        ownershipBySurface={
                            "instructions": "local",
                            "prompts": "local",
                        },
                    ),
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("factory-restore", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("factory-restore", payload["command"])
        self.assertEqual("factory-restore", payload["mode"])
        self.assertEqual("ok", payload["status"])
        self.assertEqual(1, payload["result"]["writes"]["replaced"])
        self.assertEqual(1, payload["result"]["writes"]["merged"])
        self.assertEqual("passed", payload["result"]["validation"]["status"])

    def test_plan_setup_emits_json_lines_and_agent_progress(self) -> None:
        result = self.run_command("plan", "setup", "--json-lines", "--ui", "agent")

        self.assertEqual(0, result.returncode)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual("phase", events[0]["type"])
        self.assertEqual("Preflight", events[0]["phase"])
        self.assertEqual("inspect-summary", events[1]["type"])
        self.assertEqual("question", events[2]["type"])
        self.assertEqual("phase", events[-3]["type"])
        self.assertEqual("Plan", events[-3]["phase"])
        self.assertEqual("plan-summary", events[-2]["type"])
        self.assertIn("conflicts", events[-2])
        self.assertEqual("receipt", events[-1]["type"])
        self.assertIn("Plan", result.stderr)
        self.assertIn("Waiting on Copilot", result.stderr)

    def test_interview_emits_json_lines_and_agent_progress(self) -> None:
        result = self.run_command("interview", "--json-lines", "--ui", "agent", "--mode", "setup")

        self.assertEqual(0, result.returncode)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual("phase", events[0]["type"])
        self.assertEqual("Interview", events[0]["phase"])
        self.assertEqual("question", events[1]["type"])
        self.assertEqual("receipt", events[-1]["type"])
        self.assertIn("Interview", result.stderr)
        self.assertIn("Questions emitted", result.stderr)




if __name__ == "__main__":
    unittest.main()
