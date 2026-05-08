from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase


class XanadAssistantPhase9Tests(XanadTestBase):
    """Phase 9: pack selection, profile defaults, lean skill, catalog generation."""

    # ------------------------------------------------------------------
    # condition_matches – list membership
    # ------------------------------------------------------------------

    def test_lean_profile_does_not_override_explicit_packs(self) -> None:
        from scripts.lifecycle.xanad_assistant import seed_answers_from_profile
        profile_registry = {
            "profiles": [{"id": "lean", "defaultPacks": ["lean"], "setupAnswerDefaults": {}}]
        }
        result = seed_answers_from_profile(profile_registry, {"profile.selected": "lean", "packs.selected": ["memory"]})
        self.assertEqual(["memory"], result["packs.selected"])

    def test_no_profile_selected_leaves_answers_unchanged(self) -> None:
        from scripts.lifecycle.xanad_assistant import seed_answers_from_profile
        answers = {"packs.selected": ["memory"]}
        result = seed_answers_from_profile({}, answers)
        self.assertEqual(answers, result)

    def test_lean_profile_plan_auto_includes_lean_pack(self) -> None:
        """Selecting lean profile in answers should auto-include lean pack via profile defaults."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            answers_path = workspace / "answers.json"
            answers_path.write_text(
                json.dumps({"ownership.agents": "local", "ownership.skills": "local", "profile.selected": "lean"}),
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
    # catalog generation
    # ------------------------------------------------------------------

    def test_catalog_contains_generated_packs(self) -> None:
        catalog_path = self.REPO_ROOT / "template" / "setup" / "catalog.json"
        self.assertTrue(catalog_path.exists())
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertIn("lean", catalog["packs"])
        self.assertIn("memory", catalog["packs"])

    def test_catalog_contains_profiles(self) -> None:
        catalog_path = self.REPO_ROOT / "template" / "setup" / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertIn("balanced", catalog["profiles"])
        self.assertIn("lean", catalog["profiles"])

    def test_catalog_surface_layers_includes_lean_skills(self) -> None:
        catalog_path = self.REPO_ROOT / "template" / "setup" / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual("pack", catalog["surfaceLayers"].get("lean-skills"))

    def test_catalog_generated_from_field(self) -> None:
        catalog_path = self.REPO_ROOT / "template" / "setup" / "catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual("policy+registries", catalog["generatedFrom"])

    def test_generate_catalog_function(self) -> None:
        from scripts.lifecycle.generate_manifest import generate_catalog
        policy = {
            "surfaceSources": {
                "core": {"layer": "core"},
                "lean-skills": {"layer": "pack"},
            }
        }
        pack_registry = {"packs": [{"id": "lean"}, {"id": "memory"}]}
        profile_registry = {"profiles": [{"id": "balanced"}, {"id": "lean"}]}
        catalog = generate_catalog(policy, pack_registry, profile_registry)
        self.assertEqual("policy+registries", catalog["generatedFrom"])
        self.assertEqual(["lean", "memory"], catalog["packs"])
        self.assertEqual(["balanced", "lean"], catalog["profiles"])
        self.assertEqual("pack", catalog["surfaceLayers"]["lean-skills"])



if __name__ == "__main__":
    unittest.main()
