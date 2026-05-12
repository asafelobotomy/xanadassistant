"""Phase 2 — TDD-pack conditioned surface apply tests.

Covers:
1. tdd-skills surface — written when packs.selected=tdd
2. tdd-prompts surface — written when packs.selected=tdd
3. No-tdd install — tdd skill and prompt files are NOT written
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


class TddPackSurfaceApplyTests(XanadTestBase):
    """TDD-pack conditioned surfaces (skills, prompts) are written when conditions are met."""

    def test_apply_tdd_pack_writes_skill_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["tdd"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            skills_dir = ws / ".github" / "skills"
            for skill in ("tddCycle", "testDoubles", "testCoverage"):
                self.assertTrue(
                    (skills_dir / skill / "SKILL.md").exists(),
                    f"{skill}/SKILL.md not written",
                )

    def test_apply_tdd_pack_writes_prompt_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["tdd"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            prompts_dir = ws / ".github" / "prompts"
            for prompt in ("tdd-session.prompt.md", "tdd-review.prompt.md"):
                self.assertTrue(
                    (prompts_dir / prompt).exists(),
                    f"{prompt} not written",
                )

    def test_apply_no_pack_does_not_write_tdd_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(json.dumps(_answers()), encoding="utf-8")

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            skills_dir = ws / ".github" / "skills"
            prompts_dir = ws / ".github" / "prompts"
            for skill in ("tddCycle", "testDoubles", "testCoverage", "testArchitecture"):
                self.assertFalse(
                    (skills_dir / skill / "SKILL.md").exists(),
                    f"{skill}/SKILL.md should not be written without tdd pack",
                )
            for prompt in ("tdd-session.prompt.md", "tdd-review.prompt.md"):
                self.assertFalse(
                    (prompts_dir / prompt).exists(),
                    f"{prompt} should not be written without tdd pack",
                )


if __name__ == "__main__":
    unittest.main()
