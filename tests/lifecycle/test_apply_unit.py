"""Unit tests for _apply.py and _execute_apply.py covering uncovered branches.

These tests call the functions directly (no subprocess) to capture coverage.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# _apply.py
# ---------------------------------------------------------------------------

class MaterializeApplyTimestampTests(unittest.TestCase):
    def test_returns_none_when_value_is_none(self):
        """_apply.py line 30: return None when value is None."""
        from scripts.lifecycle._xanad._apply import materialize_apply_timestamp
        result = materialize_apply_timestamp(None, "2026-01-01T00-00-00Z")
        self.assertIsNone(result)

    def test_replaces_apply_timestamp_placeholder(self):
        from scripts.lifecycle._xanad._apply import materialize_apply_timestamp
        result = materialize_apply_timestamp(".backup/<apply-timestamp>", "2026-01-01T00-00-00Z")
        self.assertEqual(".backup/2026-01-01T00-00-00Z", result)


class RenderEntryBytesTests(unittest.TestCase):
    def test_raises_lifecycle_command_error_when_expected_bytes_is_none(self):
        """_apply.py line 37: raise LifecycleCommandError when result is None."""
        from scripts.lifecycle._xanad._apply import render_entry_bytes
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            # merge-json-object with non-dict source → expected_entry_bytes returns None
            (pkg_root / "source.json").write_text("[1, 2, 3]", encoding="utf-8")
            entry = {
                "id": "test.entry",
                "source": "source.json",
                "strategy": "merge-json-object",
                "tokens": [],
                "hash": "sha256:fake",
            }
            with self.assertRaises(LifecycleCommandError):
                render_entry_bytes(pkg_root, entry, {})


class MergeJsonObjectFileTests(unittest.TestCase):
    def test_merges_when_target_exists_and_both_are_dicts(self):
        """_apply.py lines 47-72: merge when target exists with valid JSON dict."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "source.json").write_text('{"a": 1}', encoding="utf-8")
            target_path = workspace / ".github" / "mcp.json"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text('{"b": 2}', encoding="utf-8")
            entry = {"id": "test", "source": "source.json"}
            merge_json_object_file(target_path, pkg_root, entry)
            merged = json.loads(target_path.read_text(encoding="utf-8"))
        self.assertIn("a", merged)
        self.assertIn("b", merged)

    def test_raises_when_target_json_is_invalid(self):
        """_apply.py lines 51-56: raise when target JSON cannot be decoded."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "source.json").write_text('{"a": 1}', encoding="utf-8")
            target_path = workspace / "target.json"
            target_path.write_text("{invalid json", encoding="utf-8")
            entry = {"id": "test", "source": "source.json"}
            with self.assertRaises(LifecycleCommandError):
                merge_json_object_file(target_path, pkg_root, entry)

    def test_raises_when_target_is_not_dict(self):
        """_apply.py lines 57-62: raise when target JSON is valid but not a dict."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "source.json").write_text('{"a": 1}', encoding="utf-8")
            target_path = workspace / "target.json"
            target_path.write_text('[1, 2, 3]', encoding="utf-8")
            entry = {"id": "test", "source": "source.json"}
            with self.assertRaises(LifecycleCommandError):
                merge_json_object_file(target_path, pkg_root, entry)

    def test_writes_source_when_target_does_not_exist(self):
        """_apply.py lines 63-71: write source when target does not exist."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "source.json").write_text('{"key": "value"}', encoding="utf-8")
            target_path = workspace / "target.json"
            entry = {"id": "test", "source": "source.json"}
            merge_json_object_file(target_path, pkg_root, entry)
            result = json.loads(target_path.read_text(encoding="utf-8"))
        self.assertEqual({"key": "value"}, result)

    def test_raises_when_source_is_not_dict_and_target_missing(self):
        """_apply.py lines 67-71: raise when source JSON is not a dict."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        from scripts.lifecycle._xanad._errors import LifecycleCommandError
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "source.json").write_text('[1, 2, 3]', encoding="utf-8")
            target_path = workspace / "target.json"
            entry = {"id": "test", "source": "source.json"}
            with self.assertRaises(LifecycleCommandError):
                merge_json_object_file(target_path, pkg_root, entry)


