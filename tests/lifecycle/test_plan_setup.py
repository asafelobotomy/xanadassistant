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
        self.assertIn("setup.depth", question_ids)
        self.assertIn("profile.selected", question_ids)
        self.assertIn("packs.selected", question_ids)
        self.assertIn("ownership.agents", question_ids)
        self.assertIn("ownership.skills", question_ids)
        self.assertIn("response.style", question_ids)
        self.assertIn("autonomy.level", question_ids)
        self.assertIn("agent.persona", question_ids)
        self.assertIn("testing.philosophy", question_ids)
        self.assertIn("mcp.enabled", question_ids)
        self.assertIn("mcp.servers", question_ids)
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
        self.assertFalse(payload["result"]["backupRequired"])  # pure-add: no files overwritten
        self.assertEqual(0, payload["result"]["writes"]["replace"])
        self.assertEqual(0, payload["result"]["writes"]["merge"])
        self.assertEqual("balanced", payload["result"]["profile"])
        self.assertEqual([], payload["result"]["packs"])
        self.assertTrue(payload["result"]["questionsResolved"])
        self.assertEqual(
            ".github/xanadAssistant-lock.json",
            payload["result"]["plannedLockfile"]["path"],
        )
        self.assertNotIn(  # no lastBackup for pure-add fresh install
            "lastBackup", payload["result"]["plannedLockfile"]["contents"]
        )
        self.assertEqual(
            [
                ".github/agents/commit.agent.md",
                ".github/agents/debugger.agent.md",
                ".github/agents/docs.agent.md",
                ".github/agents/explore.agent.md",
                ".github/agents/planner.agent.md",
                ".github/agents/researcher.agent.md",
                ".github/agents/review.agent.md",
                ".github/agents/triage.agent.md",
                ".github/agents/xanadLifecycle.agent.md",
                ".github/hooks/scripts/devopsEnvCheck.py",
                ".github/hooks/scripts/docsLinkCheck.py",
                ".github/hooks/scripts/leanContextBudget.py",
                ".github/hooks/scripts/leanTestReporter.py",
                ".github/hooks/scripts/mlopsModelCheck.py",
                ".github/hooks/scripts/ossGitLog.py",
                ".github/hooks/scripts/ossLicenseCheck.py",
                ".github/hooks/scripts/secureOsv.py",
                ".github/hooks/scripts/shapeupScopeCheck.py",
                ".github/hooks/scripts/tddTestRunner.py",
                ".github/prompts/devops-incident.prompt.md",
                ".github/prompts/devops-pipeline.prompt.md",
                ".github/prompts/docs-draft.prompt.md",
                ".github/prompts/docs-review.prompt.md",
                ".github/prompts/lean-plan.prompt.md",
                ".github/prompts/lean-review.prompt.md",
                ".github/prompts/lean-status.prompt.md",
                ".github/prompts/mlops-drift.prompt.md",
                ".github/prompts/mlops-experiment.prompt.md",
                ".github/prompts/oss-changelog.prompt.md",
                ".github/prompts/oss-pr.prompt.md",
                ".github/prompts/security-review.prompt.md",
                ".github/prompts/shapeup-kickoff.prompt.md",
                ".github/prompts/shapeup-pitch.prompt.md",
                ".github/prompts/tdd-review.prompt.md",
                ".github/prompts/tdd-session.prompt.md",
                ".github/prompts/threat-model.prompt.md",
                ".github/skills/dependencyAudit/SKILL.md",
                ".github/skills/devopsCiCd/SKILL.md",
                ".github/skills/devopsContainers/SKILL.md",
                ".github/skills/devopsInfraAsCode/SKILL.md",
                ".github/skills/devopsReview/SKILL.md",
                ".github/skills/docsApi/SKILL.md",
                ".github/skills/docsReview/SKILL.md",
                ".github/skills/docsStructure/SKILL.md",
                ".github/skills/docsStyle/SKILL.md",
                ".github/skills/leanAndon/SKILL.md",
                ".github/skills/leanContext/SKILL.md",
                ".github/skills/leanOutput/SKILL.md",
                ".github/skills/leanVerification/SKILL.md",
                ".github/skills/lifecycleAudit/SKILL.md",
                ".github/skills/mlopsDataPipelines/SKILL.md",
                ".github/skills/mlopsExperiments/SKILL.md",
                ".github/skills/mlopsModelServing/SKILL.md",
                ".github/skills/mlopsReview/SKILL.md",
                ".github/skills/ossChangelog/SKILL.md",
                ".github/skills/ossCodeReview/SKILL.md",
                ".github/skills/ossContributing/SKILL.md",
                ".github/skills/ossLicensing/SKILL.md",
                ".github/skills/secretScanning/SKILL.md",
                ".github/skills/secureReview/SKILL.md",
                ".github/skills/shapeupBetting/SKILL.md",
                ".github/skills/shapeupCycleWork/SKILL.md",
                ".github/skills/shapeupPitching/SKILL.md",
                ".github/skills/shapeupReview/SKILL.md",
                ".github/skills/tddCycle/SKILL.md",
                ".github/skills/testArchitecture/SKILL.md",
                ".github/skills/testCoverage/SKILL.md",
                ".github/skills/testDoubles/SKILL.md",
                ".github/skills/threatModel/SKILL.md",
            ],
            payload["result"]["plannedLockfile"]["contents"]["skippedManagedFiles"],
        )
        self.assertEqual(
            {
                "required": False,  # pure-add fresh install: no files overwritten
                "root": None,
                "targets": [],
                "archiveRoot": ".xanadAssistant/archive",
                "archiveTargets": [],
            },
            payload["result"]["backupPlan"],
        )
        token_subs = {entry["token"]: entry for entry in payload["result"]["tokenSubstitutions"]}
        workspace_name = Path(payload["workspace"]).name
        # All expected tokens must be registered — catches accidental additions or removals
        self.assertEqual(
            {"{{WORKSPACE_NAME}}", "{{XANAD_PROFILE}}", "{{PRIMARY_LANGUAGE}}",
             "{{PACKAGE_MANAGER}}", "{{TEST_COMMAND}}", "{{RESPONSE_STYLE}}",
             "{{AUTONOMY_LEVEL}}", "{{AGENT_PERSONA}}", "{{TESTING_PHILOSOPHY}}"},
            set(token_subs),
        )
        # WORKSPACE_NAME resolves to workspace dir name and appears in both surfaces
        self.assertEqual(workspace_name, token_subs["{{WORKSPACE_NAME}}"]["value"])
        self.assertIn(".github/copilot-instructions.md", token_subs["{{WORKSPACE_NAME}}"]["targets"])
        self.assertIn(".github/prompts/setup.md", token_subs["{{WORKSPACE_NAME}}"]["targets"])
        # XANAD_PROFILE resolves to the default profile
        self.assertEqual("balanced", token_subs["{{XANAD_PROFILE}}"]["value"])
        # Tier 2/3 defaults are set and contain the expected keyword
        self.assertIn("Balanced", token_subs["{{RESPONSE_STYLE}}"]["value"])
        self.assertIn("Ask first", token_subs["{{AUTONOMY_LEVEL}}"]["value"])
        self.assertIn("Professional", token_subs["{{AGENT_PERSONA}}"]["value"])
        self.assertIn("Always", token_subs["{{TESTING_PHILOSOPHY}}"]["value"])
        # Scanned tokens get fallback value for an empty workspace (no project files)
        self.assertEqual("(not detected)", token_subs["{{PRIMARY_LANGUAGE}}"]["value"])
        self.assertEqual("(not detected)", token_subs["{{PACKAGE_MANAGER}}"]["value"])
        self.assertEqual("(not detected)", token_subs["{{TEST_COMMAND}}"]["value"])
        self.assertEqual(
            {
                "instructions": "local",
                "prompts": "local",
                "agents": "plugin-backed-copilot-format",
                "skills": "plugin-backed-copilot-format",
                "hooks": "local",
                "mcp": "local",
                "vscode-settings": "local",
            },
            payload["result"]["ownershipBySurface"],
        )
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
                        "packs.selected": ["lean"],
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
        self.assertEqual(["lean"], payload["result"]["packs"])
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
        self.assertEqual(True, payload["result"]["resolvedAnswers"]["mcp.enabled"])
        self.assertEqual(True, payload["result"]["resolvedAnswers"]["hooks.enabled"])

        action_targets = {action["target"] for action in payload["result"]["actions"]}
        self.assertIn(".github/hooks/scripts/xanadWorkspaceMcp.py", action_targets)
        self.assertIn(".vscode/mcp.json", action_targets)

        skipped = {entry["target"]: entry["reason"] for entry in payload["result"]["skippedActions"]}
        self.assertEqual("plugin-backed-ownership", skipped[".github/agents/xanadLifecycle.agent.md"])
        self.assertEqual("plugin-backed-ownership", skipped[".github/skills/lifecycleAudit/SKILL.md"])

    def test_plan_setup_ignores_unknown_answer_ids_with_warning(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            handle.write(json.dumps({"profile.selected": "lean", "legacy.question": True}))
            answers_path = handle.name

        try:
            result = self.run_command("plan", "setup", "--json", "--answers", answers_path)
        finally:
            Path(answers_path).unlink(missing_ok=True)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("lean", payload["result"]["resolvedAnswers"]["profile.selected"])
        warning = next(
            item for item in payload["warnings"]
            if item["code"] == "unknown_answer_ids_ignored"
        )
        self.assertEqual(["legacy.question"], warning["details"]["questionIds"])

    def test_plan_setup_accepts_explicit_dict_option_answers(self) -> None:
        """Dict-option questions (Tier 2/3) must accept their valid option ids via --answers."""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            handle.write(json.dumps({
                "response.style": "concise",
                "autonomy.level": "act-then-tell",
                "agent.persona": "mentor",
                "testing.philosophy": "suggest",
            }))
            answers_path = handle.name

        try:
            result = self.run_command("plan", "setup", "--json", "--answers", answers_path)
        finally:
            Path(answers_path).unlink(missing_ok=True)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        resolved = payload["result"]["resolvedAnswers"]
        self.assertEqual("concise", resolved["response.style"])
        self.assertEqual("act-then-tell", resolved["autonomy.level"])
        self.assertEqual("mentor", resolved["agent.persona"])
        self.assertEqual("suggest", resolved["testing.philosophy"])

    def test_plan_setup_fills_defaults_for_omitted_answer_keys(self) -> None:
        """Omitted answer keys must resolve to their declared defaults (INSTALL.md contract)."""
        # Partial answer file — only one explicit override; all other keys are absent.
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            handle.write(json.dumps({"profile.selected": "balanced"}))
            answers_path = handle.name

        try:
            result = self.run_command(
                "plan", "setup", "--json", "--answers", answers_path, "--non-interactive"
            )
        finally:
            Path(answers_path).unlink(missing_ok=True)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        resolved = payload["result"]["resolvedAnswers"]
        # The explicit answer is applied.
        self.assertEqual("balanced", resolved["profile.selected"])
        # All other questions must still be resolved (not absent or None).
        self.assertIn("mcp.enabled", resolved)
        self.assertIn("response.style", resolved)
        self.assertIn("autonomy.level", resolved)
        self.assertIn("agent.persona", resolved)
        self.assertIn("testing.philosophy", resolved)
        # Defaults match the declared values in _interview_questions.py.
        self.assertEqual("balanced", resolved["response.style"])
        self.assertEqual("ask-first", resolved["autonomy.level"])
        self.assertEqual("professional", resolved["agent.persona"])
        self.assertEqual("always", resolved["testing.philosophy"])
        self.assertTrue(payload["result"]["questionsResolved"])


if __name__ == "__main__":
    unittest.main()
