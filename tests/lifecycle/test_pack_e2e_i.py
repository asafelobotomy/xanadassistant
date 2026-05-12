"""Phase 6 — MLOps-pack conditioned surface apply tests.

Covers:
1. mlops-skills surface — written when packs.selected=mlops
2. mlops-prompts surface — written when packs.selected=mlops
3. mlops-hooks surface — written when packs.selected=mlops AND hooks.enabled (default True)
4. mlops-hooks surface — NOT written when mcp.enabled=False
5. No-pack install — no mlops files written
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


def _answers(extra: dict | None = None) -> dict:
    """Minimal answers that write all agents locally."""
    base = {"ownership.agents": "local", "ownership.skills": "local", "packs.selected": []}
    if extra:
        base.update(extra)
    return base


class MlopsPackSurfaceApplyTests(XanadTestBase):
    """MLOps-pack conditioned surfaces (skills, prompts, hooks) are written when conditions are met."""

    def test_apply_mlops_pack_writes_skill_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["mlops"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            skills_dir = ws / ".github" / "skills"
            for skill in ("mlopsDataPipelines", "mlopsExperiments", "mlopsModelServing", "mlopsReview"):
                self.assertTrue(
                    (skills_dir / skill / "SKILL.md").exists(),
                    f"{skill}/SKILL.md not written",
                )

    def test_apply_mlops_pack_writes_prompt_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["mlops"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            prompts_dir = ws / ".github" / "prompts"
            for prompt in ("mlops-experiment.prompt.md", "mlops-drift.prompt.md"):
                self.assertTrue(
                    (prompts_dir / prompt).exists(),
                    f"{prompt} not written",
                )

    def test_apply_mlops_pack_with_hooks_enabled_writes_hook_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["mlops"]})),
                encoding="utf-8",
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            hooks_dir = ws / ".github" / "hooks" / "scripts"
            self.assertTrue(
                (hooks_dir / "mlopsModelCheck.py").exists(),
                "mlopsModelCheck.py not written",
            )

    def test_apply_mlops_pack_without_hooks_does_not_write_hook_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["mlops"], "mcp.enabled": False})),
                encoding="utf-8",
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            hooks_dir = ws / ".github" / "hooks" / "scripts"
            self.assertFalse(
                (hooks_dir / "mlopsModelCheck.py").exists(),
                "mlopsModelCheck.py should not be written when mcp.enabled=False",
            )

    def test_apply_no_pack_does_not_write_mlops_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(json.dumps(_answers()), encoding="utf-8")

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            skills_dir = ws / ".github" / "skills"
            prompts_dir = ws / ".github" / "prompts"
            hooks_dir = ws / ".github" / "hooks" / "scripts"

            for skill in ("mlopsDataPipelines", "mlopsExperiments", "mlopsModelServing", "mlopsReview"):
                self.assertFalse(
                    (skills_dir / skill / "SKILL.md").exists(),
                    f"{skill}/SKILL.md should not be written without mlops pack",
                )
            for prompt in ("mlops-experiment.prompt.md", "mlops-drift.prompt.md"):
                self.assertFalse(
                    (prompts_dir / prompt).exists(),
                    f"{prompt} should not be written without mlops pack",
                )
            self.assertFalse(
                (hooks_dir / "mlopsModelCheck.py").exists(),
                "mlopsModelCheck.py should not be written without mlops pack",
            )


if __name__ == "__main__":
    unittest.main()