class MergeMarkdownFileTests(unittest.TestCase):
    def test_merges_when_target_exists(self):
        """_apply.py lines 78-86: merge markdown when target exists preserves user-added blocks."""
        from scripts.lifecycle._xanad._apply import merge_markdown_file
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "template.md").write_text("# Header\n", encoding="utf-8")
            target_path = workspace / "target.md"
            # user-added block in the existing target should be preserved
            target_path.write_text(
                "# Header\n\n<!-- user-added -->\nMY CUSTOM CONTENT\n<!-- /user-added -->\n",
                encoding="utf-8",
            )
            entry = {"id": "test", "source": "template.md"}
            merge_markdown_file(target_path, pkg_root, entry)
            merged = target_path.read_text(encoding="utf-8")
            self.assertIn("MY CUSTOM CONTENT", merged)

    def test_writes_source_when_target_does_not_exist(self):
        """_apply.py line 85: write rendered source when target does not exist."""
        from scripts.lifecycle._xanad._apply import merge_markdown_file
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            (pkg_root / "template.md").write_text("# Hello\n", encoding="utf-8")
            target_path = workspace / "output.md"
            entry = {"id": "test", "source": "template.md"}
            merge_markdown_file(target_path, pkg_root, entry)
            content = target_path.read_text(encoding="utf-8")
        self.assertEqual("# Hello\n", content)


class BuildCopilotVersionSummaryTests(unittest.TestCase):
    def test_uses_unknown_version_when_manifest_has_no_package_version(self):
        """_apply.py line 94: package_version = 'unknown' when manifest lacks packageVersion."""
        from scripts.lifecycle._xanad._apply import build_copilot_version_summary
        lockfile = {
            "profile": "balanced",
            "selectedPacks": [],
            "manifest": {"hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z"},
        }
        result = build_copilot_version_summary(lockfile, None)
        self.assertIn("Version: unknown", result)

    def test_uses_provided_version_from_manifest(self):
        from scripts.lifecycle._xanad._apply import build_copilot_version_summary
        lockfile = {
            "profile": "balanced",
            "selectedPacks": ["lean"],
            "manifest": {"hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z"},
        }
        manifest = {"packageVersion": "1.2.3"}
        result = build_copilot_version_summary(lockfile, manifest)
        self.assertIn("Version: 1.2.3", result)
        self.assertIn("lean", result)



class StripJsonCommentsTests(unittest.TestCase):
    def test_strips_single_line_comments(self) -> None:
        from scripts.lifecycle._xanad._apply import _strip_json_comments
        text = '{\n    // a comment\n    "key": "value"\n}'
        result = _strip_json_comments(text)
        self.assertEqual("value", json.loads(result)["key"])

    def test_strips_block_comments(self) -> None:
        from scripts.lifecycle._xanad._apply import _strip_json_comments
        text = '{ /* block */ "key": 1 }'
        result = _strip_json_comments(text)
        self.assertEqual(1, json.loads(result)["key"])

    def test_preserves_url_in_string_value(self) -> None:
        from scripts.lifecycle._xanad._apply import _strip_json_comments
        text = '{"url": "https://example.com/path"}'
        result = _strip_json_comments(text)
        self.assertEqual("https://example.com/path", json.loads(result)["url"])

    def test_strips_inline_comment_after_value(self) -> None:
        from scripts.lifecycle._xanad._apply import _strip_json_comments
        text = '{"key": "value" // trailing\n}'
        result = _strip_json_comments(text)
        self.assertEqual("value", json.loads(result)["key"])

    def test_passes_through_plain_json_unchanged(self) -> None:
        from scripts.lifecycle._xanad._apply import _strip_json_comments
        text = '{"a": 1, "b": "two"}'
        self.assertEqual(json.loads(text), json.loads(_strip_json_comments(text)))


