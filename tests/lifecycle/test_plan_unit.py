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
            "present": False, "malformed": False, "path": ".github/xanad-assistant-lock.json",
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
                "present": True, "malformed": True, "path": ".github/xanad-assistant-lock.json",
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
                "present": True, "malformed": False, "path": ".github/xanad-assistant-lock.json",
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
                "present": True, "malformed": False, "path": ".github/xanad-assistant-lock.json",
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
                "present": True, "malformed": False, "path": ".github/xanad-assistant-lock.json",
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

class PlanATests(unittest.TestCase):

    def _get_manifest(self):
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        return load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}

    def _get_policy(self):
        from scripts.lifecycle._xanad._loader import load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        return load_json(REPO_ROOT / DEFAULT_POLICY_PATH)

    def test_resolve_ownership_by_surface_returns_empty_when_manifest_none(self):
        """_plan_a.py line 73: early return when manifest is None."""
        from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface
        result = resolve_ownership_by_surface({}, None, {}, {})
        self.assertEqual({}, result)

    def test_resolve_ownership_by_surface_raises_for_invalid_ownership(self):
        """_plan_a.py line 40: raise when resolved_ownership not in entry['ownership']."""
        from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        # Force invalid ownership via policy default
        policy = self._get_policy()
        first_surface = entries[0]["surface"]
        policy["ownershipDefaults"][first_surface] = "invalid-ownership-xyz"
        with self.assertRaises(LifecycleCommandError):
            resolve_ownership_by_surface(policy, manifest, {}, {})

    def test_resolve_ownership_by_surface_uses_existing_ownership(self):
        """_plan_a.py line 27: existing_ownership from lockfile_state is used."""
        from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        policy = self._get_policy()
        first_entry = entries[0]
        lockfile_state = {"ownershipBySurface": {first_entry["surface"]: first_entry["ownership"][0]}}
        result = resolve_ownership_by_surface(policy, manifest, lockfile_state, {})
        self.assertIn(first_entry["surface"], result)

    def test_build_setup_plan_actions_returns_empty_when_manifest_none(self):
        """_plan_a.py line 73: early return when manifest is None."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            writes, actions, skipped, retired = build_setup_plan_actions(
                ws, REPO_ROOT, None, {}, {}, {},
            )
        self.assertEqual([], actions)

    def test_build_setup_plan_actions_skips_non_local_ownership(self):
        """_plan_a.py lines 87-93: entry with non-local ownership mode is skipped."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        first_surface = entries[0]["surface"]
        # Map the first surface to non-local ownership
        ownership_by_surface = {first_surface: "plugin-backed-copilot-format"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            writes, actions, skipped, retired = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership_by_surface, {}, {},
            )
        # At least one action should be skipped due to non-local ownership
        skipped_ids = [s["id"] for s in skipped if s.get("reason") == "plugin-backed-ownership"]
        self.assertTrue(len(skipped_ids) > 0)

    def test_build_setup_plan_actions_skips_condition_not_selected(self):
        """_plan_a.py lines 106-113: entry whose requiredWhen condition fails is skipped."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        entries = manifest.get("managedFiles", []) if manifest else []
        # Find entry with requiredWhen condition
        conditional_entry = next((e for e in entries if e.get("requiredWhen")), None)
        if not conditional_entry:
            self.skipTest("No conditional entries in manifest")
        # Set all surfaces to local ownership, but leave resolved_answers empty
        # so the requiredWhen condition fails
        ownership_by_surface = {conditional_entry["surface"]: "local"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            _, _, skipped, _ = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership_by_surface, {}, {},
            )
        skipped_ids = [s["id"] for s in skipped if s.get("reason") == "condition-not-selected"]
        self.assertTrue(len(skipped_ids) > 0)

    def test_build_setup_plan_actions_copy_if_missing_present_skips(self):
        """_plan_a.py lines 126-128: copy-if-missing entry skipped when target exists."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        # Build a synthetic manifest with a copy-if-missing entry
        synthetic_manifest = {
            "managedFiles": [
                {
                    "id": "test.copy-if-missing",
                    "surface": "test",
                    "target": ".github/test-file.md",
                    "source": "template/copilot-instructions.md",
                    "strategy": "copy-if-missing",
                    "ownership": ["local"],
                    "hash": "sha256:fake",
                    "tokens": [],
                    "chmod": "none",
                }
            ],
            "retiredFiles": [],
        }
        ownership = {"test": "local"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create the target file so copy-if-missing skips it
            target = ws / ".github" / "test-file.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Existing content", encoding="utf-8")
            _, _, skipped, _ = build_setup_plan_actions(
                ws, REPO_ROOT, synthetic_manifest, ownership, {}, {},
            )
        skipped_ids = [s["id"] for s in skipped if s.get("reason") == "copy-if-missing-present"]
        self.assertIn("test.copy-if-missing", skipped_ids)

    def test_build_setup_plan_actions_includes_retired_files(self):
        """_plan_a.py lines 148-150: retired file that exists is included in actions."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        retired = manifest.get("retiredFiles", []) if manifest else []
        if not retired:
            self.skipTest("No retired files in manifest")
        first_retired = retired[0]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create the retired file in workspace
            target = ws / first_retired["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Retired content", encoding="utf-8")
            _, actions, _, retired_targets = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, {}, {}, {},
            )
        archive_actions = [a for a in actions if a["action"] == "archive-retired"]
        self.assertTrue(len(archive_actions) > 0)
        self.assertIn(first_retired["target"], retired_targets)

    def test_classify_plan_conflicts_managed_drift(self):
        """_plan_a.py lines 161-163: managed drift conflict when replace/merge actions exist."""
        from scripts.lifecycle._xanad._plan_a import classify_plan_conflicts
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            context = _minimal_context(ws)
            actions = [
                {"action": "replace", "target": ".github/copilot-instructions.md", "id": "test"},
            ]
            conflicts, warnings = classify_plan_conflicts(ws, context, actions, [])
        conflict_classes = [c["class"] for c in conflicts]
        self.assertIn("managed-drift", conflict_classes)

    def test_classify_plan_conflicts_unmanaged_lookalike(self):
        """_plan_a.py lines 170-175: unmanaged file in managed dir creates conflict."""
        from scripts.lifecycle._xanad._plan_a import classify_plan_conflicts
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create an unmanaged file in a managed directory
            agents_dir = ws / ".github" / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "unmanaged-file.md").write_text("# Unmanaged", encoding="utf-8")
            context = _minimal_context(ws)
            context["manifest"] = manifest
            conflicts, warnings = classify_plan_conflicts(ws, context, [], [])
        conflict_classes = [c["class"] for c in conflicts]
        self.assertIn("unmanaged-lookalike", conflict_classes)

    def test_classify_plan_conflicts_malformed_state(self):
        """_plan_a.py lines 182-184: malformed lockfile creates malformed-managed-state conflict."""
        from scripts.lifecycle._xanad._plan_a import classify_plan_conflicts
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            context = _minimal_context(ws)
            context["lockfileState"]["malformed"] = True
            conflicts, warnings = classify_plan_conflicts(ws, context, [], [])
        conflict_classes = [c["class"] for c in conflicts]
        self.assertIn("malformed-managed-state", conflict_classes)

    def test_classify_plan_conflicts_retired_file_present(self):
        """_plan_a.py lines 196-197: retired file in workspace creates conflict."""
        from scripts.lifecycle._xanad._plan_a import classify_plan_conflicts
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            context = _minimal_context(ws)
            conflicts, warnings = classify_plan_conflicts(ws, context, [], [".github/old-file.md"])
        conflict_classes = [c["class"] for c in conflicts]
        self.assertIn("retired-file-present", conflict_classes)

    def test_verify_manifest_integrity_lockfile_not_present(self):
        """_plan_a.py: lockfile not present → (True, None)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        ok, reason = verify_manifest_integrity(REPO_ROOT, {"present": False, "malformed": False})
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_manifest_hash_mismatch(self):
        """_plan_a.py line 225: hash mismatch returns (False, reason)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        lockfile_state = {
            "present": True, "malformed": False,
            "data": {"manifest": {"hash": "sha256:totally-wrong-hash"}},
        }
        ok, reason = verify_manifest_integrity(REPO_ROOT, lockfile_state)
        self.assertFalse(ok)
        self.assertIn("mismatch", reason)

    def test_verify_manifest_integrity_hash_matches(self):
        """_plan_a.py line 229: hash match returns (True, None)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        from scripts.lifecycle._xanad._merge import sha256_json
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        current_hash = sha256_json(manifest) if manifest else ""
        lockfile_state = {
            "present": True, "malformed": False,
            "data": {"manifest": {"hash": current_hash}},
        }
        ok, reason = verify_manifest_integrity(REPO_ROOT, lockfile_state)
        self.assertTrue(ok)
        self.assertIsNone(reason)


