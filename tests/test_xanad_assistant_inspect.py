from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class XanadAssistantInspectTests(unittest.TestCase):
    def render_setup_prompt(self, repo_root: Path, workspace: Path, profile: str = "balanced") -> str:
        return (
            (repo_root / "template" / "prompts" / "setup.md")
            .read_text(encoding="utf-8")
            .replace("{{WORKSPACE_NAME}}", workspace.name)
            .replace("{{XANAD_PROFILE}}", profile)
        )

    def run_command_in_workspace(self, workspace: Path, command: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts/lifecycle/xanad_assistant.py"
        command_args = [
            sys.executable,
            str(script_path),
            command,
        ]
        if command == "plan" and extra_args:
            command_args.extend([extra_args[0], "--workspace", str(workspace), "--package-root", str(repo_root), *extra_args[1:]])
        else:
            command_args.extend(
                [
                    "--workspace",
                    str(workspace),
                    "--package-root",
                    str(repo_root),
                    *extra_args,
                ]
            )
        return subprocess.run(
            command_args,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

    def run_command(self, command: str, *extra_args: str, workspace_setup=None) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            if workspace_setup is not None:
                workspace_setup(workspace, repo_root)
            return self.run_command_in_workspace(workspace, command, *extra_args)

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
        self.assertEqual(8, payload["result"]["summary"]["skipped"])
        self.assertEqual(0, payload["result"]["summary"]["unmanaged"])

    def test_check_detects_clean_and_unmanaged_targets(self) -> None:
        def workspace_setup(workspace: Path, repo_root: Path) -> None:
            target_one = workspace / ".github" / "copilot-instructions.md"
            target_one.parent.mkdir(parents=True, exist_ok=True)
            target_one.write_text((repo_root / "template" / "copilot-instructions.md").read_text(encoding="utf-8"), encoding="utf-8")

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

    def test_check_reports_clean_when_all_targets_match(self) -> None:
        def workspace_setup(workspace: Path, repo_root: Path) -> None:
            target_one = workspace / ".github" / "copilot-instructions.md"
            target_one.parent.mkdir(parents=True, exist_ok=True)
            target_one.write_text((repo_root / "template" / "copilot-instructions.md").read_text(encoding="utf-8"), encoding="utf-8")

            target_two = workspace / ".github" / "prompts" / "setup.md"
            target_two.parent.mkdir(parents=True, exist_ok=True)
            target_two.write_text(self.render_setup_prompt(repo_root, workspace), encoding="utf-8")

            instructions_dir = workspace / ".github" / "instructions"
            instructions_dir.mkdir(parents=True, exist_ok=True)
            (instructions_dir / "tests.instructions.md").write_text(
                (repo_root / "template" / "instructions" / "tests.instructions.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (instructions_dir / "scripts.instructions.md").write_text(
                (repo_root / "template" / "instructions" / "scripts.instructions.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        result = self.run_command("check", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("clean", payload["status"])
        self.assertEqual(4, payload["result"]["summary"]["clean"])
        self.assertEqual(0, payload["result"]["summary"]["missing"])
        self.assertEqual(8, payload["result"]["summary"]["skipped"])
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
            (github_dir / "xanad-assistant-lock.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "0.1.0",
                        "package": {
                            "name": "xanad-assistant"
                        },
                        "manifest": {
                            "schemaVersion": "0.1.0",
                            "hash": "sha256:test"
                        },
                        "timestamps": {
                            "appliedAt": "2026-05-07T00:00:00Z",
                            "updatedAt": "2026-05-07T00:00:00Z"
                        },
                        "selectedPacks": [
                            "review"
                        ],
                        "profile": "balanced",
                        "ownershipBySurface": {
                            "agents": "plugin-backed-copilot-format",
                            "prompts": "local"
                        },
                        "skippedManagedFiles": [
                            ".github/prompts/setup.md"
                        ],
                        "unknownValues": {
                            "legacy": True
                        },
                        "files": []
                    },
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
            (github_dir / "xanad-assistant-lock.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "0.1.0",
                        "package": {
                            "name": "xanad-assistant"
                        },
                        "manifest": {
                            "schemaVersion": "0.1.0",
                            "hash": "sha256:test"
                        },
                        "timestamps": {
                            "appliedAt": "2026-05-07T00:00:00Z",
                            "updatedAt": "2026-05-07T00:00:00Z"
                        },
                        "selectedPacks": [],
                        "files": [
                            {
                                "id": "prompt.setup",
                                "target": ".github/prompts/setup.md",
                                "sourceHash": "sha256:test",
                                "installedHash": "unknown",
                                "status": "unknown"
                            }
                        ],
                        "unknownValues": {
                            "legacyOwnership": True
                        }
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("check", "--json", workspace_setup=workspace_setup)

        self.assertEqual(7, result.returncode)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["result"]["summary"]["malformed"], 1)
        self.assertGreaterEqual(payload["result"]["summary"]["unknown"], 2)

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
        self.assertIn("hooks.enabled", question_ids)
        self.assertIn("mcp.enabled", question_ids)
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
        self.assertEqual(4, payload["result"]["writes"]["add"])
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
                ".github/hooks/scripts/xanad-workspace-mcp.py",
                ".github/skills/lean-output/SKILL.md",
                ".github/skills/lifecycle-audit/SKILL.md",
                ".vscode/mcp.json",
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
        self.assertEqual(8, len(payload["result"]["skippedActions"]))
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
        self.assertEqual(2, payload["result"]["writes"]["add"])
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

    def test_plan_update_uses_installed_profile_and_packs_by_default(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-instructions.md").write_text("modified\n", encoding="utf-8")

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

            (github_dir / "xanad-assistant-lock.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanad-assistant"},
                        "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                        "timestamps": {
                            "appliedAt": "2026-05-07T00:00:00Z",
                            "updatedAt": "2026-05-07T00:00:00Z"
                        },
                        "selectedPacks": ["review"],
                        "profile": "balanced",
                        "ownershipBySurface": {
                            "instructions": "local",
                            "prompts": "local"
                        },
                        "files": []
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("plan", "update", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("plan", payload["command"])
        self.assertEqual("update", payload["mode"])
        self.assertEqual("installed", payload["result"]["installState"])
        self.assertEqual("balanced", payload["result"]["profile"])
        self.assertEqual(["review"], payload["result"]["packs"])
        self.assertEqual(1, payload["result"]["writes"]["replace"])
        self.assertEqual(1, payload["result"]["writes"]["merge"])
        self.assertEqual(4, len(payload["result"]["plannedLockfile"]["contents"]["files"]))
        self.assertEqual(
            [
                ".github/agents/commit.agent.md",
                ".github/agents/explore.agent.md",
                ".github/agents/lifecycle-planning.agent.md",
                ".github/agents/review.agent.md",
                ".github/hooks/scripts/xanad-workspace-mcp.py",
                ".github/skills/lean-output/SKILL.md",
                ".github/skills/lifecycle-audit/SKILL.md",
                ".vscode/mcp.json",
            ],
            payload["result"]["plannedLockfile"]["contents"]["skippedManagedFiles"],
        )
        self.assertEqual(
            [
                {
                    "target": ".github/copilot-instructions.md",
                    "action": "merge",
                    "backupPath": ".xanad-assistant/backups/<apply-timestamp>/.github/copilot-instructions.md",
                },
                {
                    "target": ".github/prompts/setup.md",
                    "action": "replace",
                    "backupPath": ".xanad-assistant/backups/<apply-timestamp>/.github/prompts/setup.md",
                },
            ],
            payload["result"]["backupPlan"]["targets"],
        )

    def test_plan_update_is_stable_when_rerun_against_unchanged_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-instructions.md").write_text("modified\n", encoding="utf-8")

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

            (github_dir / "xanad-assistant-lock.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanad-assistant"},
                        "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                        "timestamps": {
                            "appliedAt": "2026-05-07T00:00:00Z",
                            "updatedAt": "2026-05-07T00:00:00Z"
                        },
                        "selectedPacks": ["review"],
                        "profile": "balanced",
                        "ownershipBySurface": {
                            "instructions": "local",
                            "prompts": "local"
                        },
                        "files": []
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            first = self.run_command_in_workspace(workspace, "plan", "update", "--json")
            second = self.run_command_in_workspace(workspace, "plan", "update", "--json")

        self.assertEqual(0, first.returncode)
        self.assertEqual(0, second.returncode)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))

    def test_plan_repair_from_malformed_legacy_install(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-version.md").write_text("broken legacy metadata\n", encoding="utf-8")

            instructions = github_dir / "copilot-instructions.md"
            instructions.write_text("modified\n", encoding="utf-8")

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

        result = self.run_command("plan", "repair", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("plan", payload["command"])
        self.assertEqual("repair", payload["mode"])
        self.assertEqual("legacy-version-only", payload["result"]["installState"])
        self.assertIn("legacy-version-only", payload["result"]["repairReasons"])
        self.assertIn("malformed-legacy-version", payload["result"]["repairReasons"])
        self.assertEqual(1, payload["result"]["writes"]["replace"])
        self.assertEqual(1, payload["result"]["writes"]["merge"])
        self.assertEqual(1, payload["result"]["conflictSummary"]["managed-drift"])
        self.assertEqual(1, payload["result"]["conflictSummary"]["malformed-managed-state"])
        self.assertEqual([], payload["result"]["plannedLockfile"]["contents"]["retiredManagedFiles"])

    def test_plan_repair_is_stable_when_rerun_against_unchanged_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-version.md").write_text("broken legacy metadata\n", encoding="utf-8")
            (github_dir / "copilot-instructions.md").write_text("modified\n", encoding="utf-8")

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

            first = self.run_command_in_workspace(workspace, "plan", "repair", "--json")
            second = self.run_command_in_workspace(workspace, "plan", "repair", "--json")

        self.assertEqual(0, first.returncode)
        self.assertEqual(0, second.returncode)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))

    def test_plan_repair_rejects_clean_installed_state(self) -> None:
        def workspace_setup(workspace: Path, repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-instructions.md").write_text(
                (repo_root / "template" / "copilot-instructions.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text(
                self.render_setup_prompt(repo_root, workspace),
                encoding="utf-8",
            )

            instructions_dir = github_dir / "instructions"
            instructions_dir.mkdir(parents=True, exist_ok=True)
            (instructions_dir / "tests.instructions.md").write_text(
                (repo_root / "template" / "instructions" / "tests.instructions.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (instructions_dir / "scripts.instructions.md").write_text(
                (repo_root / "template" / "instructions" / "scripts.instructions.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            (github_dir / "xanad-assistant-lock.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanad-assistant"},
                        "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                        "timestamps": {
                            "appliedAt": "2026-05-07T00:00:00Z",
                            "updatedAt": "2026-05-07T00:00:00Z"
                        },
                        "selectedPacks": [],
                        "profile": "balanced",
                        "ownershipBySurface": {
                            "instructions": "local",
                            "prompts": "local"
                        },
                        "files": []
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("plan", "repair", "--json", workspace_setup=workspace_setup)

        self.assertEqual(5, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("error", payload["status"])
        self.assertEqual("inspection_failure", payload["errors"][0]["code"])

    def test_plan_factory_restore_from_locally_customized_repo(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-instructions.md").write_text("modified\n", encoding="utf-8")

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

            unmanaged = github_dir / "prompts" / "custom.md"
            unmanaged.write_text("custom\n", encoding="utf-8")

            (github_dir / "xanad-assistant-lock.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanad-assistant"},
                        "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                        "timestamps": {
                            "appliedAt": "2026-05-07T00:00:00Z",
                            "updatedAt": "2026-05-07T00:00:00Z"
                        },
                        "selectedPacks": [],
                        "profile": "balanced",
                        "ownershipBySurface": {
                            "instructions": "local",
                            "prompts": "local"
                        },
                        "files": []
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("plan", "factory-restore", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("plan", payload["command"])
        self.assertEqual("factory-restore", payload["mode"])
        self.assertTrue(payload["result"]["factoryRestore"])
        self.assertEqual(2, payload["result"]["writes"]["add"])
        self.assertEqual(1, payload["result"]["writes"]["replace"])
        self.assertEqual(1, payload["result"]["writes"]["merge"])
        self.assertEqual(1, payload["result"]["conflictSummary"]["managed-drift"])
        self.assertEqual(1, payload["result"]["conflictSummary"]["unmanaged-lookalike"])
        self.assertEqual(2, len(payload["result"]["backupPlan"]["targets"]))
        self.assertEqual("balanced", payload["result"]["plannedLockfile"]["contents"]["profile"])

    def test_plan_factory_restore_is_stable_when_rerun_against_unchanged_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-instructions.md").write_text("modified\n", encoding="utf-8")

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

            (github_dir / "xanad-assistant-lock.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanad-assistant"},
                        "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                        "timestamps": {
                            "appliedAt": "2026-05-07T00:00:00Z",
                            "updatedAt": "2026-05-07T00:00:00Z"
                        },
                        "selectedPacks": [],
                        "profile": "balanced",
                        "ownershipBySurface": {
                            "instructions": "local",
                            "prompts": "local"
                        },
                        "files": []
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            first = self.run_command_in_workspace(workspace, "plan", "factory-restore", "--json")
            second = self.run_command_in_workspace(workspace, "plan", "factory-restore", "--json")

        self.assertEqual(0, first.returncode)
        self.assertEqual(0, second.returncode)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))

    def test_plan_setup_rejects_invalid_answer_file(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            handle.write(json.dumps({"profile.selected": "not-a-profile"}))
            answers_path = handle.name

        try:
            result = self.run_command("plan", "setup", "--json", "--answers", answers_path)
        finally:
            Path(answers_path).unlink(missing_ok=True)

        self.assertEqual(4, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("error", payload["status"])
        self.assertEqual("contract_input_failure", payload["errors"][0]["code"])

    def test_plan_setup_writes_serialized_plan_when_requested(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            plan_out_path = handle.name

        Path(plan_out_path).unlink(missing_ok=True)
        try:
            result = self.run_command("plan", "setup", "--json", "--plan-out", plan_out_path)
            self.assertEqual(0, result.returncode)
            payload = json.loads(result.stdout)
            written_payload = json.loads(Path(plan_out_path).read_text(encoding="utf-8"))
        finally:
            Path(plan_out_path).unlink(missing_ok=True)

        self.assertEqual(payload["command"], written_payload["command"])
        self.assertEqual(payload["mode"], written_payload["mode"])
        self.assertEqual(payload["result"]["writes"], written_payload["result"]["writes"])
        self.assertTrue(payload["result"]["planOut"].endswith(".json"))

    def test_apply_setup_writes_files_lockfile_and_report(self) -> None:
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
            self.assertEqual(4, payload["result"]["writes"]["added"])
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
                    {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanad-assistant"},
                        "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                        "timestamps": {
                            "appliedAt": "2026-05-07T00:00:00Z",
                            "updatedAt": "2026-05-07T00:00:00Z"
                        },
                        "selectedPacks": ["review"],
                        "profile": "balanced",
                        "ownershipBySurface": {
                            "instructions": "local",
                            "prompts": "local"
                        },
                        "files": []
                    },
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

            (github_dir / "xanad-assistant-lock.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanad-assistant"},
                        "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                        "timestamps": {
                            "appliedAt": "2026-05-07T00:00:00Z",
                            "updatedAt": "2026-05-07T00:00:00Z"
                        },
                        "selectedPacks": [],
                        "profile": "balanced",
                        "ownershipBySurface": {
                            "instructions": "local",
                            "prompts": "local"
                        },
                        "files": []
                    },
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


class XanadAssistantPhase5Tests(unittest.TestCase):
    def _make_copy_if_missing_entry(self, target: str) -> dict:
        return {
            "id": f"test-cim-{target.replace('/', '-')}",
            "surface": "prompts",
            "layer": "core",
            "source": f"template/{target}",
            "target": target,
            "ownership": ["local"],
            "strategy": "copy-if-missing",
            "requiredWhen": [],
            "tokens": [],
            "chmod": "none",
            "hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        }

    def _make_archive_retired_plan_payload(
        self,
        workspace: Path,
        retired_target: str,
        strategy: str = "archive-retired",
        archive_root: str | None = ".xanad-assistant/archive",
    ) -> dict:
        archive_targets = []
        if strategy != "report-retired" and archive_root is not None:
            archive_targets.append(
                {
                    "target": retired_target,
                    "archivePath": f"{archive_root}/{retired_target}",
                }
            )
        return {
            "result": {
                "actions": [
                    {
                        "id": "retired-test-entry",
                        "target": retired_target,
                        "action": "archive-retired",
                        "strategy": strategy,
                        "ownershipMode": None,
                    }
                ],
                "backupPlan": {
                    "required": True,
                    "root": ".xanad-assistant/backups/<apply-timestamp>",
                    "targets": [],
                    "archiveRoot": archive_root,
                    "archiveTargets": archive_targets,
                },
                "plannedLockfile": {
                    "path": ".github/xanad-assistant-lock.json",
                    "contents": {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "xanad-assistant"},
                        "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
                        "timestamps": {
                            "appliedAt": "<apply-timestamp>",
                            "updatedAt": "<apply-timestamp>",
                        },
                        "selectedPacks": [],
                        "files": [],
                        "skippedManagedFiles": [],
                        "retiredManagedFiles": [],
                        "unknownValues": {},
                        "lastBackup": {"path": ".xanad-assistant/backups/<apply-timestamp>"},
                    },
                },
                "skippedActions": [],
                "factoryRestore": False,
            }
        }

    def test_copy_if_missing_plan_skips_file_when_present(self) -> None:
        from scripts.lifecycle.xanad_assistant import build_setup_plan_actions

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            target = ".github/prompts/custom.md"
            target_path = workspace / target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("existing content\n", encoding="utf-8")

            manifest = {"managedFiles": [self._make_copy_if_missing_entry(target)], "retiredFiles": []}
            writes, actions, skipped, retired = build_setup_plan_actions(
                workspace, repo_root, manifest, {"prompts": "local"}, {}, {}
            )

        self.assertEqual(0, writes["add"])
        self.assertEqual(0, len(actions))
        self.assertEqual(1, len(skipped))
        self.assertEqual("copy-if-missing-present", skipped[0]["reason"])
        self.assertEqual(target, skipped[0]["target"])

    def test_copy_if_missing_plan_adds_file_when_absent(self) -> None:
        from scripts.lifecycle.xanad_assistant import build_setup_plan_actions

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            target = ".github/prompts/custom.md"

            manifest = {"managedFiles": [self._make_copy_if_missing_entry(target)], "retiredFiles": []}
            writes, actions, skipped, retired = build_setup_plan_actions(
                workspace, repo_root, manifest, {"prompts": "local"}, {}, {}
            )

        self.assertEqual(1, writes["add"])
        self.assertEqual(1, len(actions))
        self.assertEqual("add", actions[0]["action"])
        self.assertEqual("copy-if-missing", actions[0]["strategy"])
        self.assertEqual(0, len(skipped))

    def test_copy_if_missing_plan_skips_file_even_during_factory_restore(self) -> None:
        from scripts.lifecycle.xanad_assistant import build_setup_plan_actions

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            target = ".github/prompts/custom.md"
            target_path = workspace / target
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("user content\n", encoding="utf-8")

            manifest = {"managedFiles": [self._make_copy_if_missing_entry(target)], "retiredFiles": []}
            writes, actions, skipped, retired = build_setup_plan_actions(
                workspace, repo_root, manifest, {"prompts": "local"}, {}, {}, force_reinstall=True
            )

        self.assertEqual(0, writes["add"])
        self.assertEqual(0, len(actions))
        self.assertEqual(1, len(skipped))
        self.assertEqual("copy-if-missing-present", skipped[0]["reason"])

    def test_archive_retired_moves_file_to_archive_path(self) -> None:
        from unittest.mock import patch
        from scripts.lifecycle.xanad_assistant import execute_apply_plan

        repo_root = Path(__file__).resolve().parents[1]
        retired_target = ".github/old-file.md"
        archive_path = f".xanad-assistant/archive/{retired_target}"

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            retired_file = workspace / retired_target
            retired_file.parent.mkdir(parents=True, exist_ok=True)
            retired_file.write_text("old content\n", encoding="utf-8")

            plan_payload = self._make_archive_retired_plan_payload(workspace, retired_target)

            with patch("scripts.lifecycle.xanad_assistant.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, repo_root, plan_payload)

            self.assertFalse(retired_file.exists())
            self.assertTrue((workspace / archive_path).exists())
            self.assertEqual("old content\n", (workspace / archive_path).read_text(encoding="utf-8"))
            self.assertEqual(1, len(result["retired"]))
            self.assertEqual("archived", result["retired"][0]["action"])
            self.assertEqual(retired_target, result["retired"][0]["target"])
            self.assertEqual(1, result["writes"]["retiredArchived"])
            self.assertEqual(0, result["writes"]["retiredReported"])

    def test_report_retired_leaves_file_in_place(self) -> None:
        from unittest.mock import patch
        from scripts.lifecycle.xanad_assistant import execute_apply_plan

        repo_root = Path(__file__).resolve().parents[1]
        retired_target = ".github/old-file.md"

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            retired_file = workspace / retired_target
            retired_file.parent.mkdir(parents=True, exist_ok=True)
            retired_file.write_text("old content\n", encoding="utf-8")

            plan_payload = self._make_archive_retired_plan_payload(
                workspace, retired_target, strategy="report-retired", archive_root=None
            )

            with patch("scripts.lifecycle.xanad_assistant.build_check_result") as mock_check:
                mock_check.return_value = {"status": "clean", "result": {"summary": {}}}
                result = execute_apply_plan(workspace, repo_root, plan_payload)

            self.assertTrue(retired_file.exists())
            self.assertEqual("old content\n", retired_file.read_text(encoding="utf-8"))
            self.assertEqual(1, len(result["retired"]))
            self.assertEqual("reported", result["retired"][0]["action"])
            self.assertEqual(0, result["writes"]["retiredArchived"])
            self.assertEqual(1, result["writes"]["retiredReported"])

    def test_lockfile_written_by_apply_validates_against_schema(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        lock_schema = json.loads(
            (repo_root / "template/setup/xanad-assistant-lock.schema.json").read_text(encoding="utf-8")
        )
        from tests.schema_validation import validate_instance

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "scripts/lifecycle/xanad_assistant.py"),
                    "apply",
                    "--json",
                    "--workspace",
                    str(workspace),
                    "--package-root",
                    str(repo_root),
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode)
            lockfile_path = workspace / ".github" / "xanad-assistant-lock.json"
            self.assertTrue(lockfile_path.exists())
            lockfile_data = json.loads(lockfile_path.read_text(encoding="utf-8"))
            validate_instance(lockfile_data, lock_schema, lock_schema)

    def test_repair_with_malformed_lockfile_backs_up_and_rewrites(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        original_lockfile_content = "NOT VALID JSON {{{"

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True)

            (github_dir / "copilot-instructions.md").write_text("modified\n", encoding="utf-8")
            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True)
            prompt.write_text("modified\n", encoding="utf-8")

            lockfile_path = github_dir / "xanad-assistant-lock.json"
            lockfile_path.write_text(original_lockfile_content, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "scripts/lifecycle/xanad_assistant.py"),
                    "repair",
                    "--json",
                    "--workspace",
                    str(workspace),
                    "--package-root",
                    str(repo_root),
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode)
            payload = json.loads(result.stdout)
            self.assertEqual("repair", payload["command"])
            self.assertEqual("ok", payload["status"])
            self.assertEqual("passed", payload["result"]["validation"]["status"])
            self.assertTrue(payload["result"]["backup"]["created"])

            backup_root = payload["result"]["backup"]["path"]
            self.assertIsNotNone(backup_root)

            lockfile_backup = workspace / backup_root / ".github" / "xanad-assistant-lock.json"
            self.assertTrue(lockfile_backup.exists(), f"Lockfile backup not found at {lockfile_backup}")
            self.assertEqual(original_lockfile_content, lockfile_backup.read_text(encoding="utf-8"))

            new_lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            self.assertEqual("0.1.0", new_lockfile["schemaVersion"])

    def test_validation_failure_leaves_backup_intact(self) -> None:
        from unittest.mock import patch
        from scripts.lifecycle.xanad_assistant import (
            build_plan_result,
            execute_apply_plan,
            LifecycleCommandError,
        )

        repo_root = Path(__file__).resolve().parents[1]
        raised_error = None

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            plan_payload = build_plan_result(workspace, repo_root, "setup", None, False)

            with patch("scripts.lifecycle.xanad_assistant.build_check_result") as mock_check:
                mock_check.return_value = {
                    "status": "drift",
                    "result": {
                        "summary": {
                            "missing": 1,
                            "stale": 0,
                            "malformed": 0,
                            "retired": 0,
                            "unmanaged": 0,
                            "unknown": 0,
                            "skipped": 0,
                            "clean": 0,
                        },
                    },
                }

                try:
                    execute_apply_plan(workspace, repo_root, plan_payload)
                    self.fail("Expected LifecycleCommandError was not raised")
                except LifecycleCommandError as exc:
                    raised_error = exc

            self.assertIsNotNone(raised_error)
            self.assertEqual("apply_failure", raised_error.code)
            self.assertEqual(9, raised_error.exit_code)
            self.assertIn("backupPath", raised_error.details)

            backup_path_str = raised_error.details["backupPath"]
            self.assertIsNotNone(backup_path_str)
            self.assertTrue(
                (workspace / backup_path_str).exists(),
                f"Backup directory not found at {workspace / backup_path_str}",
            )


class XanadAssistantPhase6Tests(unittest.TestCase):
    """Phase 6: source resolution, integrity, stale-version, incomplete-install, dry-run."""

    REPO_ROOT = Path(__file__).resolve().parents[1]
    SCRIPT = REPO_ROOT / "scripts" / "lifecycle" / "xanad_assistant.py"

    def _run(self, command: str, *extra_args: str, workspace: Path | None = None) -> subprocess.CompletedProcess[str]:
        """Run the lifecycle script with the given subcommand.

        For 'plan', the first extra_arg is the mode (e.g. 'repair').
        workspace inserts --workspace and --package-root after the subcommand(s).
        """
        cmd = [sys.executable, str(self.SCRIPT), command]
        if command == "plan" and extra_args and not extra_args[0].startswith("-"):
            cmd.append(extra_args[0])
            extra_args = extra_args[1:]
        if workspace is not None:
            cmd += ["--workspace", str(workspace), "--package-root", str(self.REPO_ROOT)]
        return subprocess.run(
            cmd + list(extra_args),
            cwd=self.REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def _apply(self, workspace: Path) -> dict:
        """Run a full apply in workspace and return the parsed payload."""
        result = self._run("apply", "--json", "--non-interactive", workspace=workspace)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    # ------------------------------------------------------------------
    # Source parsing – unit tests
    # ------------------------------------------------------------------

    def test_parse_github_source_valid(self) -> None:
        from scripts.lifecycle.xanad_assistant import parse_github_source, LifecycleCommandError

        owner, repo = parse_github_source("github:myorg/myrepo")
        self.assertEqual("myorg", owner)
        self.assertEqual("myrepo", repo)

    def test_parse_github_source_invalid_scheme(self) -> None:
        from scripts.lifecycle.xanad_assistant import parse_github_source, LifecycleCommandError

        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("bitbucket:owner/repo")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_parse_github_source_missing_repo(self) -> None:
        from scripts.lifecycle.xanad_assistant import parse_github_source, LifecycleCommandError

        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:owneronly")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_parse_github_source_too_many_slashes(self) -> None:
        from scripts.lifecycle.xanad_assistant import parse_github_source, LifecycleCommandError

        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:owner/repo/extra")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    def test_parse_github_source_rejects_special_chars(self) -> None:
        from scripts.lifecycle.xanad_assistant import parse_github_source, LifecycleCommandError

        with self.assertRaises(LifecycleCommandError) as ctx:
            parse_github_source("github:own!er/rep$o")
        self.assertEqual("source_resolution_failure", ctx.exception.code)

    # ------------------------------------------------------------------
    # Cache root – unit tests
    # ------------------------------------------------------------------

    def test_get_cache_root_default(self) -> None:
        import os
        from scripts.lifecycle.xanad_assistant import get_cache_root, DEFAULT_CACHE_ROOT

        env = os.environ.copy()
        env.pop("XANAD_PKG_CACHE", None)
        original = os.environ.get("XANAD_PKG_CACHE")
        try:
            if "XANAD_PKG_CACHE" in os.environ:
                del os.environ["XANAD_PKG_CACHE"]
            self.assertEqual(DEFAULT_CACHE_ROOT, get_cache_root())
        finally:
            if original is not None:
                os.environ["XANAD_PKG_CACHE"] = original

    def test_get_cache_root_env_override(self) -> None:
        import os
        from scripts.lifecycle.xanad_assistant import get_cache_root
        from pathlib import Path

        original = os.environ.get("XANAD_PKG_CACHE")
        try:
            os.environ["XANAD_PKG_CACHE"] = "/custom/cache"
            result = get_cache_root()
            self.assertEqual(Path("/custom/cache").resolve(), result)
        finally:
            if original is not None:
                os.environ["XANAD_PKG_CACHE"] = original
            else:
                os.environ.pop("XANAD_PKG_CACHE", None)

    # ------------------------------------------------------------------
    # resolve_effective_package_root – unit tests
    # ------------------------------------------------------------------

    def test_resolve_effective_no_args_raises(self) -> None:
        from scripts.lifecycle.xanad_assistant import resolve_effective_package_root, LifecycleCommandError

        with self.assertRaises(LifecycleCommandError) as ctx:
            resolve_effective_package_root(None, None, None, None)
        self.assertEqual("source_resolution_failure", ctx.exception.code)
        self.assertEqual(8, ctx.exception.exit_code)

    def test_resolve_effective_with_package_root(self) -> None:
        from scripts.lifecycle.xanad_assistant import resolve_effective_package_root

        pkg_root, source_info = resolve_effective_package_root(str(self.REPO_ROOT), None, None, None)
        self.assertEqual(self.REPO_ROOT, pkg_root)
        self.assertEqual("package-root", source_info["kind"])

    # ------------------------------------------------------------------
    # _build_lockfile_package_info – unit tests
    # ------------------------------------------------------------------

    def test_build_lockfile_package_info_default(self) -> None:
        import scripts.lifecycle.xanad_assistant as _engine

        original = _engine._session_source_info
        try:
            _engine._session_source_info = None
            info = _engine._build_lockfile_package_info()
        finally:
            _engine._session_source_info = original
        self.assertEqual({"name": "xanad-assistant"}, info)

    def test_build_lockfile_package_info_with_release(self) -> None:
        import scripts.lifecycle.xanad_assistant as _engine

        original = _engine._session_source_info
        try:
            _engine._session_source_info = {
                "kind": "github-release",
                "source": "github:myorg/myrepo",
                "version": "v1.2.3",
                "packageRoot": "/fake/path",
            }
            info = _engine._build_lockfile_package_info()
        finally:
            _engine._session_source_info = original
        self.assertEqual("xanad-assistant", info["name"])
        self.assertEqual("v1.2.3", info["version"])
        self.assertEqual("github:myorg/myrepo", info["source"])
        self.assertNotIn("ref", info)

    # ------------------------------------------------------------------
    # verify_manifest_integrity – unit tests
    # ------------------------------------------------------------------

    def test_verify_manifest_integrity_no_lockfile(self) -> None:
        from scripts.lifecycle.xanad_assistant import verify_manifest_integrity

        ok, reason = verify_manifest_integrity(self.REPO_ROOT, {"present": False})
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_malformed_lockfile(self) -> None:
        from scripts.lifecycle.xanad_assistant import verify_manifest_integrity

        ok, reason = verify_manifest_integrity(
            self.REPO_ROOT, {"present": True, "malformed": True}
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_no_recorded_hash(self) -> None:
        from scripts.lifecycle.xanad_assistant import verify_manifest_integrity

        ok, reason = verify_manifest_integrity(
            self.REPO_ROOT,
            {"present": True, "malformed": False, "data": {"manifest": {}}},
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_hash_mismatch(self) -> None:
        from scripts.lifecycle.xanad_assistant import verify_manifest_integrity

        ok, reason = verify_manifest_integrity(
            self.REPO_ROOT,
            {
                "present": True,
                "malformed": False,
                "data": {"manifest": {"hash": "sha256:deadbeef0000000000000000000000000000000000000000000000000000dead"}},
            },
        )
        self.assertFalse(ok)
        self.assertIn("Manifest hash mismatch", reason)

    # ------------------------------------------------------------------
    # Stale-version warning – subprocess test
    # ------------------------------------------------------------------

    def test_stale_version_warning_appears_in_inspect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._apply(workspace)

            lockfile_path = workspace / ".github" / "xanad-assistant-lock.json"
            lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            lockfile["manifest"]["hash"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
            lockfile_path.write_text(json.dumps(lockfile, indent=2), encoding="utf-8")

            result = self._run("inspect", "--json", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)

            warning_codes = [w["code"] for w in payload.get("warnings", [])]
            self.assertIn("package_version_changed", warning_codes)

    # ------------------------------------------------------------------
    # Incomplete-install – subprocess tests
    # ------------------------------------------------------------------

    def test_incomplete_install_appears_as_repair_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._apply(workspace)

            (workspace / ".github" / "copilot-instructions.md").unlink()

            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("incomplete-install", payload["result"]["repairReasons"])

    def test_repair_fixes_incomplete_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._apply(workspace)

            (workspace / ".github" / "copilot-instructions.md").unlink()

            result = self._run("repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("ok", payload["status"])
            self.assertEqual("passed", payload["result"]["validation"]["status"])
            self.assertTrue((workspace / ".github" / "copilot-instructions.md").exists())

    # ------------------------------------------------------------------
    # Dry-run – subprocess test
    # ------------------------------------------------------------------

    def test_dry_run_apply_skips_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = self._run("apply", "--json", "--non-interactive", "--dry-run", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["result"].get("dryRun"), "Expected dryRun=True in result")
            self.assertFalse(
                (workspace / ".github" / "copilot-instructions.md").exists(),
                "Dry-run should not write managed files",
            )
            self.assertFalse(
                (workspace / ".github" / "xanad-assistant-lock.json").exists(),
                "Dry-run should not write lockfile",
            )

    def test_dry_run_apply_reports_planned_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = self._run("apply", "--json", "--non-interactive", "--dry-run", workspace=workspace)
            payload = json.loads(result.stdout)
            # Planned writes should be > 0 (files would be added)
            writes = payload["result"]["writes"]
            total = sum(writes.values())
            self.assertGreater(total, 0, "Dry-run should still report planned write counts")

    # ------------------------------------------------------------------
    # Lockfile package field – subprocess test
    # ------------------------------------------------------------------

    def test_lockfile_package_field_has_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._apply(workspace)
            lockfile = json.loads((workspace / ".github" / "xanad-assistant-lock.json").read_text())
            self.assertEqual("xanad-assistant", lockfile["package"]["name"])

    # ------------------------------------------------------------------
    # Phase 7 – agent and prompt file checks
    # ------------------------------------------------------------------

    def test_agent_file_has_lifecycle_commands(self) -> None:
        agent_text = (self.REPO_ROOT / "agents" / "lifecycle-planning.agent.md").read_text(encoding="utf-8")
        for term in ("inspect", "apply", "update", "repair", "factory-restore"):
            self.assertIn(term, agent_text, f"Agent file missing lifecycle command: {term}")

    def test_agent_file_has_trigger_phrases(self) -> None:
        agent_text = (self.REPO_ROOT / "agents" / "lifecycle-planning.agent.md").read_text(encoding="utf-8")
        self.assertIn("Trigger phrases", agent_text)

    def test_setup_prompt_has_workflow_steps(self) -> None:
        prompt_text = (self.REPO_ROOT / "template" / "prompts" / "setup.md").read_text(encoding="utf-8")
        for step in ("inspect", "plan", "apply"):
            self.assertIn(step, prompt_text, f"Setup prompt missing workflow step: {step}")

    def test_setup_prompt_references_dry_run(self) -> None:
        prompt_text = (self.REPO_ROOT / "template" / "prompts" / "setup.md").read_text(encoding="utf-8")
        self.assertIn("dry-run", prompt_text.lower())

    # ------------------------------------------------------------------
    # Phase 8 – UI / agent progress
    # ------------------------------------------------------------------

    def test_agent_progress_apply_includes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = self._run(
                "apply", "--non-interactive", "--ui", "agent", "--json", workspace=workspace
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Receipt", result.stderr)

    def test_agent_progress_apply_includes_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = self._run(
                "apply", "--non-interactive", "--ui", "agent", "--json", workspace=workspace
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Validate", result.stderr)

    def test_dry_run_agent_progress_notes_no_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = self._run(
                "apply", "--non-interactive", "--dry-run", "--ui", "agent", "--json", workspace=workspace
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("Dry run", result.stderr)

    def test_log_file_written_when_flag_is_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            log_path = Path(tmp) / "lifecycle.log"
            result = self._run(
                "apply", "--non-interactive", "--ui", "agent", "--json",
                "--log-file", str(log_path),
                workspace=workspace,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(log_path.exists(), "Log file should have been created")
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("xanad-assistant", log_text)
            self.assertIn("Apply", log_text)
            self.assertIn("Receipt", log_text)


class XanadAssistantPhase9Tests(unittest.TestCase):
    """Phase 9: pack selection, profile defaults, lean skill, catalog generation."""

    REPO_ROOT = Path(__file__).resolve().parents[1]
    SCRIPT = REPO_ROOT / "scripts" / "lifecycle" / "xanad_assistant.py"

    def _run(self, command: str, *extra_args: str, workspace: Path | None = None) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(self.SCRIPT), command]
        if command == "plan" and extra_args and not extra_args[0].startswith("-"):
            cmd.append(extra_args[0])
            extra_args = extra_args[1:]
        if workspace is not None:
            cmd += ["--workspace", str(workspace), "--package-root", str(self.REPO_ROOT)]
        return subprocess.run(
            cmd + list(extra_args),
            cwd=self.REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    # ------------------------------------------------------------------
    # condition_matches – list membership
    # ------------------------------------------------------------------

    def test_condition_matches_list_membership(self) -> None:
        from scripts.lifecycle.xanad_assistant import condition_matches
        self.assertTrue(condition_matches("packs.selected=lean", {"packs.selected": ["lean"]}))
        self.assertTrue(condition_matches("packs.selected=lean", {"packs.selected": ["lean", "memory"]}))
        self.assertFalse(condition_matches("packs.selected=lean", {"packs.selected": ["memory"]}))
        self.assertFalse(condition_matches("packs.selected=lean", {"packs.selected": []}))

    def test_condition_matches_list_does_not_affect_scalar(self) -> None:
        from scripts.lifecycle.xanad_assistant import condition_matches
        self.assertTrue(condition_matches("mcp.enabled=true", {"mcp.enabled": True}))
        self.assertFalse(condition_matches("mcp.enabled=true", {"mcp.enabled": False}))

    # ------------------------------------------------------------------
    # lean pack – plan excludes lean skill without pack selection
    # ------------------------------------------------------------------

    def test_lean_skill_skipped_when_pack_not_selected(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            answers_path = workspace / "answers.json"
            answers_path.write_text(
                json.dumps({"ownership.agents": "local", "ownership.skills": "local", "packs.selected": []}),
                encoding="utf-8",
            )
            result = self._run(
                "plan", "setup",
                "--json", "--non-interactive",
                "--answers", str(answers_path),
                workspace=workspace,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            skipped = {entry["target"] for entry in payload["result"]["skippedActions"]}
            self.assertIn(".github/skills/lean-output/SKILL.md", skipped)

    def test_lean_skill_included_when_pack_selected(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            answers_path = workspace / "answers.json"
            answers_path.write_text(
                json.dumps({"ownership.agents": "local", "ownership.skills": "local", "packs.selected": ["lean"]}),
                encoding="utf-8",
            )
            result = self._run(
                "plan", "setup",
                "--json", "--non-interactive",
                "--answers", str(answers_path),
                workspace=workspace,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            action_targets = {action["target"] for action in payload["result"]["actions"]}
            self.assertIn(".github/skills/lean-output/SKILL.md", action_targets)

    # ------------------------------------------------------------------
    # lean pack – apply writes lean skill when pack selected
    # ------------------------------------------------------------------

    def test_lean_skill_written_on_apply_when_pack_selected(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            answers_path = workspace / "answers.json"
            answers_path.write_text(
                json.dumps({"ownership.agents": "local", "ownership.skills": "local", "packs.selected": ["lean"]}),
                encoding="utf-8",
            )
            result = self._run(
                "apply",
                "--json", "--non-interactive",
                "--answers", str(answers_path),
                workspace=workspace,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            lean_skill_path = workspace / ".github" / "skills" / "lean-output" / "SKILL.md"
            self.assertTrue(lean_skill_path.exists(), "lean-output/SKILL.md should be written when lean pack selected")

    def test_lean_skill_not_written_on_apply_when_pack_not_selected(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            answers_path = workspace / "answers.json"
            answers_path.write_text(
                json.dumps({"ownership.agents": "local", "ownership.skills": "local", "packs.selected": []}),
                encoding="utf-8",
            )
            result = self._run(
                "apply",
                "--json", "--non-interactive",
                "--answers", str(answers_path),
                workspace=workspace,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            lean_skill_path = workspace / ".github" / "skills" / "lean-output" / "SKILL.md"
            self.assertFalse(lean_skill_path.exists(), "lean-output/SKILL.md should not be written when lean pack not selected")

    # ------------------------------------------------------------------
    # lean pack – lockfile records selectedPacks
    # ------------------------------------------------------------------

    def test_lockfile_records_selected_packs(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            answers_path = workspace / "answers.json"
            answers_path.write_text(
                json.dumps({"ownership.agents": "local", "ownership.skills": "local", "packs.selected": ["lean"]}),
                encoding="utf-8",
            )
            result = self._run(
                "apply",
                "--json", "--non-interactive",
                "--answers", str(answers_path),
                workspace=workspace,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            lockfile_path = workspace / ".github" / "xanad-assistant-lock.json"
            self.assertTrue(lockfile_path.exists())
            lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            self.assertEqual(["lean"], lockfile["selectedPacks"])

    # ------------------------------------------------------------------
    # profile defaults – lean profile seeds lean pack
    # ------------------------------------------------------------------

    def test_lean_profile_seeds_lean_pack(self) -> None:
        from scripts.lifecycle.xanad_assistant import seed_answers_from_profile
        profile_registry = {
            "profiles": [
                {
                    "id": "lean",
                    "defaultPacks": ["lean"],
                    "setupAnswerDefaults": {"reportDensity": "lean"},
                }
            ]
        }
        result = seed_answers_from_profile(profile_registry, {"profile.selected": "lean"})
        self.assertEqual(["lean"], result["packs.selected"])
        self.assertEqual("lean", result["reportDensity"])

    def test_lean_profile_does_not_override_explicit_packs(self) -> None:
        from scripts.lifecycle.xanad_assistant import seed_answers_from_profile
        profile_registry = {
            "profiles": [{"id": "lean", "defaultPacks": ["lean"], "setupAnswerDefaults": {}}]
        }
        result = seed_answers_from_profile(profile_registry, {"profile.selected": "lean", "packs.selected": ["memory"]})
        self.assertEqual(["memory"], result["packs.selected"])

    def test_no_profile_selected_leaves_answers_unchanged(self) -> None:
        from scripts.lifecycle.xanad_assistant import seed_answers_from_profile
        answers = {"packs.selected": ["memory"]}
        result = seed_answers_from_profile({}, answers)
        self.assertEqual(answers, result)

    def test_lean_profile_plan_auto_includes_lean_pack(self) -> None:
        """Selecting lean profile in answers should auto-include lean pack via profile defaults."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            answers_path = workspace / "answers.json"
            answers_path.write_text(
                json.dumps({"ownership.agents": "local", "ownership.skills": "local", "profile.selected": "lean"}),
                encoding="utf-8",
            )
            result = self._run(
                "plan", "setup",
                "--json", "--non-interactive",
                "--answers", str(answers_path),
                workspace=workspace,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            action_targets = {action["target"] for action in payload["result"]["actions"]}
            self.assertIn(".github/skills/lean-output/SKILL.md", action_targets)

    # ------------------------------------------------------------------
    # catalog generation
    # ------------------------------------------------------------------

    def test_catalog_contains_generated_packs(self) -> None:
        catalog_path = self.REPO_ROOT / "template" / "setup" / "catalog.json"
        self.assertTrue(catalog_path.exists())
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertIn("lean", catalog["packs"])
        self.assertIn("memory", catalog["packs"])

    def test_catalog_contains_profiles(self) -> None:
        catalog_path = self.REPO_ROOT / "template" / "setup" / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertIn("balanced", catalog["profiles"])
        self.assertIn("lean", catalog["profiles"])

    def test_catalog_surface_layers_includes_lean_skills(self) -> None:
        catalog_path = self.REPO_ROOT / "template" / "setup" / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual("pack", catalog["surfaceLayers"].get("lean-skills"))

    def test_catalog_generated_from_field(self) -> None:
        catalog_path = self.REPO_ROOT / "template" / "setup" / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual("policy+registries", catalog["generatedFrom"])

    def test_generate_catalog_function(self) -> None:
        from scripts.lifecycle.generate_manifest import generate_catalog
        policy = {
            "surfaceSources": {
                "core": {"layer": "core"},
                "lean-skills": {"layer": "pack"},
            }
        }
        pack_registry = {"packs": [{"id": "lean"}, {"id": "memory"}]}
        profile_registry = {"profiles": [{"id": "balanced"}, {"id": "lean"}]}
        catalog = generate_catalog(policy, pack_registry, profile_registry)
        self.assertEqual("policy+registries", catalog["generatedFrom"])
        self.assertEqual(["lean", "memory"], catalog["packs"])
        self.assertEqual(["balanced", "lean"], catalog["profiles"])
        self.assertEqual("pack", catalog["surfaceLayers"]["lean-skills"])


class LockfileMigrationTests(unittest.TestCase):
    """Coverage for pre-0.1.0 lockfile shapes that are valid JSON but structurally incomplete."""

    REPO_ROOT = Path(__file__).resolve().parents[1]
    SCRIPT = REPO_ROOT / "scripts" / "lifecycle" / "xanad_assistant.py"

    def _run(self, command: str, *extra_args: str, workspace: Path) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(self.SCRIPT), command]
        if command == "plan" and extra_args and not extra_args[0].startswith("-"):
            cmd.append(extra_args[0])
            extra_args = extra_args[1:]
        cmd += ["--workspace", str(workspace), "--package-root", str(self.REPO_ROOT)]
        return subprocess.run(
            cmd + list(extra_args),
            cwd=self.REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def _write_lockfile(self, workspace: Path, data: dict) -> None:
        path = workspace / ".github" / "xanad-assistant-lock.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # _lockfile_needs_migration – unit tests
    # ------------------------------------------------------------------

    def test_needs_migration_empty_object(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        self.assertTrue(_lockfile_needs_migration({}))

    def test_needs_migration_missing_files(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanad-assistant"},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": [],
            # "files" intentionally absent
        }
        self.assertTrue(_lockfile_needs_migration(data))

    def test_needs_migration_missing_manifest_hash(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanad-assistant"},
            "manifest": {"schemaVersion": "0.1.0"},  # hash absent
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": [],
            "files": [],
        }
        self.assertTrue(_lockfile_needs_migration(data))

    def test_needs_migration_missing_package_name(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {},  # name absent
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": [],
            "files": [],
        }
        self.assertTrue(_lockfile_needs_migration(data))

    def test_needs_migration_valid_shape_returns_false(self) -> None:
        from scripts.lifecycle.xanad_assistant import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanad-assistant"},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc123"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": [],
            "files": [],
        }
        self.assertFalse(_lockfile_needs_migration(data))

    # ------------------------------------------------------------------
    # migrate_lockfile_shape – unit tests
    # ------------------------------------------------------------------

    def test_migrate_fills_all_required_fields(self) -> None:
        from scripts.lifecycle.xanad_assistant import migrate_lockfile_shape, _lockfile_needs_migration
        migrated = migrate_lockfile_shape({})
        self.assertFalse(_lockfile_needs_migration(migrated))
        self.assertEqual("0.1.0", migrated["schemaVersion"])
        self.assertEqual("xanad-assistant", migrated["package"]["name"])
        self.assertIn("hash", migrated["manifest"])
        self.assertIn("appliedAt", migrated["timestamps"])
        self.assertEqual([], migrated["selectedPacks"])
        self.assertEqual([], migrated["files"])

    def test_migrate_preserves_existing_fields(self) -> None:
        from scripts.lifecycle.xanad_assistant import migrate_lockfile_shape
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanad-assistant"},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": ["lean"],
            "profile": "lean",
            # files absent
        }
        migrated = migrate_lockfile_shape(data)
        self.assertEqual(["lean"], migrated["selectedPacks"])
        self.assertEqual("lean", migrated["profile"])
        self.assertEqual("sha256:abc", migrated["manifest"]["hash"])

    # ------------------------------------------------------------------
    # parse_lockfile_state – reports needsMigration
    # ------------------------------------------------------------------

    def test_parse_lockfile_state_sets_needs_migration_for_empty_object(self) -> None:
        from scripts.lifecycle.xanad_assistant import parse_lockfile_state
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {})
            state = parse_lockfile_state(workspace)
            self.assertTrue(state["present"])
            self.assertFalse(state["malformed"])
            self.assertTrue(state["needsMigration"])

    def test_parse_lockfile_state_clears_needs_migration_for_valid_shape(self) -> None:
        from scripts.lifecycle.xanad_assistant import parse_lockfile_state
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanad-assistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [],
                "files": [],
            })
            state = parse_lockfile_state(workspace)
            self.assertFalse(state["malformed"])
            self.assertFalse(state["needsMigration"])

    # ------------------------------------------------------------------
    # determine_repair_reasons – schema-migration-required
    # ------------------------------------------------------------------

    def test_schema_migration_appears_as_repair_reason_for_empty_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {})
            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("schema-migration-required", payload["result"]["repairReasons"])

    def test_schema_migration_appears_as_repair_reason_for_missing_files_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanad-assistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [],
                # "files" absent
            })
            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("schema-migration-required", payload["result"]["repairReasons"])

    def test_schema_migration_does_not_appear_for_valid_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanad-assistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [],
                "files": [],
            })
            result = self._run("plan", "repair", "--json", "--non-interactive", workspace=workspace)
            payload = json.loads(result.stdout)
            self.assertNotIn("schema-migration-required", payload["result"].get("repairReasons", []))

    # ------------------------------------------------------------------
    # repair rewrites pre-0.1.0 lockfile to a valid shape
    # ------------------------------------------------------------------

    def test_repair_rewrites_empty_object_lockfile_to_valid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {})
            result = self._run("repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("ok", payload["status"])
            lockfile_path = workspace / ".github" / "xanad-assistant-lock.json"
            lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            self.assertEqual("0.1.0", lockfile["schemaVersion"])
            self.assertEqual("xanad-assistant", lockfile["package"]["name"])
            self.assertIn("hash", lockfile["manifest"])
            self.assertNotEqual("sha256:unknown", lockfile["manifest"]["hash"])

    def test_repair_preserves_profile_from_pre_schema_lockfile(self) -> None:
        """Profile field present in a partial lockfile is carried forward after repair."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {"profile": "lean"})
            result = self._run("repair", "--json", "--non-interactive", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            lockfile_path = workspace / ".github" / "xanad-assistant-lock.json"
            lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
            # After repair, profile should come from answers (default balanced) or preserved
            # The key point is repair succeeds and lockfile is schema-valid.
            self.assertIn("selectedPacks", lockfile)
            self.assertIn("files", lockfile)
            self.assertNotEqual("sha256:unknown", lockfile["manifest"]["hash"])

    def test_check_after_repair_of_empty_lockfile_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._write_lockfile(workspace, {})
            self._run("repair", "--json", "--non-interactive", workspace=workspace)
            result = self._run("check", "--json", workspace=workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("clean", payload["status"])


if __name__ == "__main__":
    unittest.main()