class MergeJsonObjectFileJsoncTests(unittest.TestCase):
    def test_merge_succeeds_with_jsonc_existing_target(self) -> None:
        """merge_json_object_file() must not crash on // comments in the existing target."""
        from scripts.lifecycle._xanad._apply import merge_json_object_file
        from scripts.lifecycle._xanad._loader import load_manifest, load_json
        from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH
        manifest = load_manifest(REPO_ROOT, load_json(REPO_ROOT / DEFAULT_POLICY_PATH)) or {}
        entry = next(
            (e for e in manifest.get("managedFiles", []) if e.get("strategy") == "merge-json-object"),
            None,
        )
        if entry is None:
            self.skipTest("No merge-json-object entries in manifest")
        with tempfile.TemporaryDirectory() as tmp:
            target_path = Path(tmp) / entry["target"]
            target_path.parent.mkdir(parents=True, exist_ok=True)
            # Simulate VS Code settings.json with // comments
            target_path.write_text(
                '{\n    // a comment\n    "existing.key": "existing-value"\n}\n',
                encoding="utf-8",
            )
            merge_json_object_file(target_path, REPO_ROOT, entry)
            result = json.loads(target_path.read_text(encoding="utf-8"))
            self.assertIn("existing.key", result)


# ---------------------------------------------------------------------------
# _execute_apply.py — _apply_memory_gitignore
# ---------------------------------------------------------------------------

class ApplyMemoryGitignoreTests(unittest.TestCase):
    def setUp(self):
        from scripts.lifecycle._xanad._execute_apply import _apply_memory_gitignore
        self._fn = _apply_memory_gitignore

    def test_does_nothing_when_answer_is_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._fn(workspace, {"memory.gitignore": False})
            self.assertFalse((workspace / ".gitignore").exists())

    def test_does_nothing_when_answer_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._fn(workspace, {})
            self.assertFalse((workspace / ".gitignore").exists())

    def test_creates_gitignore_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self._fn(workspace, {"memory.gitignore": True})
            content = (workspace / ".gitignore").read_text(encoding="utf-8")
            self.assertIn(".github/xanadAssistant/memory/", content)

    def test_appends_to_existing_gitignore(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
            self._fn(workspace, {"memory.gitignore": True})
            content = (workspace / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("node_modules/", content)
            self.assertIn(".github/xanadAssistant/memory/", content)

    def test_does_not_duplicate_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".gitignore").write_text(".github/xanadAssistant/memory/\n", encoding="utf-8")
            self._fn(workspace, {"memory.gitignore": True})
            content = (workspace / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(content.count(".github/xanadAssistant/memory/"), 1)

    def test_adds_entry_when_only_in_a_comment(self):
        """A commented-out entry must not suppress the real gitignore entry."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".gitignore").write_text(
                "# .github/xanadAssistant/memory/\nnode_modules/\n", encoding="utf-8"
            )
            self._fn(workspace, {"memory.gitignore": True})
            content = (workspace / ".gitignore").read_text(encoding="utf-8")
            lines = [ln.strip() for ln in content.splitlines()]
            self.assertIn(".github/xanadAssistant/memory/", lines)

    def test_does_not_duplicate_entry_without_trailing_slash(self):
        """Entry without trailing slash counts as already present."""
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".gitignore").write_text(
                ".github/xanadAssistant/memory\n", encoding="utf-8"
            )
            self._fn(workspace, {"memory.gitignore": True})
            content = (workspace / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(content.count(".github/xanadAssistant/memory"), 1)


class MemoryGitignoreQuestionTests(unittest.TestCase):
    def test_question_is_present_with_correct_shape(self):
        from scripts.lifecycle._xanad._interview_questions import personalisation_questions
        questions = personalisation_questions()
        q = next((q for q in questions if q["id"] == "memory.gitignore"), None)
        self.assertIsNotNone(q, "memory.gitignore question missing from personalisation_questions")
        self.assertEqual(q["kind"], "confirm")
        self.assertEqual(q["batch"], "advanced")
        self.assertFalse(q["required"])
        self.assertTrue(q["default"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
