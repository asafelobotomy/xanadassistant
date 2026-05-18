from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _conditions
from scripts.lifecycle._xanad import _interview
from scripts.lifecycle._xanad import _migration
from scripts.lifecycle._xanad import _plan_c
from scripts.lifecycle._xanad._errors import LifecycleCommandError


class MigrationAndPackTokensTests(unittest.TestCase):
    def _lockfile_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": "0.1.0",
            "package": {"name": _migration.CURRENT_PACKAGE_NAME},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:ok"},
            "timestamps": {},
            "selectedPacks": [],
            "files": [],
        }
        payload.update(overrides)
        return payload

    def test_lockfile_migration_detects_missing_fields_and_preserves_previous_package_name(self) -> None:
        self.assertTrue(_migration._lockfile_needs_migration({"manifest": {}}))

        migrated = _migration.migrate_lockfile_shape(
            {
                "package": {"name": "copilot-instructions-template"},
                "manifest": {},
                "timestamps": None,
                "selectedPacks": "not-a-list",
                "files": None,
            }
        )

        self.assertEqual(migrated["package"]["name"], _migration.CURRENT_PACKAGE_NAME)
        self.assertEqual(migrated["unknownValues"]["migratedFromPackageName"], "copilot-instructions-template")
        self.assertEqual(migrated["manifest"]["hash"], "sha256:unknown")
        self.assertEqual(migrated["selectedPacks"], [])
        self.assertEqual(migrated["files"], [])

    def test_lockfile_migration_helper_branches_cover_non_dicts_and_existing_valid_shape(self) -> None:
        self.assertFalse(_migration._lockfile_needs_migration([]))
        self.assertTrue(_migration._lockfile_needs_migration(self._lockfile_payload(package=[])))
        self.assertTrue(_migration._lockfile_needs_migration(self._lockfile_payload(manifest={"schemaVersion": "0.1.0"})))
        self.assertFalse(_migration._lockfile_needs_migration(self._lockfile_payload()))

        migrated = _migration.migrate_lockfile_shape(
            self._lockfile_payload(
                timestamps={"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                selectedPacks=["docs"],
                files=[{"target": ".github/prompts/main.prompt.md"}],
                unknownValues={"keep": True},
                skippedManagedFiles=[".github/mcp/scripts/gitMcp.py"],
                resolvedTokenConflicts={"voice": "docs"},
            )
        )

        self.assertEqual(migrated["package"], {"name": _migration.CURRENT_PACKAGE_NAME})
        self.assertEqual(migrated["manifest"]["hash"], "sha256:ok")
        self.assertEqual(migrated["selectedPacks"], ["docs"])
        self.assertEqual(migrated["unknownValues"], {"keep": True})
        self.assertEqual(migrated["skippedManagedFiles"], [".github/mcp/scripts/gitMcp.py"])
        self.assertEqual(migrated["resolvedTokenConflicts"], {"voice": "docs"})

    def test_migrate_lockfile_shape_replaces_invalid_unknown_values_container(self) -> None:
        migrated = _migration.migrate_lockfile_shape(
            {
                "package": {"name": "copilot-instructions-template"},
                "manifest": {},
                "timestamps": {},
                "selectedPacks": [],
                "files": [],
                "unknownValues": [],
            }
        )

        self.assertEqual(migrated["unknownValues"]["migratedFromPackageName"], "copilot-instructions-template")

    def test_load_pack_tokens_skips_invalid_sources_and_honors_resolved_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "packs" / "core").mkdir(parents=True)
            (root / "packs" / "core" / "tokens.json").write_text(
                json.dumps({"VOICE": "base", "STYLE": "plain"}),
                encoding="utf-8",
            )
            (root / "packs" / "docs").mkdir(parents=True)
            (root / "packs" / "docs" / "tokens.json").write_text(
                json.dumps({"VOICE": "docs", "DOC_STYLE": "clear"}),
                encoding="utf-8",
            )
            (root / "packs" / "secure").mkdir(parents=True)
            (root / "packs" / "secure" / "tokens.json").write_text("{invalid", encoding="utf-8")

            result = _conditions.load_pack_tokens(
                root,
                ["docs", "secure"],
                {"VOICE": "docs"},
            )

        self.assertEqual(result["{{VOICE}}"], "docs")
        self.assertEqual(result["{{STYLE}}"], "plain")
        self.assertEqual(result["{{DOC_STYLE}}"], "clear")


if __name__ == "__main__":
    unittest.main()
