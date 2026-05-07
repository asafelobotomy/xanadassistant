from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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



if __name__ == "__main__":
    unittest.main()
