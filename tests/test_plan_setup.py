from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class PlanSetupTests(XanadTestBase):
    def test_interview_emits_profile_and_pack_questions(self) -> None:
        result = self.run_command("interview", "--json", "--mode", "setup")

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("interview", payload["command"])
        self.assertEqual("setup", payload["mode"])
        question_ids = [question["id"] for question in payload["result"]["questions"]]
        self.assertIn("profile.selected", question_ids)
        self.assertIn("packs.selected", question_ids)
        self.assertIn("ownership.agents", question_ids)
        self.assertIn("ownership.skills", question_ids)
        self.assertIn("mcp.enabled", question_ids)
        mcp_question = next(question for question in payload["result"]["questions"] if question["id"] == "mcp.enabled")
        self.assertTrue(mcp_question["default"])
        self.assertTrue(mcp_question["recommended"])
        self.assertTrue(payload["result"]["discoveryMetadata"]["profileRegistry"]["loaded"])

    def test_plan_setup_from_empty_workspace_emits_summary(self) -> None:
        result = self.run_command("plan", "setup", "--json")

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("plan", payload["command"])
        self.assertEqual("setup", payload["mode"])
        self.assertEqual("approval-required", payload["status"])
        self.assertTrue(payload["result"]["approvalRequired"])
        self.assertTrue(payload["result"]["backupRequired"])
        self.assertEqual(6, payload["result"]["writes"]["add"])
        self.assertEqual(0, payload["result"]["writes"]["replace"])
        self.assertEqual(0, payload["result"]["writes"]["merge"])
        self.assertEqual("balanced", payload["result"]["profile"])
        self.assertEqual([], payload["result"]["packs"])
        self.assertTrue(payload["result"]["questionsResolved"])
        self.assertEqual(
            ".github/xanad-assistant-lock.json",
            payload["result"]["plannedLockfile"]["path"],
        )
        self.assertEqual(
            ".xanad-assistant/backups/<apply-timestamp>",
            payload["result"]["plannedLockfile"]["contents"]["lastBackup"]["path"],
        )
        self.assertEqual(
            [
                ".github/agents/commit.agent.md",
                ".github/agents/explore.agent.md",
                ".github/agents/lifecycle-planning.agent.md",
                ".github/agents/review.agent.md",
                ".github/skills/lean-output/SKILL.md",
                ".github/skills/lifecycle-audit/SKILL.md",
            ],
            payload["result"]["plannedLockfile"]["contents"]["skippedManagedFiles"],
        )
        self.assertEqual(
            {
                "required": True,
                "root": ".xanad-assistant/backups/<apply-timestamp>",
                "targets": [],
                "archiveRoot": ".xanad-assistant/archive",
                "archiveTargets": [],
            },
            payload["result"]["backupPlan"],
        )
        self.assertEqual(
            [
                {
                    "token": "{{WORKSPACE_NAME}}",
                    "value": Path(payload["workspace"]).name,
                    "required": False,
                    "targets": [".github/prompts/setup.md"],
                },
                {
                    "token": "{{XANAD_PROFILE}}",
                    "value": "balanced",
                    "required": False,
                    "targets": [".github/prompts/setup.md"],
                },
            ],
            payload["result"]["tokenSubstitutions"],
        )
        self.assertEqual(
            {
                "instructions": "local",
                "prompts": "local",
                "agents": "plugin-backed-copilot-format",
                "skills": "plugin-backed-copilot-format",
                "hooks": "local",
                "mcp": "local",
            },
            payload["result"]["ownershipBySurface"],
        )
        self.assertEqual(6, len(payload["result"]["skippedActions"]))
        self.assertEqual({}, payload["result"]["conflictSummary"])

        prompt_action = next(action for action in payload["result"]["actions"] if action["target"] == ".github/prompts/setup.md")
        self.assertEqual("token-replace", prompt_action["strategy"])
        self.assertEqual(
            {
                "{{WORKSPACE_NAME}}": Path(payload["workspace"]).name,
                "{{XANAD_PROFILE}}": "balanced",
            },
            prompt_action["tokenValues"],
        )

    def test_plan_setup_is_stable_when_rerun_against_unchanged_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            first = self.run_command_in_workspace(workspace, "plan", "setup", "--json")
            second = self.run_command_in_workspace(workspace, "plan", "setup", "--json")

        self.assertEqual(0, first.returncode)
        self.assertEqual(0, second.returncode)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))

    def test_plan_setup_classifies_replace_and_merge_for_stale_targets(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            instructions = workspace / ".github" / "copilot-instructions.md"
            instructions.parent.mkdir(parents=True, exist_ok=True)
            instructions.write_text("modified\n", encoding="utf-8")

            prompt = workspace / ".github" / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

        result = self.run_command("plan", "setup", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("approval-required", payload["status"])
        self.assertEqual(4, payload["result"]["writes"]["add"])
        self.assertEqual(1, payload["result"]["writes"]["replace"])
        self.assertEqual(1, payload["result"]["writes"]["merge"])
        actions_by_target = {action["target"]: action["action"] for action in payload["result"]["actions"]}
        self.assertEqual("merge", actions_by_target[".github/copilot-instructions.md"])
        self.assertEqual("replace", actions_by_target[".github/prompts/setup.md"])
        self.assertEqual(1, payload["result"]["conflictSummary"]["managed-drift"])
        self.assertEqual("managed_drift", payload["warnings"][0]["code"])

    def test_plan_setup_classifies_unmanaged_lookalikes(self) -> None:
        def workspace_setup(workspace: Path, repo_root: Path) -> None:
            managed_prompt = workspace / ".github" / "prompts" / "setup.md"
            managed_prompt.parent.mkdir(parents=True, exist_ok=True)
            managed_prompt.write_text(self.render_setup_prompt(repo_root, workspace), encoding="utf-8")

            unmanaged = workspace / ".github" / "prompts" / "custom.md"
            unmanaged.write_text("custom\n", encoding="utf-8")

        result = self.run_command("plan", "setup", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual(1, payload["result"]["conflictSummary"]["unmanaged-lookalike"])
        self.assertTrue(any(warning["code"] == "unmanaged_lookalike" for warning in payload["warnings"]))

    def test_plan_setup_uses_answer_file_for_profile_and_packs(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            handle.write(
                json.dumps(
                    {
                        "profile.selected": "lean",
                        "packs.selected": ["review", "research"],
                    }
                )
            )
            answers_path = handle.name

        try:
            result = self.run_command("plan", "setup", "--json", "--answers", answers_path)
        finally:
            Path(answers_path).unlink(missing_ok=True)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("lean", payload["result"]["profile"])
        self.assertEqual(["review", "research"], payload["result"]["packs"])
        self.assertEqual("lean", payload["result"]["resolvedAnswers"]["profile.selected"])
        prompt_action = next(action for action in payload["result"]["actions"] if action["target"] == ".github/prompts/setup.md")
        self.assertEqual("lean", prompt_action["tokenValues"]["{{XANAD_PROFILE}}"])

    def test_plan_setup_skips_plugin_backed_agents_and_enables_hook_mcp_atomically(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            handle.write(json.dumps({"mcp.enabled": True}))
            answers_path = handle.name

        try:
            result = self.run_command("plan", "setup", "--json", "--answers", answers_path)
        finally:
            Path(answers_path).unlink(missing_ok=True)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual(6, payload["result"]["writes"]["add"])
        self.assertEqual(True, payload["result"]["resolvedAnswers"]["mcp.enabled"])
        self.assertEqual(True, payload["result"]["resolvedAnswers"]["hooks.enabled"])

        action_targets = {action["target"] for action in payload["result"]["actions"]}
        self.assertIn(".github/hooks/scripts/xanad-workspace-mcp.py", action_targets)
        self.assertIn(".vscode/mcp.json", action_targets)

        skipped = {entry["target"]: entry["reason"] for entry in payload["result"]["skippedActions"]}
        self.assertEqual("plugin-backed-ownership", skipped[".github/agents/lifecycle-planning.agent.md"])
        self.assertEqual("plugin-backed-ownership", skipped[".github/skills/lifecycle-audit/SKILL.md"])


if __name__ == "__main__":
    unittest.main()
