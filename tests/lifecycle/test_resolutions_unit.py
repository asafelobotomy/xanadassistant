"""Unit tests for _resolutions.py — load, validate, apply, and delete-action building."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class LoadResolutionsTests(unittest.TestCase):

    def _load(self, path):
        from scripts.lifecycle._xanad._resolutions import load_resolutions
        return load_resolutions(path)

    def test_returns_empty_dict_for_none(self):
        self.assertEqual({}, self._load(None))

    def test_returns_empty_dict_for_missing_file(self):
        self.assertEqual({}, self._load("/nonexistent/path/resolutions.json"))

    def test_loads_valid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "resolutions.json"
            p.write_text(json.dumps({".github/agents/a.md": "keep"}), encoding="utf-8")
            result = self._load(str(p))
        self.assertEqual({".github/agents/a.md": "keep"}, result)

    def test_exits_on_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "resolutions.json"
            p.write_text("not json", encoding="utf-8")
            with self.assertRaises(SystemExit):
                self._load(str(p))

    def test_exits_on_non_object_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "resolutions.json"
            p.write_text(json.dumps(["keep"]), encoding="utf-8")
            with self.assertRaises(SystemExit):
                self._load(str(p))


class ValidateResolutionsTests(unittest.TestCase):

    def _validate(self, resolutions, existing_files):
        from scripts.lifecycle._xanad._resolutions import validate_resolutions
        return validate_resolutions(resolutions, existing_files)

    def _make_existing(self, path, file_type="collision", available=None):
        return {
            "path": path,
            "type": file_type,
            "availableDecisions": available or ["keep", "replace"],
        }

    def test_valid_decision_is_kept(self):
        existing = [self._make_existing(".github/agents/a.md")]
        valid, warnings = self._validate({".github/agents/a.md": "keep"}, existing)
        self.assertEqual({".github/agents/a.md": "keep"}, valid)
        self.assertEqual([], warnings)

    def test_unknown_path_produces_warning(self):
        valid, warnings = self._validate({".github/agents/unknown.md": "keep"}, [])
        self.assertEqual({}, valid)
        self.assertEqual(1, len(warnings))
        self.assertEqual("resolution_unknown_path", warnings[0]["code"])

    def test_invalid_decision_produces_warning(self):
        existing = [self._make_existing(".github/agents/a.md", available=["keep", "replace"])]
        valid, warnings = self._validate({".github/agents/a.md": "merge"}, existing)
        self.assertEqual({}, valid)
        self.assertEqual(1, len(warnings))
        self.assertEqual("resolution_invalid_decision", warnings[0]["code"])


class ApplyResolutionsToPlanActionsTests(unittest.TestCase):

    def _apply(self, actions, skipped, resolutions):
        from scripts.lifecycle._xanad._resolutions import apply_resolutions_to_plan_actions
        return apply_resolutions_to_plan_actions(actions, skipped, resolutions)

    def _action(self, target, action_type="replace"):
        return {"id": f"test:{target}", "target": target, "action": action_type, "ownershipMode": "local", "tokens": [], "tokenValues": {}}

    def test_keep_decision_moves_action_to_skipped(self):
        action = self._action(".github/agents/a.md")
        new_actions, new_skipped = self._apply([action], [], {".github/agents/a.md": "keep"})
        self.assertEqual([], new_actions)
        self.assertEqual(1, len(new_skipped))
        self.assertEqual("consumer-keep", new_skipped[0]["reason"])

    def test_replace_decision_keeps_action_unchanged(self):
        action = self._action(".github/agents/a.md")
        new_actions, new_skipped = self._apply([action], [], {".github/agents/a.md": "replace"})
        self.assertEqual([action], new_actions)
        self.assertEqual([], new_skipped)

    def test_merge_decision_changes_action_field(self):
        action = self._action(".github/prompts/p.md")
        new_actions, new_skipped = self._apply([action], [], {".github/prompts/p.md": "merge"})
        self.assertEqual(1, len(new_actions))
        self.assertEqual("merge", new_actions[0]["action"])

    def test_update_decision_keeps_action_unchanged(self):
        action = self._action(".github/agents/a.md", action_type="replace")
        new_actions, new_skipped = self._apply([action], [], {".github/agents/a.md": "update"})
        self.assertEqual([action], new_actions)
        self.assertEqual([], new_skipped)

    def test_no_resolutions_returns_original_lists(self):
        action = self._action(".github/agents/a.md")
        new_actions, new_skipped = self._apply([action], [], {})
        self.assertEqual([action], new_actions)
        self.assertEqual([], new_skipped)

    def test_existing_skipped_actions_are_preserved(self):
        action = self._action(".github/agents/a.md")
        pre_skipped = [self._action(".github/agents/b.md")]
        new_actions, new_skipped = self._apply([action], pre_skipped, {".github/agents/a.md": "keep"})
        self.assertEqual(2, len(new_skipped))


class BuildDeleteActionsTests(unittest.TestCase):

    def _build(self, workspace, resolutions, existing_files):
        from scripts.lifecycle._xanad._resolutions import build_delete_actions
        return build_delete_actions(workspace, resolutions, existing_files)

    def test_remove_decision_creates_delete_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ".github/agents/old.md"
            (ws / ".github" / "agents").mkdir(parents=True)
            (ws / target).write_text("old", encoding="utf-8")
            existing = [{"path": target, "type": "unmanaged", "surface": "agents", "availableDecisions": ["keep", "remove"]}]
            actions = self._build(ws, {target: "remove"}, existing)
        self.assertEqual(1, len(actions))
        a = actions[0]
        self.assertEqual("delete", a["action"])
        self.assertEqual(target, a["target"])
        self.assertEqual(f"delete:{target}", a["id"])

    def test_missing_file_is_skipped_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ".github/agents/gone.md"
            existing = [{"path": target, "type": "unmanaged", "surface": "agents", "availableDecisions": ["keep", "remove"]}]
            actions = self._build(ws, {target: "remove"}, existing)
        self.assertEqual([], actions)

    def test_keep_decision_does_not_create_delete_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ".github/agents/kept.md"
            (ws / ".github" / "agents").mkdir(parents=True)
            (ws / target).write_text("keep", encoding="utf-8")
            existing = [{"path": target, "type": "unmanaged", "surface": "agents", "availableDecisions": ["keep", "remove"]}]
            actions = self._build(ws, {target: "keep"}, existing)
        self.assertEqual([], actions)


if __name__ == "__main__":
    unittest.main()
