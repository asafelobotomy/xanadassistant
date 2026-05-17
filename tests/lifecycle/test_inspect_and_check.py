from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _check
from scripts.lifecycle._xanad import _inspect
from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH


class InspectTests(unittest.TestCase):
    def test_collect_context_adds_real_manifest_hash_and_package_name_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            policy_path = package_root / DEFAULT_POLICY_PATH
            manifest_path = package_root / "template" / "setup" / "install-manifest.json"
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(
                json.dumps({"tokenRules": [], "generationSettings": {"manifestOutput": "template/setup/install-manifest.json"}}),
                encoding="utf-8",
            )
            manifest_path.write_text(json.dumps({"managedFiles": [], "retiredFiles": []}), encoding="utf-8")
            lockfile_path = workspace / ".github" / "xanadAssistant-lock.json"
            lockfile_path.parent.mkdir(parents=True)
            lockfile_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "0.1.0",
                        "package": {"name": "copilot-instructions-template"},
                        "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:old"},
                        "timestamps": {"appliedAt": "2026-05-16T00:00:00Z", "updatedAt": "2026-05-16T00:00:00Z"},
                        "selectedPacks": [],
                        "files": [],
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch("scripts.lifecycle._xanad._inspect.derive_effective_plan_defaults", return_value=({}, {})), mock.patch(
                "scripts.lifecycle._xanad._inspect.resolve_token_values",
                return_value={},
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.annotate_manifest_entries",
                return_value={"managedFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.collect_successor_migration_files",
                return_value=[".github/prompts/legacy.prompt.md"],
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.check_memory_health",
                return_value=[{"code": "memory_warning", "message": "warn", "details": {}}],
            ):
                context = _inspect.collect_context(workspace, package_root)

        warning_codes = {warning["code"] for warning in context["warnings"]}
        self.assertEqual(
            warning_codes,
            {"package_version_changed", "package_name_mismatch", "successor_cleanup_required", "memory_warning"},
        )
        mismatch_warning = next(warning for warning in context["warnings"] if warning["code"] == "package_version_changed")
        self.assertEqual(mismatch_warning["details"]["installedHash"], "sha256:old")

    def test_collect_context_covers_manifest_missing_and_quiet_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()

            with mock.patch(
                "scripts.lifecycle._xanad._inspect.load_contract_artifacts",
                return_value=({"tokenRules": []}, {"manifest": {"loaded": False, "path": "template/setup/install-manifest.json"}}),
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.load_discovery_metadata",
                return_value=({}, {}),
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.load_manifest",
                return_value=None,
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.determine_install_state",
                return_value=("not-installed", {"lockfile": None}),
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.parse_legacy_version_file",
                return_value={"malformed": False},
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.parse_lockfile_state",
                return_value={
                    "malformed": False,
                    "resolvedTokenConflicts": {"voice": "docs", "ignored": 1},
                    "consumerResolutions": {},
                    "setupAnswers": {},
                    "mcpEnabled": False,
                    "data": {"manifest": {}},
                },
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.derive_effective_plan_defaults",
                return_value=({}, {}),
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.resolve_token_values",
                return_value={},
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.annotate_manifest_entries",
                return_value={"managedFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.summarize_manifest_targets",
                return_value={"declared": 0},
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.get_lockfile_package_name",
                return_value=None,
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.collect_successor_migration_files",
                return_value=[],
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.check_memory_health",
                return_value=[],
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.detect_git_state",
                return_value={"present": False},
            ), mock.patch(
                "scripts.lifecycle._xanad._inspect.detect_existing_surfaces",
                return_value={},
            ):
                context = _inspect.collect_context(workspace, package_root)

        self.assertEqual(context["warnings"], [{
            "code": "manifest_missing",
            "message": "Generated manifest not found at package root.",
            "details": {"path": "template/setup/install-manifest.json"},
        }])
        self.assertEqual(context["defaultPlanAnswers"], {"resolvedTokenConflicts.voice": "docs"})
        self.assertEqual(context["manifestSummary"], {"declared": 0})

    def test_build_inspect_result_shapes_payload_from_context(self) -> None:
        context = {
            "warnings": [],
            "installState": "installed",
            "installPaths": {"lockfile": ".github/xanadAssistant-lock.json"},
            "git": {"present": True, "dirty": False},
            "artifacts": {},
            "metadataArtifacts": {},
            "existingSurfaces": {"agents": {"count": 1}},
            "legacyVersionState": {"present": False},
            "lockfileState": {"present": True},
            "manifestSummary": {"declared": 1},
        }

        with mock.patch("scripts.lifecycle._xanad._inspect.collect_context", return_value=context):
            result = _inspect.build_inspect_result(Path("/workspace"), Path("/package"))

        self.assertEqual(result["command"], "inspect")
        self.assertEqual(result["result"]["manifestSummary"]["declared"], 1)


class CheckTests(unittest.TestCase):
    def test_build_check_result_marks_drift_and_augments_skipped_and_unknown(self) -> None:
        context = {
            "warnings": [],
            "installState": "installed",
            "installPaths": {"lockfile": ".github/xanadAssistant-lock.json"},
            "artifacts": {},
            "existingSurfaces": {},
            "legacyVersionState": {"malformed": True},
            "lockfileState": {
                "malformed": True,
                "skippedManagedFiles": [".github/skills/extra.skill.md"],
                "unknownValues": {"migratedFromPackageName": "old"},
                "files": [{"target": ".github/prompts/main.prompt.md", "status": "unknown"}],
            },
            "manifestWithStatus": {"managedFiles": []},
        }

        with mock.patch("scripts.lifecycle._xanad._check.collect_context", return_value=context), mock.patch(
            "scripts.lifecycle._xanad._check.classify_manifest_entries",
            return_value=({"missing": 0, "stale": 0, "malformed": 0, "retired": 0, "skipped": 0, "unknown": 0}, [], set()),
        ), mock.patch(
            "scripts.lifecycle._xanad._check.collect_unmanaged_files",
            return_value=[".github/mcp/scripts/custom.py"],
        ):
            result = _check.build_check_result(Path("/workspace"), Path("/package"))

        self.assertEqual(result["status"], "drift")
        self.assertEqual(result["result"]["summary"]["unmanaged"], 1)
        self.assertEqual(result["result"]["summary"]["malformed"], 2)
        self.assertEqual(result["result"]["summary"]["unknown"], 2)
        self.assertEqual(len(result["result"]["entries"]), 2)


if __name__ == "__main__":
    unittest.main()