from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class PlanLifecycleTests(XanadTestBase):
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

        result = self.run_command("plan", "factory-restore", "--json", workspace_setup=workspace_setup)

        self.assertEqual(0, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("plan", payload["command"])
        self.assertEqual("factory-restore", payload["mode"])
        self.assertTrue(payload["result"]["factoryRestore"])
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



if __name__ == "__main__":
    unittest.main()
