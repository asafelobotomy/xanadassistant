"""Phase 3 — OSS-pack conditioned surface apply tests.

Covers:
1. oss-skills surface — written when packs.selected=oss
2. oss-prompts surface — written when packs.selected=oss
3. oss-hooks surface — written when packs.selected=oss AND hooks.enabled (default True)
4. oss-hooks surface — NOT written when mcp.enabled=False
5. No-pack install — no oss files written
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


class OssPackSurfaceApplyTests(XanadTestBase):
    """OSS-pack conditioned surfaces (skills, prompts, hooks) are written when conditions are met."""

    def test_apply_oss_pack_writes_skill_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["oss"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            skills_dir = ws / ".github" / "skills"
            for skill in ("ossChangelog", "ossCodeReview", "ossContributing", "ossLicensing"):
                self.assertTrue(
                    (skills_dir / skill / "SKILL.md").exists(),
                    f"{skill}/SKILL.md not written",
                )

    def test_apply_oss_pack_writes_prompt_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["oss"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            prompts_dir = ws / ".github" / "prompts"
            for prompt in ("oss-changelog.prompt.md", "oss-pr.prompt.md"):
                self.assertTrue(
                    (prompts_dir / prompt).exists(),
                    f"{prompt} not written",
                )

    def test_apply_oss_pack_with_hooks_enabled_writes_hook_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            # hooks.enabled defaults to True when mcp.enabled is unset
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["oss"]})),
                encoding="utf-8",
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            hooks_dir = ws / ".github" / "hooks" / "scripts"
            self.assertTrue(
                (hooks_dir / "ossGitLog.py").exists(),
                "ossGitLog.py not written",
            )

    def test_apply_oss_pack_without_hooks_does_not_write_hook_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["oss"], "mcp.enabled": False})),
                encoding="utf-8",
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            hooks_dir = ws / ".github" / "hooks" / "scripts"
            self.assertFalse(
                (hooks_dir / "ossGitLog.py").exists(),
                "ossGitLog.py should not be written when mcp.enabled=False",
            )

    def test_apply_no_pack_does_not_write_oss_files(self) -> None:
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

            for skill in ("ossChangelog", "ossCodeReview", "ossContributing", "ossLicensing"):
                self.assertFalse(
                    (skills_dir / skill / "SKILL.md").exists(),
                    f"{skill}/SKILL.md should not be written without oss pack",
                )
            for prompt in ("oss-changelog.prompt.md", "oss-pr.prompt.md"):
                self.assertFalse(
                    (prompts_dir / prompt).exists(),
                    f"{prompt} should not be written without oss pack",
                )
            self.assertFalse(
                (hooks_dir / "ossGitLog.py").exists(),
                "ossGitLog.py should not be written without oss pack",
            )


if __name__ == "__main__":
    unittest.main()
