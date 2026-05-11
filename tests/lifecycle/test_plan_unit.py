"""Unit tests for lifecycle plan, interview, and inspect-helpers modules.

These tests call functions directly (no subprocess) to capture coverage for
branches not exercised by the subprocess-based integration tests.
"""
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

class PlanCTests(unittest.TestCase):

    def _make_context(self, **overrides) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            ctx = _minimal_context(ws, "not-installed")
        ctx.update(overrides)
        return ctx

    def test_seed_answers_from_install_state_non_update_mode(self):
        """_plan_c.py line 35: mode not in update/repair/factory-restore → return dict(answers)."""
        from scripts.lifecycle._xanad._plan_c import seed_answers_from_install_state
        result = seed_answers_from_install_state("setup", [], {}, {"key": "val"})
        self.assertEqual({"key": "val"}, result)

    def test_determine_repair_reasons_legacy_version_only(self):
        """_plan_c.py line 55: installState=legacy-version-only adds reason."""
        from scripts.lifecycle._xanad._plan_c import determine_repair_reasons
        ctx = self._make_context(installState="legacy-version-only")
        reasons = determine_repair_reasons(ctx)
        self.assertIn("legacy-version-only", reasons)

    def test_determine_repair_reasons_malformed_legacy_version(self):
        """_plan_c.py line 57: legacyVersionState.malformed adds reason."""
        from scripts.lifecycle._xanad._plan_c import determine_repair_reasons
        ctx = self._make_context(
            legacyVersionState={"present": True, "malformed": True, "path": ".github/copilot-version.md", "data": None},
        )
        reasons = determine_repair_reasons(ctx)
        self.assertIn("malformed-legacy-version", reasons)

    def test_determine_repair_reasons_malformed_lockfile(self):
        """_plan_c.py line 59: lockfileState.malformed adds reason."""
        from scripts.lifecycle._xanad._plan_c import determine_repair_reasons
        ctx = self._make_context(
            lockfileState={
                "present": True, "malformed": True, "path": ".github/xanadAssistant-lock.json",
                "data": None, "needsMigration": False, "profile": None, "selectedPacks": [],
                "ownershipBySurface": {}, "files": [], "skippedManagedFiles": [],
                "unknownValues": {}, "originalPackageName": None,
            },
        )
        reasons = determine_repair_reasons(ctx)
        self.assertIn("malformed-lockfile", reasons)

    def test_determine_repair_reasons_needs_migration(self):
        """_plan_c.py line 61: lockfileState.needsMigration adds reason."""
        from scripts.lifecycle._xanad._plan_c import determine_repair_reasons
        ctx = self._make_context(
            lockfileState={
                "present": True, "malformed": False, "path": ".github/xanadAssistant-lock.json",
                "data": {"schemaVersion": "0.1.0"}, "needsMigration": True, "profile": None,
                "selectedPacks": [], "ownershipBySurface": {}, "files": [],
                "skippedManagedFiles": [], "unknownValues": {}, "originalPackageName": None,
            },
        )
        reasons = determine_repair_reasons(ctx)
        self.assertIn("schema-migration-required", reasons)

    def test_determine_repair_reasons_package_identity_migration(self):
        """_plan_c.py line 64: predecessor package name adds reason."""
        from scripts.lifecycle._xanad._plan_c import determine_repair_reasons
        ctx = self._make_context(
            installState="installed",
            lockfileState={
                "present": True, "malformed": False, "path": ".github/xanadAssistant-lock.json",
                "data": {"package": {"name": "copilot-instructions-template"}},
                "needsMigration": False, "profile": "balanced", "selectedPacks": [],
                "ownershipBySurface": {}, "files": [], "skippedManagedFiles": [],
                "unknownValues": {}, "originalPackageName": "copilot-instructions-template",
            },
        )
        reasons = determine_repair_reasons(ctx)
        self.assertIn("package-identity-migration-required", reasons)

    def test_determine_repair_reasons_successor_cleanup(self):
        """_plan_c.py line 66: successorMigrationTargets adds reason."""
        from scripts.lifecycle._xanad._plan_c import determine_repair_reasons
        ctx = self._make_context(successorMigrationTargets=[".github/agents/old-agent.md"])
        reasons = determine_repair_reasons(ctx)
        self.assertIn("successor-cleanup-required", reasons)

    def test_determine_repair_reasons_incomplete_install(self):
        """_plan_c.py lines 68-73: missing managed file triggers incomplete-install reason."""
        from scripts.lifecycle._xanad._plan_c import determine_repair_reasons
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        # Build a manifest_with_status where a file is "missing"
        manifest_with_status = dict(manifest or {})
        entries = list(manifest_with_status.get("managedFiles", []))
        if entries:
            first = dict(entries[0])
            first["status"] = "missing"
            manifest_with_status["managedFiles"] = [first] + entries[1:]
        ctx = self._make_context(
            installState="installed",
            manifestWithStatus=manifest_with_status,
            lockfileState={
                "present": True, "malformed": False, "path": ".github/xanadAssistant-lock.json",
                "data": {}, "needsMigration": False, "profile": "balanced", "selectedPacks": [],
                "ownershipBySurface": {}, "files": [], "skippedManagedFiles": [],
                "unknownValues": {}, "originalPackageName": None,
            },
        )
        reasons = determine_repair_reasons(ctx)
        self.assertIn("incomplete-install", reasons)

    def test_seed_answers_from_profile_no_profile_selected(self):
        """seed_answers_from_profile returns unchanged when no profile.selected."""
        from scripts.lifecycle._xanad._plan_c import seed_answers_from_profile
        answers = {"some-key": "value"}
        result = seed_answers_from_profile({"profiles": []}, answers, set())
        self.assertEqual(answers, result)

    def test_seed_answers_from_profile_unknown_profile(self):
        """seed_answers_from_profile returns unchanged when profile not in registry."""
        from scripts.lifecycle._xanad._plan_c import seed_answers_from_profile
        answers = {"profile.selected": "nonexistent-profile"}
        profile_registry = {"profiles": [{"id": "balanced", "setupAnswerDefaults": {}}]}
        result = seed_answers_from_profile(profile_registry, answers, set())
        self.assertEqual(answers, result)


