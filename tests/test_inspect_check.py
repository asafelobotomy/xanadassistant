from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
