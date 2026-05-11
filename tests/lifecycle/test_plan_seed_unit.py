"""Unit tests for seed answers, successor plans, interview extras, and missing token cases."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]


def _minimal_context(
    workspace: Path,
    install_state: str = "not-installed",
    lockfile_state: dict | None = None,
    legacy_version_state: dict | None = None,
) -> dict:
    """Build a minimal context dict for testing plan/inspect functions."""
    from scripts.lifecycle._xanad._loader import load_manifest, load_json, load_optional_json
    from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
    from pathlib import Path as _Path
    policy = load_json(REPO_ROOT / DEFAULT_POLICY_PATH)
    manifest = load_manifest(REPO_ROOT, policy)
    return {
        "workspace": str(workspace),
        "packageRoot": REPO_ROOT,
        "policy": policy,
        "metadata": {},
        "metadataArtifacts": {},
        "artifacts": {},
        "installState": install_state,
        "installPaths": {},
        "existingSurfaces": {},
        "manifest": manifest,
        "manifestWithStatus": None,
        "warnings": [],
        "lockfileState": lockfile_state or {
            "present": False, "malformed": False, "path": ".github/xanadAssistant-lock.json",
            "data": None, "needsMigration": False, "profile": None, "selectedPacks": [],
            "ownershipBySurface": {}, "files": [], "skippedManagedFiles": [],
            "unknownValues": {}, "originalPackageName": None,
        },
        "legacyVersionState": legacy_version_state or {
            "present": False, "malformed": False,
            "path": ".github/copilot-version.md", "data": None,
        },
        "successorMigrationTargets": [],
    }


# ---------------------------------------------------------------------------
# _plan_c.py — determine_repair_reasons and seeding functions
# ---------------------------------------------------------------------------

class InterviewExtraTests(unittest.TestCase):
    """Additional tests for _interview.py lines not covered by InterviewTests."""

    def test_build_interview_questions_skips_surface_not_in_ownership_defaults(self):
        """_interview.py line 47: surface not in ownershipDefaults is skipped."""
        from scripts.lifecycle._xanad._interview import build_interview_questions
        # Policy with empty ownershipDefaults → both "agents" and "skills" loops hit continue
        policy = {"ownershipDefaults": {}, "canonicalSurfaces": []}
        metadata = {}
        questions = build_interview_questions(policy, metadata, "setup")
        # Should have no ownership questions
        ownership_ids = [q["id"] for q in questions if q["id"].startswith("ownership.")]
        self.assertEqual([], ownership_ids)

    def test_resolve_question_answers_uses_recommended_when_no_default(self):
        """_interview.py lines 205-206: 'recommended' used when no 'default' key."""
        from scripts.lifecycle._xanad._interview import resolve_question_answers
        questions = [
            {
                "id": "q1",
                "kind": "choice",
                "options": ["a", "b"],
                "required": True,
                "recommended": "a",
                # No "default" key — so line 201 condition is False
            }
        ]
        resolved, unresolved, unknown = resolve_question_answers(questions, {})
        self.assertEqual({"q1": "a"}, resolved)
        self.assertEqual([], unresolved)


class PlanBSuccessorTests(unittest.TestCase):
    """Tests for successor migration target handling in build_plan_result."""

    def test_build_plan_result_with_successor_migration_adds_archive_action(self):
        """_plan_b.py lines 183-185: successor migration target is added as archive-retired action."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        import json as _json
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create a predecessor lockfile so the workspace is recognized as migrating
            github = ws / ".github"
            github.mkdir()
            predecessor_lock = {
                "schemaVersion": "0.1.0",
                "package": {"name": "copilot-instructions-template"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [], "profile": "balanced",
                "ownershipBySurface": {}, "setupAnswers": {},
                "installMetadata": {}, "files": [],
                "skippedManagedFiles": [], "retiredManagedFiles": [],
                "unknownValues": {},
            }
            (github / "xanadAssistant-lock.json").write_text(
                _json.dumps(predecessor_lock), encoding="utf-8"
            )
            # Create a file that collect_successor_migration_files will detect
            agents_dir = github / "agents"
            agents_dir.mkdir()
            (agents_dir / "old-agent.agent.md").write_text("# Old agent", encoding="utf-8")
            result = build_plan_result(ws, REPO_ROOT, "setup", None, True)
        retired = result["result"].get("retired", [])
        self.assertTrue(len(retired) > 0)


class SeedAnswersFromInstallStateTests(unittest.TestCase):
    """Tests for the personalisation and mcp.enabled re-seeding from lockfile (Bug 1+2)."""

    def _make_questions(self, *ids: str) -> list:
        q = []
        for qid in ids:
            entry: dict = {"id": qid, "type": "choice"}
            if qid == "profile.selected":
                entry["options"] = ["developer", "researcher"]
            elif qid == "packs.selected":
                entry["options"] = ["lean"]
            elif qid == "mcp.enabled":
                entry["type"] = "boolean"
            q.append(entry)
        return q

    def _minimal_lockfile_state(self, **overrides) -> dict:
        base = {
            "present": True, "malformed": False, "profile": None,
            "selectedPacks": [], "setupAnswers": {}, "mcpEnabled": None,
        }
        base.update(overrides)
        return base

    def test_noop_for_setup_mode(self) -> None:
        from scripts.lifecycle._xanad._plan_c import seed_answers_from_install_state
        lockfile = self._minimal_lockfile_state(setupAnswers={"response.style": "verbose"})
        result = seed_answers_from_install_state("setup", self._make_questions("response.style"), lockfile, {})
        self.assertEqual({}, result)

    def test_reseeds_personalisation_answers_for_update_mode(self) -> None:
        from scripts.lifecycle._xanad._plan_c import seed_answers_from_install_state
        lockfile = self._minimal_lockfile_state(
            setupAnswers={"response.style": "verbose", "autonomy.level": "act-then-tell"}
        )
        questions = self._make_questions("response.style", "autonomy.level")
        result = seed_answers_from_install_state("update", questions, lockfile, {})
        self.assertEqual("verbose", result.get("response.style"))
        self.assertEqual("act-then-tell", result.get("autonomy.level"))

    def test_does_not_overwrite_caller_supplied_answers(self) -> None:
        from scripts.lifecycle._xanad._plan_c import seed_answers_from_install_state
        lockfile = self._minimal_lockfile_state(setupAnswers={"response.style": "verbose"})
        questions = self._make_questions("response.style")
        result = seed_answers_from_install_state("update", questions, lockfile, {"response.style": "concise"})
        self.assertEqual("concise", result.get("response.style"))

    def test_reseeds_mcp_enabled_for_repair_mode(self) -> None:
        from scripts.lifecycle._xanad._plan_c import seed_answers_from_install_state
        lockfile = self._minimal_lockfile_state(mcpEnabled=False)
        questions = self._make_questions("mcp.enabled")
        result = seed_answers_from_install_state("repair", questions, lockfile, {})
        self.assertIs(False, result.get("mcp.enabled"))

    def test_skips_answer_id_not_in_questions(self) -> None:
        from scripts.lifecycle._xanad._plan_c import seed_answers_from_install_state
        lockfile = self._minimal_lockfile_state(setupAnswers={"unknown.key": "x"})
        result = seed_answers_from_install_state("update", self._make_questions("response.style"), lockfile, {})
        self.assertNotIn("unknown.key", result)

    def test_mcp_not_reseeded_when_none_in_lockfile(self) -> None:
        from scripts.lifecycle._xanad._plan_c import seed_answers_from_install_state
        lockfile = self._minimal_lockfile_state(mcpEnabled=None)
        questions = self._make_questions("mcp.enabled")
        result = seed_answers_from_install_state("update", questions, lockfile, {})
        self.assertNotIn("mcp.enabled", result)


class BuildSetupPlanActionsMissingTokenTests(unittest.TestCase):
    """Verify that actions with unresolved tokens report missingTokenValues (Bug 4)."""

    def test_missing_token_recorded_in_action(self) -> None:
        import tempfile, json as _json
        from pathlib import Path as _Path
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions

        with tempfile.TemporaryDirectory() as tmp:
            ws = _Path(tmp)
            # Minimal manifest with one entry that has a token not in token_values
            manifest = {
                "managedFiles": [{
                    "id": "test.file",
                    "surface": "instructions",
                    "target": ".github/test.md",
                    "strategy": "token-replace",
                    "tokens": ["{{MISSING_TOKEN}}"],
                    "ownership": ["local"],
                    "requiredWhen": [],
                }],
                "retiredFiles": [],
            }
            ownership = {"instructions": "local"}
            resolved_answers: dict = {}
            token_values: dict = {}  # deliberately empty — token has no value

            _writes, actions, _skipped, _retired = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership, resolved_answers, token_values
            )

        add_actions = [a for a in actions if a["action"] == "add"]
        self.assertEqual(1, len(add_actions))
        action = add_actions[0]
        self.assertIn("missingTokenValues", action)
        self.assertEqual(["{{MISSING_TOKEN}}"], action["missingTokenValues"])
        self.assertEqual({}, action["tokenValues"])

    def test_no_missing_token_key_when_all_tokens_present(self) -> None:
        import tempfile
        from pathlib import Path as _Path
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions

        with tempfile.TemporaryDirectory() as tmp:
            ws = _Path(tmp)
            manifest = {
                "managedFiles": [{
                    "id": "test.file",
                    "surface": "instructions",
                    "target": ".github/test.md",
                    "strategy": "token-replace",
                    "tokens": ["{{MY_TOKEN}}"],
                    "ownership": ["local"],
                    "requiredWhen": [],
                }],
                "retiredFiles": [],
            }
            ownership = {"instructions": "local"}
            token_values = {"{{MY_TOKEN}}": "hello"}

            _writes, actions, _skipped, _retired = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership, {}, token_values
            )

        add_actions = [a for a in actions if a["action"] == "add"]
        self.assertEqual(1, len(add_actions))
        self.assertNotIn("missingTokenValues", add_actions[0])
        self.assertEqual({"{{MY_TOKEN}}": "hello"}, add_actions[0]["tokenValues"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
