"""Phase 4c — Lean-pack conditioned surface apply tests.

Covers:
1. lean-prompts surface — written when packs.selected=lean
2. lean-hooks surface — written when packs.selected=lean AND mcp.enabled (default True)
3. lean-hooks surface — NOT written when mcp.enabled=False
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


class LeanPackSurfaceApplyTests(XanadTestBase):
    """Lean-pack conditioned surfaces (prompts, hooks) are written when conditions are met."""

    def test_apply_lean_pack_writes_prompt_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            self.assertTrue(
                (ws / ".github" / "prompts" / "lean-plan.prompt.md").exists(),
                "lean-plan.prompt.md not written",
            )
            self.assertTrue(
                (ws / ".github" / "prompts" / "lean-review.prompt.md").exists(),
                "lean-review.prompt.md not written",
            )
            self.assertTrue(
                (ws / ".github" / "prompts" / "lean-status.prompt.md").exists(),
                "lean-status.prompt.md not written",
            )

    def test_apply_lean_pack_with_mcp_enabled_writes_hook_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            # mcp.enabled defaults to True, so no explicit override needed
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})),
                encoding="utf-8",
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            hooks_dir = ws / ".github" / "hooks" / "scripts"
            self.assertTrue(
                (hooks_dir / "leanContextBudget.py").exists(),
                "leanContextBudget.py not written",
            )
            self.assertTrue(
                (hooks_dir / "leanTestReporter.py").exists(),
                "leanTestReporter.py not written",
            )

    def test_apply_lean_pack_without_mcp_does_not_write_hook_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["lean"], "mcp.enabled": False})),
                encoding="utf-8",
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            hooks_dir = ws / ".github" / "hooks" / "scripts"
            self.assertFalse(
                (hooks_dir / "leanContextBudget.py").exists(),
                "leanContextBudget.py should not be written when mcp.enabled=False",
            )
            self.assertFalse(
                (hooks_dir / "leanTestReporter.py").exists(),
                "leanTestReporter.py should not be written when mcp.enabled=False",
            )


if __name__ == "__main__":
    unittest.main()
