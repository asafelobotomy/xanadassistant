from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class PromptContractTests(unittest.TestCase):
    def test_template_prompts_use_serialized_plan_apply_flow(self) -> None:
        prompt_paths = [
            REPO_ROOT / "template" / "prompts" / "bootstrap.md",
            REPO_ROOT / "template" / "prompts" / "setup.md",
        ]

        for prompt_path in prompt_paths:
            with self.subTest(prompt=prompt_path.name):
                content = prompt_path.read_text(encoding="utf-8")
                self.assertIn("--plan-out", content)
                self.assertIn("--plan .xanadAssistant/tmp/setup-plan.json", content)
                self.assertNotRegex(content, re.compile(r"apply \\\n(?:.+\\\n)*\s+--answers "))

    def test_readme_uses_serialized_plan_apply_flow(self) -> None:
        content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("--plan-out .xanadAssistant/tmp/setup-plan.json", content)
        self.assertIn("--plan .xanadAssistant/tmp/setup-plan.json --json", content)
        self.assertNotRegex(content, re.compile(r"xanadBootstrap.py apply \\\n(?:.+\\\n)*\s+--answers "))


if __name__ == "__main__":
    unittest.main()