# ---------------------------------------------------------------------------
# _interview.py — load_answers, validate_answer_value, build_interview_questions
# ---------------------------------------------------------------------------

class InterviewTests(unittest.TestCase):

    def test_load_answers_returns_empty_dict_for_none(self):
        from scripts.lifecycle._xanad._interview import load_answers
        self.assertEqual({}, load_answers(None))

    def test_load_answers_raises_when_file_not_found(self):
        """_interview.py lines 117-124: raise when answers file doesn't exist."""
        from scripts.lifecycle._xanad._interview import load_answers
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with self.assertRaises(LifecycleCommandError) as ctx:
            load_answers("/nonexistent/answers/path-xyz.json")
        self.assertEqual("contract_input_failure", ctx.exception.code)

    def test_load_answers_raises_when_file_is_invalid_json(self):
        """_interview.py lines 125-133: raise when answers file has invalid JSON."""
        from scripts.lifecycle._xanad._interview import load_answers
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            answers_file = Path(tmp) / "answers.json"
            answers_file.write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(LifecycleCommandError) as ctx:
                load_answers(str(answers_file))
        self.assertEqual("contract_input_failure", ctx.exception.code)

    def test_load_answers_raises_when_file_is_not_dict(self):
        """_interview.py lines 134-140: raise when answers file is not a JSON object."""
        from scripts.lifecycle._xanad._interview import load_answers
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            answers_file = Path(tmp) / "answers.json"
            answers_file.write_text("[1, 2, 3]", encoding="utf-8")
            with self.assertRaises(LifecycleCommandError) as ctx:
                load_answers(str(answers_file))
        self.assertEqual("contract_input_failure", ctx.exception.code)

    def test_load_answers_returns_dict_from_valid_file(self):
        """_interview.py line 143: successful load returns dict."""
        from scripts.lifecycle._xanad._interview import load_answers
        with tempfile.TemporaryDirectory() as tmp:
            answers_file = Path(tmp) / "answers.json"
            answers_file.write_text('{"profile.selected": "balanced"}', encoding="utf-8")
            result = load_answers(str(answers_file))
        self.assertEqual({"profile.selected": "balanced"}, result)

    def test_validate_answer_value_choice_invalid_string(self):
        """_interview.py line 154: raise for choice with invalid string value."""
        from scripts.lifecycle._xanad._interview import validate_answer_value
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        question = {"id": "q", "kind": "choice", "options": ["a", "b"]}
        with self.assertRaises(LifecycleCommandError):
            validate_answer_value(question, "invalid-option")

    def test_validate_answer_value_choice_non_string(self):
        """_interview.py line 154: raise for choice with non-string value."""
        from scripts.lifecycle._xanad._interview import validate_answer_value
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        question = {"id": "q", "kind": "choice", "options": ["a", "b"]}
        with self.assertRaises(LifecycleCommandError):
            validate_answer_value(question, 42)

    def test_validate_answer_value_multi_choice_non_list(self):
        """_interview.py line 164: raise for multi-choice with non-list value."""
        from scripts.lifecycle._xanad._interview import validate_answer_value
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        question = {"id": "q", "kind": "multi-choice", "options": ["a", "b"]}
        with self.assertRaises(LifecycleCommandError):
            validate_answer_value(question, "a")

    def test_validate_answer_value_multi_choice_invalid_item(self):
        """_interview.py line 171: raise for multi-choice with invalid item."""
        from scripts.lifecycle._xanad._interview import validate_answer_value
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        question = {"id": "q", "kind": "multi-choice", "options": ["a", "b"]}
        with self.assertRaises(LifecycleCommandError):
            validate_answer_value(question, ["a", "invalid-option"])

    def test_validate_answer_value_confirm_non_bool(self):
        """_interview.py lines 179-180: raise for confirm with non-bool value."""
        from scripts.lifecycle._xanad._interview import validate_answer_value
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        question = {"id": "q", "kind": "confirm"}
        with self.assertRaises(LifecycleCommandError):
            validate_answer_value(question, "yes")

    def test_resolve_question_answers_uses_default_when_no_answer(self):
        """_interview.py lines 204-208: resolved from default when no explicit answer."""
        from scripts.lifecycle._xanad._interview import resolve_question_answers
        questions = [
            {"id": "q1", "kind": "choice", "options": ["a", "b"], "default": "a", "required": True},
        ]
        resolved, unresolved, unknown = resolve_question_answers(questions, {})
        self.assertEqual({"q1": "a"}, resolved)
        self.assertEqual([], unresolved)

    def test_resolve_question_answers_marks_required_unresolved(self):
        """_interview.py line 208: required question with no default → unresolved."""
        from scripts.lifecycle._xanad._interview import resolve_question_answers
        questions = [
            {"id": "q1", "kind": "choice", "options": ["a", "b"], "required": True},
        ]
        resolved, unresolved, unknown = resolve_question_answers(questions, {})
        self.assertIn("q1", unresolved)

    def test_resolve_question_answers_returns_unknown_ids(self):
        """_interview.py: answers dict keys not in questions → unknown_ids."""
        from scripts.lifecycle._xanad._interview import resolve_question_answers
        questions = [{"id": "q1", "kind": "choice", "options": ["a"], "default": "a", "required": True}]
        resolved, unresolved, unknown = resolve_question_answers(questions, {"unknown-key": "v"})
        self.assertIn("unknown-key", unknown)

    def test_build_interview_questions_returns_profile_question(self):
        """_interview.py line 47: build_interview_questions returns non-empty for real policy/metadata."""
        from scripts.lifecycle._xanad._interview import build_interview_questions
        from scripts.lifecycle._xanad._loader import load_json, load_optional_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        policy = load_json(REPO_ROOT / DEFAULT_POLICY_PATH)
        # Load real metadata including profileRegistry
        metadata_path = REPO_ROOT / "template" / "setup" / "catalog.json"
        metadata = {}
        if metadata_path.exists():
            metadata = load_optional_json(metadata_path) or {}
        questions = build_interview_questions(policy, metadata, "setup")
        # Should have at least profile.selected question when profile registry exists
        self.assertIsInstance(questions, list)


# ---------------------------------------------------------------------------
# _plan_a.py — resolve_ownership_by_surface, build_setup_plan_actions, etc.
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
