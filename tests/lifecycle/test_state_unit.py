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


REPO_ROOT = Path(__file__).resolve().parents[2]


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
            lockfile = ws / ".github" / "xanadAssistant-lock.json"
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
        state = {"data": {"package": {"name": "xanadAssistant"}}}
        self.assertEqual("xanadAssistant", get_lockfile_package_name(state))

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



if __name__ == "__main__":  # pragma: no cover
    unittest.main()
