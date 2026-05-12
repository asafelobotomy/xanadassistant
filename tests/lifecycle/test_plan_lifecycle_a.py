from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class PlanLifecycleTests(XanadTestBase):
    def test_plan_update_uses_installed_profile_and_packs_by_default(self) -> None:
        def workspace_setup(workspace: Path, _repo_root: Path) -> None:
            github_dir = workspace / ".github"
            github_dir.mkdir(parents=True, exist_ok=True)
            (github_dir / "copilot-instructions.md").write_text("modified\n", encoding="utf-8")

            prompt = github_dir / "prompts" / "setup.md"
            prompt.parent.mkdir(parents=True, exist_ok=True)
            prompt.write_text("modified\n", encoding="utf-8")

            (github_dir / "xanadAssistant-lock.json").write_text(
                json.dumps(
                    self.make_minimal_lockfile(
                        selectedPacks=["lean"],
                        ownershipBySurface={
                            "instructions": "local",
                            "prompts": "local",
                        },
                    ),
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
        self.assertEqual(["lean"], payload["result"]["packs"])
        self.assertEqual(1, payload["result"]["writes"]["replace"])
        self.assertEqual(1, payload["result"]["writes"]["merge"])
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
                ".github/hooks/scripts/mlopsModelCheck.py",
                ".github/hooks/scripts/ossGitLog.py",
                ".github/hooks/scripts/secureOsv.py",
                ".github/hooks/scripts/shapeupScopeCheck.py",
                ".github/prompts/devops-incident.prompt.md",
                ".github/prompts/devops-pipeline.prompt.md",
                ".github/prompts/docs-draft.prompt.md",
                ".github/prompts/docs-review.prompt.md",
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
            [
                {
                    "target": ".github/copilot-instructions.md",
                    "action": "merge",
                    "backupPath": ".xanadAssistant/backups/<apply-timestamp>/.github/copilot-instructions.md",
                },
                {
                    "target": ".github/prompts/setup.md",
                    "action": "replace",
                    "backupPath": ".xanadAssistant/backups/<apply-timestamp>/.github/prompts/setup.md",
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

            (github_dir / "xanadAssistant-lock.json").write_text(
                json.dumps(
                    self.make_minimal_lockfile(
                        selectedPacks=["lean"],
                        ownershipBySurface={
                            "instructions": "local",
                            "prompts": "local",
                        },
                    ),
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

            hooks_dir = github_dir / "hooks" / "scripts"
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

            (github_dir / "xanadAssistant-lock.json").write_text(
                json.dumps(
                    self.make_minimal_lockfile(
                        ownershipBySurface={
                            "instructions": "local",
                            "prompts": "local",
                            "hooks": "local",
                            "mcp": "local",
                        },
                    ),
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

        result = self.run_command("plan", "repair", "--json", workspace_setup=workspace_setup)

        self.assertEqual(5, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("error", payload["status"])
        self.assertEqual("inspection_failure", payload["errors"][0]["code"])



if __name__ == "__main__":
    unittest.main()
