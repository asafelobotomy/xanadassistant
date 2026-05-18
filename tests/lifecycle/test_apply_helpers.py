from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _apply
from scripts.lifecycle._xanad._errors import LifecycleCommandError


class ApplyHelperTests(unittest.TestCase):
    def test_generate_and_materialize_apply_timestamps(self) -> None:
        applied_at, path_timestamp = _apply.generate_apply_timestamps()

        self.assertTrue(applied_at.endswith("Z"))
        self.assertIn("T", path_timestamp)
        self.assertEqual(
            _apply.materialize_apply_timestamp(".xanadAssistant/backups/<apply-timestamp>", path_timestamp),
            f".xanadAssistant/backups/{path_timestamp}",
        )

    def test_render_entry_bytes_raises_when_rendering_fails(self) -> None:
        with mock.patch("scripts.lifecycle._xanad._apply.expected_entry_bytes", return_value=None):
            with self.assertRaises(LifecycleCommandError):
                _apply.render_entry_bytes(Path("."), {"id": "managed.prompt", "strategy": "replace"}, {})

    def test_merge_json_object_file_strips_comments_and_merge_markdown_preserves_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            package_root = root / "package"
            package_root.mkdir()
            json_source = package_root / "config.json"
            json_source.write_text(json.dumps({"setting": True}), encoding="utf-8")
            json_target = root / "config.json"
            json_target.write_text('{\n  // comment\n  "existing": 1\n}\n', encoding="utf-8")
            markdown_source = package_root / "instructions.md"
            markdown_source.write_text("# Title\n\nBase\n", encoding="utf-8")
            markdown_target = root / "instructions.md"
            markdown_target.write_text("# Title\n\n<!-- user-added -->keep<!-- /user-added -->\n", encoding="utf-8")

            _apply.merge_json_object_file(json_target, package_root, {"source": "config.json"})
            _apply.merge_markdown_file(markdown_target, package_root, {"source": "instructions.md"})

            merged_json = json.loads(json_target.read_text(encoding="utf-8"))
            merged_markdown = markdown_target.read_text(encoding="utf-8")

        self.assertEqual(merged_json, {"existing": 1, "setting": True})
        self.assertIn("<!-- user-added -->keep<!-- /user-added -->", merged_markdown)

    def test_build_summary_and_apply_chmod_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "script.sh"
            target.write_text("echo hi\n", encoding="utf-8")
            summary = _apply.build_copilot_version_summary(
                {
                    "profile": "balanced",
                    "selectedPacks": ["tdd"],
                    "manifest": {"hash": "sha256:abc"},
                    "timestamps": {"appliedAt": "2026-05-16T00:00:00Z"},
                },
                {"packageVersion": "1.2.3"},
            )
            _apply.apply_chmod_rule(target, "executable")

            self.assertTrue(target.stat().st_mode & stat.S_IXUSR)

        self.assertIn("Version: 1.2.3", summary)


if __name__ == "__main__":
    unittest.main()