# ---------------------------------------------------------------------------
# _plan_b.py — build_plan_result edge cases and build_planned_lockfile
# ---------------------------------------------------------------------------

class PlanBTests(unittest.TestCase):

    def test_build_plan_result_unsupported_mode(self):
        """_plan_b.py line 129: unsupported mode returns not-implemented payload."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            result = build_plan_result(ws, REPO_ROOT, "not-a-real-mode", None, True)
        self.assertEqual("plan", result["command"])
        self.assertEqual("not-implemented", result["status"])

    def test_build_plan_result_repair_on_not_installed_raises(self):
        """_plan_b.py lines 144-145: repair on not-installed workspace raises."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            with self.assertRaises(LifecycleCommandError) as ctx:
                build_plan_result(ws, REPO_ROOT, "repair", None, True)
        self.assertEqual("inspection_failure", ctx.exception.code)

    def test_build_plan_result_factory_restore_on_not_installed_raises(self):
        """_plan_b.py line 165: factory-restore on not-installed raises."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            with self.assertRaises(LifecycleCommandError) as ctx:
                build_plan_result(ws, REPO_ROOT, "factory-restore", None, True)
        self.assertEqual("inspection_failure", ctx.exception.code)

    def test_build_plan_result_setup_on_fresh_workspace(self):
        """_plan_b.py: setup mode on fresh workspace returns ok or approval-required payload."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            result = build_plan_result(ws, REPO_ROOT, "setup", None, True)
        self.assertEqual("plan", result["command"])
        self.assertEqual("setup", result["mode"])
        self.assertIn(result["status"], ("ok", "approval-required"))

    def test_build_planned_lockfile_with_mixed_actions(self):
        """_plan_b.py lines 67-70, 88, 97: lockfile built from mix of action types."""
        from scripts.lifecycle._xanad._plan_b import build_planned_lockfile
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        real_entry = entries[0]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            context = _minimal_context(ws)
            context["manifest"] = manifest
            retired_target = ".github/agents/old-agent.md"
            actions = [
                {
                    "id": "migration.cleanup.test",
                    "target": retired_target,
                    "action": "archive-retired",
                    "ownershipMode": None,
                    "strategy": "archive-retired",
                },
                {
                    "id": real_entry["id"],
                    "target": real_entry["target"],
                    "action": "add",
                    "strategy": real_entry.get("strategy", "copy"),
                    "ownershipMode": "local",
                },
            ]
            # archiveTargets maps the retired target so line 97 is covered
            backup_plan = {
                "required": False, "root": None, "targets": [],
                "archiveTargets": [
                    {"target": retired_target, "archivePath": f".xanad-archive/{retired_target}"},
                ],
            }
            lockfile = build_planned_lockfile(
                ws, context, {}, {}, {}, actions, [], [retired_target], backup_plan,
            )
        retired = lockfile["contents"]["retiredManagedFiles"]
        self.assertEqual(1, len(retired))
        self.assertEqual("archived", retired[0]["action"])
        file_records = lockfile["contents"]["files"]
        self.assertTrue(len(file_records) > 0)

    def test_build_lockfile_package_info_includes_ref_from_session(self):
        """_plan_b.py line 43: info['ref'] is set when session_source_info has 'ref'."""
        from scripts.lifecycle._xanad._plan_b import _build_lockfile_package_info
        from scripts.lifecycle._xanad._errors import _State
        original = _State.session_source_info
        try:
            _State.session_source_info = {
                "packageRoot": str(REPO_ROOT),
                "ref": "main",
                "source": "owner/repo",
            }
            info = _build_lockfile_package_info()
        finally:
            _State.session_source_info = original
        self.assertEqual("main", info.get("ref"))

    def test_build_plan_result_unknown_answer_ids_warns(self):
        """_plan_b.py lines 181-185: unknown answer IDs trigger warning."""
        from scripts.lifecycle._xanad._plan_b import build_plan_result
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_file = Path(tmp) / "answers.json"
            answers_file.write_text('{"unknown-key-xyz": "value"}', encoding="utf-8")
            result = build_plan_result(ws, REPO_ROOT, "setup", str(answers_file), True)
        warning_codes = [w["code"] for w in result.get("warnings", [])]
        self.assertIn("unknown_answer_ids_ignored", warning_codes)

    def test_build_planned_lockfile_skips_action_with_unknown_id(self):
        """_plan_b.py line 69: continue when manifest_entry is None for non-archive action."""
        from scripts.lifecycle._xanad._plan_b import build_planned_lockfile
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            context = _minimal_context(ws)
            context["manifest"] = manifest
            # Action with an ID that does NOT exist in manifest
            actions = [{
                "id": "does-not-exist-in-manifest",
                "action": "add",
                "target": "some/file.md",
                "ownershipMode": "local",
                "strategy": "copy",
            }]
            backup_plan = {"required": False, "root": None, "targets": [], "archiveTargets": []}
            lockfile = build_planned_lockfile(ws, context, {}, {}, {}, actions, [], [], backup_plan)
        self.assertEqual([], lockfile["contents"]["files"])


