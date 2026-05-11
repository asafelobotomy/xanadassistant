"""Direct unit tests for scripts/lifecycle/_xanad/_state.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._state import (
    CURRENT_PACKAGE_NAME,
    _lockfile_needs_migration,
    count_files,
    detect_existing_surfaces,
    detect_git_state,
    determine_install_state,
    get_lockfile_package_name,
    get_predecessor_package_name,
    migrate_lockfile_shape,
    parse_legacy_version_file,
    parse_lockfile_state,
    read_lockfile_status,
    summarize_manifest_targets,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class DetectGitStateTests(unittest.TestCase):
    def test_returns_not_present_when_no_git_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = detect_git_state(Path(tmp))
            self.assertFalse(result["present"])
            self.assertIsNone(result["dirty"])

    def test_returns_present_for_repo_root(self) -> None:
        result = detect_git_state(REPO_ROOT)
        self.assertTrue(result["present"])
        self.assertIn("dirty", result)


class DetermineInstallStateTests(unittest.TestCase):
    def test_not_installed_when_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state, paths = determine_install_state(Path(tmp))
            self.assertEqual("not-installed", state)
            self.assertIsNone(paths["lockfile"])

    def test_installed_when_lockfile_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            lockfile = ws / ".github" / "xanad-assistant-lock.json"
            lockfile.parent.mkdir(parents=True)
            lockfile.write_text("{}", encoding="utf-8")
            state, paths = determine_install_state(ws)
            self.assertEqual("installed", state)
            self.assertIsNotNone(paths["lockfile"])

    def test_legacy_version_only_when_copilot_version_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            legacy = ws / ".github" / "copilot-version.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("version: 1.0\n", encoding="utf-8")
            state, paths = determine_install_state(ws)
            self.assertEqual("legacy-version-only", state)


class ParseLegacyVersionFileTests(unittest.TestCase):
    def test_returns_not_present_when_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = parse_legacy_version_file(Path(tmp))
            self.assertFalse(result["present"])
            self.assertFalse(result["malformed"])

    def test_parses_version_from_plain_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            legacy = ws / ".github" / "copilot-version.md"
            legacy.parent.mkdir()
            legacy.write_text("version: 2.0\n", encoding="utf-8")
            result = parse_legacy_version_file(ws)
            self.assertTrue(result["present"])
            self.assertFalse(result["malformed"])
            self.assertEqual("2.0", result["data"]["version"])

    def test_parses_version_from_json_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            legacy = ws / ".github" / "copilot-version.md"
            legacy.parent.mkdir()
            legacy.write_text('```json\n{"version": "3.0"}\n```\n', encoding="utf-8")
            result = parse_legacy_version_file(ws)
            self.assertTrue(result["present"])
            self.assertFalse(result["malformed"])
            self.assertEqual({"version": "3.0"}, result["data"])

    def test_malformed_json_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            legacy = ws / ".github" / "copilot-version.md"
            legacy.parent.mkdir()
            legacy.write_text("```json\n{invalid json}\n```\n", encoding="utf-8")
            result = parse_legacy_version_file(ws)
            self.assertTrue(result["present"])
            self.assertTrue(result["malformed"])

    def test_malformed_when_no_recognizable_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            legacy = ws / ".github" / "copilot-version.md"
            legacy.parent.mkdir()
            legacy.write_text("some random text with no version\n", encoding="utf-8")
            result = parse_legacy_version_file(ws)
            self.assertTrue(result["present"])
            self.assertTrue(result["malformed"])


class LockfileNeedsMigrationTests(unittest.TestCase):
    def test_needs_migration_when_missing_fields(self) -> None:
        self.assertTrue(_lockfile_needs_migration({}))

    def test_needs_migration_when_package_name_wrong(self) -> None:
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "old-package"},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {},
            "selectedPacks": [],
            "files": [],
        }
        self.assertTrue(_lockfile_needs_migration(data))

    def test_does_not_need_migration_for_valid_lockfile(self) -> None:
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": CURRENT_PACKAGE_NAME},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {},
            "selectedPacks": [],
            "files": [],
        }
        self.assertFalse(_lockfile_needs_migration(data))

    def test_non_dict_input_returns_false(self) -> None:
        self.assertFalse(_lockfile_needs_migration("not a dict"))  # type: ignore[arg-type]

    def test_needs_migration_when_manifest_block_missing_hash(self) -> None:
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": CURRENT_PACKAGE_NAME},
            "manifest": {"schemaVersion": "0.1.0"},
            "timestamps": {},
            "selectedPacks": [],
            "files": [],
        }
        self.assertTrue(_lockfile_needs_migration(data))


class GetLockfilePackageNameTests(unittest.TestCase):
    def test_returns_name_from_valid_state(self) -> None:
        state = {"data": {"package": {"name": "xanad-assistant"}}}
        self.assertEqual("xanad-assistant", get_lockfile_package_name(state))

    def test_returns_none_when_data_is_none(self) -> None:
        self.assertIsNone(get_lockfile_package_name({"data": None}))

    def test_returns_none_when_package_missing(self) -> None:
        self.assertIsNone(get_lockfile_package_name({"data": {}}))

    def test_returns_none_when_name_not_string(self) -> None:
        state = {"data": {"package": {"name": 42}}}
        self.assertIsNone(get_lockfile_package_name(state))


class GetPredecessorPackageNameTests(unittest.TestCase):
    def test_returns_predecessor_name(self) -> None:
        state = {"data": {"package": {"name": "copilot-instructions-template"}}}
        result = get_predecessor_package_name(state)
        self.assertEqual("copilot-instructions-template", result)

    def test_returns_none_for_current_package_name(self) -> None:
        state = {"data": {"package": {"name": CURRENT_PACKAGE_NAME}}}
        result = get_predecessor_package_name(state)
        self.assertIsNone(result)

    def test_uses_original_package_name_field_first(self) -> None:
        state = {
            "originalPackageName": "copilot-instructions-template",
            "data": {"package": {"name": CURRENT_PACKAGE_NAME}},
        }
        result = get_predecessor_package_name(state)
        self.assertEqual("copilot-instructions-template", result)


class MigrateLockfileShapeTests(unittest.TestCase):
    def test_fills_missing_fields_with_defaults(self) -> None:
        result = migrate_lockfile_shape({})
        self.assertIn("schemaVersion", result)
        self.assertIn("package", result)
        self.assertIn("manifest", result)
        self.assertIn("timestamps", result)
        self.assertIn("selectedPacks", result)
        self.assertIn("files", result)

    def test_resets_package_name_to_current(self) -> None:
        result = migrate_lockfile_shape({"package": {"name": "old-pkg"}})
        self.assertEqual(CURRENT_PACKAGE_NAME, result["package"]["name"])

    def test_preserves_original_package_name_in_unknown_values(self) -> None:
        result = migrate_lockfile_shape({"package": {"name": "copilot-instructions-template"}})
        self.assertEqual(
            "copilot-instructions-template",
            result["unknownValues"]["migratedFromPackageName"],
        )

    def test_preserves_existing_manifest_fields(self) -> None:
        data = {
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:existing", "extra": "kept"}
        }
        result = migrate_lockfile_shape(data)
        self.assertEqual("sha256:existing", result["manifest"]["hash"])
        self.assertEqual("kept", result["manifest"]["extra"])


class ParseLockfileStateTests(unittest.TestCase):
    def test_returns_not_present_when_no_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = parse_lockfile_state(Path(tmp))
            self.assertFalse(result["present"])
            self.assertFalse(result["malformed"])

    def test_returns_malformed_for_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            lockfile = ws / ".github" / "xanad-assistant-lock.json"
            lockfile.parent.mkdir()
            lockfile.write_text("{ invalid json", encoding="utf-8")
            result = parse_lockfile_state(ws)
            self.assertTrue(result["present"])
            self.assertTrue(result["malformed"])

    def test_returns_present_and_migrates_old_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            lockfile = ws / ".github" / "xanad-assistant-lock.json"
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
            lockfile = ws / ".github" / "xanad-assistant-lock.json"
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
