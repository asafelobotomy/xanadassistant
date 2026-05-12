"""Phase 1 — Secure-pack conditioned surface apply tests.

Covers:
1. secure-skills surface — written when packs.selected=secure
2. secure-prompts surface — written when packs.selected=secure
3. secure-hooks surface — written when packs.selected=secure AND hooks.enabled (default True)
4. secure-hooks surface — NOT written when mcp.enabled=False
5. No-pack install — no {{pack:}} markers survive in installed files
"""

from __future__ import annotations

import json
import re
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


class SecurePackSurfaceApplyTests(XanadTestBase):
    """Secure-pack conditioned surfaces (skills, prompts, hooks) are written when conditions are met."""

    def test_apply_no_pack_has_no_raw_pack_markers(self) -> None:
        """No {{pack:…}} markers survive token substitution in a no-pack install."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(json.dumps(_answers()), encoding="utf-8")

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            pattern = re.compile(r"\{\{pack:[^}]+\}\}")
            for path in ws.rglob("*"):
                if path.is_file():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    m = pattern.search(text)
                    self.assertIsNone(
                        m,
                        f"Unresolved pack marker {m.group() if m else ''} found in {path.relative_to(ws)}",
                    )

    def test_apply_secure_pack_writes_skill_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["secure"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            skills_dir = ws / ".github" / "skills"
            for skill in ("secureReview", "threatModel", "secretScanning", "dependencyAudit"):
                self.assertTrue(
                    (skills_dir / skill / "SKILL.md").exists(),
                    f"{skill}/SKILL.md not written",
                )

    def test_apply_secure_pack_writes_prompt_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["secure"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            prompts_dir = ws / ".github" / "prompts"
            self.assertTrue(
                (prompts_dir / "security-review.prompt.md").exists(),
                "security-review.prompt.md not written",
            )
            self.assertTrue(
                (prompts_dir / "threat-model.prompt.md").exists(),
                "threat-model.prompt.md not written",
            )

    def test_apply_secure_pack_with_hooks_enabled_writes_hook_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            # hooks.enabled defaults to True
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["secure"]})),
                encoding="utf-8",
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            hooks_dir = ws / ".github" / "hooks" / "scripts"
            self.assertTrue(
                (hooks_dir / "secureOsv.py").exists(),
                "secureOsv.py not written",
            )

    def test_apply_secure_pack_without_hooks_does_not_write_hook_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["secure"], "mcp.enabled": False})),
                encoding="utf-8",
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            hooks_dir = ws / ".github" / "hooks" / "scripts"
            self.assertFalse(
                (hooks_dir / "secureOsv.py").exists(),
                "secureOsv.py should not be written when mcp.enabled=False",
            )


if __name__ == "__main__":
    unittest.main()