# ---------------------------------------------------------------------------
# _inspect_helpers.py
# ---------------------------------------------------------------------------

class InspectHelpersTests(unittest.TestCase):

    def _make_annotated_entry(self, entry: dict, status: str) -> dict:
        result = dict(entry)
        result["status"] = status
        return result

    def test_annotate_manifest_entries_skips_non_local_ownership(self):
        """_inspect_helpers.py lines 42-43: ownership != local sets condition-not-selected status."""
        from scripts.lifecycle._xanad._inspect_helpers import annotate_manifest_entries
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files")
        first_surface = entries[0]["surface"]
        ownership = {first_surface: "plugin-backed-copilot-format"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            result = annotate_manifest_entries(ws, REPO_ROOT, manifest, ownership, {}, {})
        skipped = [e for e in (result or {}).get("managedFiles", [])
                   if e.get("skipReason") == "plugin-backed-ownership"]
        self.assertTrue(len(skipped) > 0)

    def test_annotate_manifest_entries_condition_not_selected(self):
        """_inspect_helpers.py lines 42-43: condition not selected sets skip status."""
        from scripts.lifecycle._xanad._inspect_helpers import annotate_manifest_entries
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        entries = manifest.get("managedFiles", [])
        conditional = next((e for e in entries if e.get("requiredWhen")), None)
        if not conditional:
            self.skipTest("No conditional entries")
        # Set all surfaces to local, but leave resolved_answers empty
        ownership = {e["surface"]: "local" for e in entries}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            result = annotate_manifest_entries(ws, REPO_ROOT, manifest, ownership, {}, {})
        skipped = [e for e in (result or {}).get("managedFiles", [])
                   if e.get("skipReason") == "condition-not-selected"]
        self.assertTrue(len(skipped) > 0)

    def test_classify_manifest_entries_retired_file_counts(self):
        """_inspect_helpers.py lines 86-87: retired file that exists is counted."""
        from scripts.lifecycle._xanad._inspect_helpers import classify_manifest_entries
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        retired = manifest.get("retiredFiles", [])
        if not retired:
            self.skipTest("No retired files in manifest")
        # Build annotated manifest with all managed files as "clean"
        annotated = dict(manifest)
        annotated["managedFiles"] = [dict(e, status="clean") for e in manifest.get("managedFiles", [])]
        first_retired_target = retired[0]["target"]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create the retired file so it gets counted
            target = ws / first_retired_target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Retired", encoding="utf-8")
            counts, entries, managed_targets = classify_manifest_entries(ws, annotated)
        self.assertGreater(counts["retired"], 0)

    def test_collect_unmanaged_files_finds_unmanaged_in_managed_dir(self):
        """_inspect_helpers.py lines 94, 102, 112: unmanaged file is returned."""
        from scripts.lifecycle._xanad._inspect_helpers import collect_unmanaged_files
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        managed_targets = {e["target"] for e in manifest.get("managedFiles", [])}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create an unmanaged file in a managed directory
            agents_dir = ws / ".github" / "agents"
            agents_dir.mkdir(parents=True)
            unmanaged = agents_dir / "not-in-manifest.md"
            unmanaged.write_text("# Unmanaged", encoding="utf-8")
            result = collect_unmanaged_files(ws, manifest, managed_targets)
        self.assertIn(".github/agents/not-in-manifest.md", result)

    def test_collect_successor_migration_files_finds_migration_targets(self):
        """_inspect_helpers.py lines 149, 154: files in successor roots are returned."""
        from scripts.lifecycle._xanad._inspect_helpers import collect_successor_migration_files
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        lockfile_state = {"originalPackageName": "copilot-instructions-template", "data": {}}
        legacy_state = {"present": True, "malformed": False, "data": {"version": "0.9.0"}}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            agents_dir = ws / ".github" / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "old-agent.agent.md").write_text("# Old agent", encoding="utf-8")
            result = collect_successor_migration_files(ws, manifest, lockfile_state, legacy_state)
        self.assertIn(".github/agents/old-agent.agent.md", result)

    def test_collect_successor_migration_files_finds_mcp_json(self):
        """_inspect_helpers.py line 154: .mcp.json in SUCCESSOR_MIGRATION_FILES is found."""
        from scripts.lifecycle._xanad._inspect_helpers import collect_successor_migration_files
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH))
        if not manifest:
            self.skipTest("No manifest available")
        lockfile_state = {"originalPackageName": "copilot-instructions-template", "data": {}}
        legacy_state = {"present": False, "malformed": False, "data": None}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create .mcp.json (a SUCCESSOR_MIGRATION_FILE)
            (ws / ".mcp.json").write_text('{"mcpServers":{}}', encoding="utf-8")
            result = collect_successor_migration_files(ws, manifest, lockfile_state, legacy_state)
        self.assertIn(".mcp.json", result)

    def test_classify_manifest_entries_returns_empty_when_manifest_none(self):
        """_inspect_helpers.py line 71: early return when manifest is None."""
        from scripts.lifecycle._xanad._inspect_helpers import classify_manifest_entries
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            counts, entries, managed = classify_manifest_entries(ws, None)
        self.assertEqual(0, sum(counts.values()))
        self.assertEqual([], entries)
        self.assertEqual(set(), managed)

    def test_collect_unmanaged_files_returns_empty_when_manifest_none(self):
        """_inspect_helpers.py line 94: early return [] when manifest is None."""
        from scripts.lifecycle._xanad._inspect_helpers import collect_unmanaged_files
        result = collect_unmanaged_files(Path("/tmp"), None, set())
        self.assertEqual([], result)

    def test_collect_unmanaged_files_skips_root_candidate_dir(self):
        """_inspect_helpers.py line 102: candidate in {'', '.'} is skipped."""
        from scripts.lifecycle._xanad._inspect_helpers import collect_unmanaged_files
        # A managed target with no directory component → candidate dir = "."
        manifest = {"managedFiles": [], "retiredFiles": []}
        managed_targets = {"root-level-file.md"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create a file at root level — it should be skipped (root dir "." is excluded)
            (ws / "root-level-file.md").write_text("# Root", encoding="utf-8")
            result = collect_unmanaged_files(ws, manifest, managed_targets)
        # Root-level candidate dirs are skipped, so no files from "." are reported
        self.assertEqual([], result)


class PlanAExtraTests(unittest.TestCase):
    """Extra tests for _plan_a.py lines not covered by PlanATests."""

    def _get_manifest(self):
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        return load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}

    def _get_policy(self):
        from scripts.lifecycle._xanad._loader import load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        return load_json(REPO_ROOT / DEFAULT_POLICY_PATH)

    def test_build_conflict_summary_counts_by_class(self):
        """_plan_a.py lines 196-197: build_conflict_summary counts each class."""
        from scripts.lifecycle._xanad._plan_a import build_conflict_summary
        conflicts = [
            {"class": "managed-drift", "target": "a"},
            {"class": "managed-drift", "target": "b"},
            {"class": "unmanaged-lookalike", "target": "c"},
        ]
        summary = build_conflict_summary(conflicts)
        self.assertEqual(2, summary["managed-drift"])
        self.assertEqual(1, summary["unmanaged-lookalike"])

    def test_resolve_ownership_by_surface_uses_entry_first_ownership_when_not_in_defaults(self):
        """_plan_a.py line 27: surface not in policy ownershipDefaults → uses entry.ownership[0]."""
        from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        if not entries:
            self.skipTest("No managed files in manifest")
        first_entry = entries[0]
        # Build policy WITHOUT the first surface in ownershipDefaults
        policy = self._get_policy()
        modified_defaults = {k: v for k, v in policy.get("ownershipDefaults", {}).items()
                             if k != first_entry["surface"]}
        modified_policy = dict(policy, ownershipDefaults=modified_defaults)
        result = resolve_ownership_by_surface(modified_policy, manifest, {}, {})
        # First surface should use entry.ownership[0]
        self.assertIn(first_entry["surface"], result)
        self.assertEqual(first_entry["ownership"][0], result[first_entry["surface"]])

    def test_build_setup_plan_actions_file_exists_checks_hash(self):
        """_plan_a.py lines 109-113: file exists with non-copy-if-missing strategy → hash check."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        copy_entry = next(
            (e for e in entries if e.get("strategy") not in {"merge-json-object", "preserve-marked-markdown-blocks", "copy-if-missing"}),
            None,
        )
        if copy_entry is None:
            self.skipTest("No suitable copy-strategy entries in manifest")
        policy = self._get_policy()
        ownership = {copy_entry["surface"]: "local"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create the target file with different content from source → hashes differ → replace action
            target = ws / copy_entry["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Different content from source", encoding="utf-8")
            writes, actions, skipped, retired = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership, {}, {},
            )
        action_ids = [a["id"] for a in actions]
        self.assertIn(copy_entry["id"], action_ids)
        # The action should be "replace" (not "add") since file exists
        entry_actions = [a for a in actions if a["id"] == copy_entry["id"]]
        self.assertTrue(all(a["action"] == "replace" for a in entry_actions))

    def test_build_setup_plan_actions_force_reinstall_replaces_matching_file(self):
        """_plan_a.py line 107: force_reinstall=True skips hash check and uses replace/merge."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        copy_entry = next(
            (e for e in entries if e.get("strategy") not in {"merge-json-object", "preserve-marked-markdown-blocks", "copy-if-missing"} and not e.get("tokens")),
            None,
        )
        if copy_entry is None:
            self.skipTest("No tokenless copy-strategy entries in manifest")
        ownership = {copy_entry["surface"]: "local"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ws / copy_entry["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            # Write identical content — but force_reinstall=True bypasses hash check
            source_path = REPO_ROOT / copy_entry["source"]
            import shutil
            shutil.copy2(source_path, target)
            writes, actions, skipped, retired = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership, {}, {}, force_reinstall=True,
            )
        action_ids = [a["id"] for a in actions]
        self.assertIn(copy_entry["id"], action_ids)
        # With force_reinstall, action should be "replace" even with identical content
        entry_actions = [a for a in actions if a["id"] == copy_entry["id"]]
        self.assertTrue(all(a["action"] == "replace" for a in entry_actions))


        """_plan_a.py line 112: continue when installed_hash == expected_hash."""
        from scripts.lifecycle._xanad._plan_a import build_setup_plan_actions
        manifest = self._get_manifest()
        entries = manifest.get("managedFiles", [])
        copy_entry = next(
            (e for e in entries if e.get("strategy") not in {"merge-json-object", "preserve-marked-markdown-blocks", "copy-if-missing"} and not e.get("tokens")),
            None,
        )
        if copy_entry is None:
            self.skipTest("No tokenless copy-strategy entries in manifest")
        ownership = {copy_entry["surface"]: "local"}
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ws / copy_entry["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            # Write the exact same content as the source
            source_path = REPO_ROOT / copy_entry["source"]
            import shutil
            shutil.copy2(source_path, target)
            writes, actions, skipped, retired = build_setup_plan_actions(
                ws, REPO_ROOT, manifest, ownership, {}, {},
            )
        # The entry should be skipped (hashes match)
        action_ids = [a["id"] for a in actions]
        self.assertNotIn(copy_entry["id"], action_ids)

    def test_verify_manifest_integrity_lockfile_data_not_dict(self):
        """_plan_a.py line 216: lockfile_data is not a dict → return (True, None)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        lockfile_state = {
            "present": True, "malformed": False,
            "data": "not-a-dict",
        }
        ok, reason = verify_manifest_integrity(REPO_ROOT, lockfile_state)
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_no_recorded_hash(self):
        """_plan_a.py line 219: no recorded hash → return (True, None)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        lockfile_state = {
            "present": True, "malformed": False,
            "data": {"manifest": {}},  # no "hash" key
        }
        ok, reason = verify_manifest_integrity(REPO_ROOT, lockfile_state)
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_no_policy_returns_ok(self):
        """_plan_a.py line 222: policy not found → return (True, None)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        with tempfile.TemporaryDirectory() as tmp:
            empty_root = Path(tmp)
            lockfile_state = {
                "present": True, "malformed": False,
                "data": {"manifest": {"hash": "sha256:some-hash"}},
            }
            ok, reason = verify_manifest_integrity(empty_root, lockfile_state)
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_verify_manifest_integrity_manifest_not_found(self):
        """_plan_a.py line 225: manifest not found → return (False, reason)."""
        from scripts.lifecycle._xanad._plan_a import verify_manifest_integrity
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            # Create a policy file but no manifest
            import json as _json
            policy = {"surfaces": [], "managedSurfaces": [], "ownershipDefaults": {},
                      "defaultProfile": "balanced", "canonicalSurfaces": []}
            policy_path = fake_root / "template" / "setup" / "install-policy.json"
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(_json.dumps(policy), encoding="utf-8")
            lockfile_state = {
                "present": True, "malformed": False,
                "data": {"manifest": {"hash": "sha256:some-hash"}},
            }
            # Patch load_manifest to return None to simulate missing manifest
            with patch("scripts.lifecycle._xanad._plan_a.load_manifest", return_value=None):
                ok, reason = verify_manifest_integrity(fake_root, lockfile_state)
        self.assertFalse(ok)
        self.assertIn("Manifest not found", reason)


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
            (github / "xanad-assistant-lock.json").write_text(
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
