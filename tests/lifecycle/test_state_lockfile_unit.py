"""Unit tests for lockfile parsing and workspace scanning in _state.py."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._state import (
    CURRENT_PACKAGE_NAME,
    count_files,
    detect_existing_surfaces,
    parse_lockfile_state,
    read_lockfile_status,
    summarize_manifest_targets,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class ParseLockfileStateTests(unittest.TestCase):
    def test_returns_not_present_when_no_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = parse_lockfile_state(Path(tmp))
            self.assertFalse(result["present"])
            self.assertFalse(result["malformed"])

    def test_returns_malformed_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            lockfile = ws / ".github" / "xanadAssistant-lock.json"
            lockfile.parent.mkdir()
            lockfile.write_text("{ invalid json", encoding="utf-8")
            result = parse_lockfile_state(ws)
            self.assertTrue(result["present"])
            self.assertTrue(result["malformed"])

    def test_returns_present_and_migrates_old_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            lockfile = ws / ".github" / "xanadAssistant-lock.json"
            lockfile.parent.mkdir()
            old_data = {"package": {"name": "copilot-instructions-template"}}
            lockfile.write_text(json.dumps(old_data), encoding="utf-8")
            result = parse_lockfile_state(ws)
            self.assertTrue(result["present"])
            self.assertFalse(result["malformed"])
            self.assertTrue(result["needsMigration"])

    def test_returns_present_for_valid_current_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            lockfile = ws / ".github" / "xanadAssistant-lock.json"
            lockfile.parent.mkdir()
            valid_data = {
                "schemaVersion": "0.1.0",
                "package": {"name": CURRENT_PACKAGE_NAME},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [],
                "files": [],
            }
            lockfile.write_text(json.dumps(valid_data), encoding="utf-8")
            result = parse_lockfile_state(ws)
            self.assertTrue(result["present"])
            self.assertFalse(result["malformed"])
            self.assertFalse(result["needsMigration"])


class ReadLockfileStatusTests(unittest.TestCase):
    def test_returns_status_dict_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = read_lockfile_status(Path(tmp))
            self.assertIn("present", result)
            self.assertIn("malformed", result)
            self.assertIn("needsMigration", result)


class CountFilesTests(unittest.TestCase):
    def test_returns_zero_for_nonexistent_path(self) -> None:
        self.assertEqual(0, count_files(Path("/nonexistent")))

    def test_returns_zero_for_non_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.txt"
            path.write_text("x\n", encoding="utf-8")
            self.assertEqual(0, count_files(path))

    def test_counts_files_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("a\n", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.txt").write_text("b\n", encoding="utf-8")
            self.assertEqual(2, count_files(root))


class DetectExistingSurfacesTests(unittest.TestCase):
    def test_all_surfaces_absent_in_empty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = detect_existing_surfaces(Path(tmp))
            self.assertFalse(result["instructions"]["present"])
            self.assertFalse(result["mcp"]["present"])
            self.assertEqual(0, result["prompts"]["count"])

    def test_detects_instructions_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            instructions = ws / ".github" / "copilot-instructions.md"
            instructions.parent.mkdir(parents=True)
            instructions.write_text("instructions\n", encoding="utf-8")
            result = detect_existing_surfaces(ws)
            self.assertTrue(result["instructions"]["present"])

    def test_detects_mcp_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            mcp = ws / ".vscode" / "mcp.json"
            mcp.parent.mkdir(parents=True)
            mcp.write_text("{}\n", encoding="utf-8")
            result = detect_existing_surfaces(ws)
            self.assertTrue(result["mcp"]["present"])


class SummarizeManifestTargetsTests(unittest.TestCase):
    def test_returns_zero_dict_for_none_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = summarize_manifest_targets(Path(tmp), None)
            self.assertEqual(0, result["declared"])
            self.assertEqual(0, result["present"])

    def test_counts_missing_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            manifest = {
                "managedFiles": [{"target": ".github/not-there.md"}],
                "retiredFiles": [],
            }
            result = summarize_manifest_targets(ws, manifest)
            self.assertEqual(1, result["declared"])
            self.assertEqual(0, result["present"])
            self.assertEqual(1, result["missing"])

    def test_counts_present_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            target = ws / ".github" / "copilot-instructions.md"
            target.parent.mkdir(parents=True)
            target.write_text("instructions\n", encoding="utf-8")
            manifest = {
                "managedFiles": [{"target": ".github/copilot-instructions.md"}],
                "retiredFiles": [],
            }
            result = summarize_manifest_targets(ws, manifest)
            self.assertEqual(1, result["declared"])
            self.assertEqual(1, result["present"])
            self.assertEqual(0, result["missing"])

    def test_counts_skipped_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            manifest = {
                "managedFiles": [{"target": ".github/file.md", "status": "skipped"}],
                "retiredFiles": [],
            }
            result = summarize_manifest_targets(ws, manifest)
            self.assertEqual(1, result["skipped"])


class ParseLockfileStateSetupAnswersTests(unittest.TestCase):
    """Verify that setupAnswers and mcpEnabled are surfaced from lockfile state (Bug 1+2)."""

    def _write_lockfile(self, ws: Path, data: dict) -> None:
        lockfile = ws / ".github" / "xanadAssistant-lock.json"
        lockfile.parent.mkdir(parents=True, exist_ok=True)
        lockfile.write_text(json.dumps(data), encoding="utf-8")

    def _valid_base(self) -> dict:
        return {
            "schemaVersion": "0.1.0",
            "package": {"name": CURRENT_PACKAGE_NAME},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
            "selectedPacks": [],
            "files": [],
        }

    def test_setup_answers_surfaced_from_valid_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            data = self._valid_base()
            data["setupAnswers"] = {"response.style": "verbose", "testing.philosophy": "skip"}
            self._write_lockfile(ws, data)
            result = parse_lockfile_state(ws)
        self.assertEqual({"response.style": "verbose", "testing.philosophy": "skip"}, result["setupAnswers"])

    def test_setup_answers_defaults_to_empty_dict_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            self._write_lockfile(ws, self._valid_base())
            result = parse_lockfile_state(ws)
        self.assertEqual({}, result["setupAnswers"])

    def test_mcp_enabled_surfaced_from_install_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            data = self._valid_base()
            data["installMetadata"] = {"mcpAvailable": True, "mcpEnabled": False}
            self._write_lockfile(ws, data)
            result = parse_lockfile_state(ws)
        self.assertIs(False, result["mcpEnabled"])

    def test_mcp_enabled_is_none_when_install_metadata_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            self._write_lockfile(ws, self._valid_base())
            result = parse_lockfile_state(ws)
        self.assertIsNone(result["mcpEnabled"])

    def test_not_present_lockfile_has_empty_setup_answers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = parse_lockfile_state(Path(tmp))
        self.assertEqual({}, result["setupAnswers"])
        self.assertIsNone(result["mcpEnabled"])

    def test_malformed_lockfile_has_empty_setup_answers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            lockfile = ws / ".github" / "xanadAssistant-lock.json"
            lockfile.parent.mkdir()
            lockfile.write_text("{ invalid", encoding="utf-8")
            result = parse_lockfile_state(ws)
        self.assertEqual({}, result["setupAnswers"])
        self.assertIsNone(result["mcpEnabled"])
