from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import add_skill_sections


class AddSkillSectionsTests(unittest.TestCase):
    def test_add_sections_injects_missing_sections_and_verify_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            skill_path = repo_root / "packs" / "demo" / "skills" / "demoSkill" / "SKILL.md"
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(
                "# Demo Skill\n\n## Steps\n\n- Do the thing\n",
                encoding="utf-8",
            )

            with mock.patch("scripts.add_skill_sections.REPO", str(repo_root)):
                add_skill_sections.add_sections(
                    "packs/demo/skills/demoSkill/SKILL.md",
                    ["Use this when drafting or reviewing a demo skill"],
                    ["Do not use this when another specialized skill applies"],
                    ["Verify the required sections were added"],
                )

            updated = skill_path.read_text(encoding="utf-8")

        self.assertIn("## When to use", updated)
        self.assertIn("## When NOT to use", updated)
        self.assertIn("## Verify", updated)
        self.assertIn("- [ ] Verify the required sections were added", updated)


if __name__ == "__main__":
    unittest.main()