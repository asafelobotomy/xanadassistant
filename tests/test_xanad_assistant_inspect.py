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
        self.assertEqual(4, payload["result"]["summary"]["skipped"])
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

        result = self.run_command("check", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("clean", payload["status"])
        self.assertEqual(2, payload["result"]["summary"]["clean"])
        self.assertEqual(0, payload["result"]["summary"]["missing"])
        self.assertEqual(4, payload["result"]["summary"]["skipped"])
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
        self.assertEqual(2, payload["result"]["writes"]["add"])
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
                ".github/agents/lifecycle-planning.agent.md",
                ".github/hooks/scripts/xanad-workspace-mcp.py",
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
        self.assertEqual(4, len(payload["result"]["skippedActions"]))
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
        self.assertEqual(0, payload["result"]["writes"]["add"])
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
        self.assertEqual(4, payload["result"]["writes"]["add"])
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
        self.assertEqual(2, len(payload["result"]["plannedLockfile"]["contents"]["files"]))
        self.assertEqual(
            [
                ".github/agents/lifecycle-planning.agent.md",
                ".github/hooks/scripts/xanad-workspace-mcp.py",
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
        self.assertEqual(0, payload["result"]["writes"]["add"])
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
            self.assertEqual(2, payload["result"]["writes"]["added"])
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
            self.assertEqual(3, payload["result"]["writes"]["added"])
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
            self.assertIn("Use `xanad-assistant.py` as the lifecycle authority", installed_instructions)
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


if __name__ == "__main__":
    unittest.main()