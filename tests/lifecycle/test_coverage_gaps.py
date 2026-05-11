"""Tests targeting specific uncovered code paths in the lifecycle engine.

Each test is narrow — it exercises exactly one uncovered branch.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# _loader.py
# ---------------------------------------------------------------------------

class LoaderGapTests(unittest.TestCase):
    def test_load_optional_json_returns_none_for_nonexistent(self):
        from scripts.lifecycle._xanad._loader import load_optional_json
        result = load_optional_json(Path("/nonexistent_path_xyz/file.json"))
        self.assertIsNone(result)

    def test_load_manifest_returns_none_when_manifest_missing(self):
        from scripts.lifecycle._xanad._loader import load_manifest
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            # Minimal policy that points to a manifest path that doesn't exist
            policy = {"generationSettings": {"manifestOutput": "install-manifest.json"}}
            result = load_manifest(pkg_root, policy)
            self.assertIsNone(result)


# ---------------------------------------------------------------------------
# _manifest_utils.py
# ---------------------------------------------------------------------------

class ManifestUtilsGapTests(unittest.TestCase):
    def test_build_file_id_with_dot_path(self):
        from scripts.lifecycle._manifest_utils import build_file_id
        result = build_file_id("agents", Path("."))
        self.assertEqual("agents", result)

    def test_iter_source_files_nonexistent_dir_yields_nothing(self):
        from scripts.lifecycle._manifest_utils import iter_source_files
        results = list(iter_source_files(Path("/nonexistent_dir_xyz"), "directory"))
        self.assertEqual([], results)

    def test_normalize_condition_expression_str(self):
        from scripts.lifecycle._manifest_utils import normalize_condition_expression
        result = normalize_condition_expression("my-condition")
        self.assertEqual(["my-condition"], result)

    def test_normalize_condition_expression_list(self):
        from scripts.lifecycle._manifest_utils import normalize_condition_expression
        result = normalize_condition_expression(["a", "b", "c"])
        self.assertEqual(["a", "b", "c"], result)

    def test_normalize_condition_expression_none(self):
        from scripts.lifecycle._manifest_utils import normalize_condition_expression
        result = normalize_condition_expression(None)
        self.assertEqual([], result)


# ---------------------------------------------------------------------------
# _conditions.py
# ---------------------------------------------------------------------------

class ConditionsGapTests(unittest.TestCase):
    def test_parse_condition_literal_returns_false_for_false_string(self):
        """_conditions.py line 41: parse_condition_literal returns False for 'false' string."""
        from scripts.lifecycle._xanad._conditions import parse_condition_literal
        self.assertIs(False, parse_condition_literal("false"))
        self.assertIs(False, parse_condition_literal("FALSE"))
        self.assertIs(False, parse_condition_literal("False"))

    def test_condition_matches_list_actual_contains_parsed(self):
        from scripts.lifecycle._xanad._conditions import condition_matches
        # When actual is a list and parsed value is in the list
        result = condition_matches("q=v", {"q": ["v", "x", "y"]})
        self.assertTrue(result)

    def test_condition_matches_list_actual_does_not_contain(self):
        from scripts.lifecycle._xanad._conditions import condition_matches
        result = condition_matches("q=z", {"q": ["v", "x"]})
        self.assertFalse(result)

    def test_entry_required_for_plan_string_required_when(self):
        from scripts.lifecycle._xanad._conditions import entry_required_for_plan
        # requiredWhen is a string → should be wrapped to list ["a=b"]
        entry = {"requiredWhen": "q=match"}
        resolved = {"q": "no-match"}
        result = entry_required_for_plan(entry, resolved)
        self.assertFalse(result)

    def test_entry_required_for_plan_string_required_when_matches(self):
        from scripts.lifecycle._xanad._conditions import entry_required_for_plan
        entry = {"requiredWhen": "q=match"}
        resolved = {"q": "match"}
        result = entry_required_for_plan(entry, resolved)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# _state.py
# ---------------------------------------------------------------------------

class StateGapTests(unittest.TestCase):
    def test_detect_git_state_oserror_returns_dirty_none(self):
        from scripts.lifecycle._xanad._state import detect_git_state
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".git").mkdir()
            with patch("subprocess.run", side_effect=OSError("no git")):
                result = detect_git_state(workspace)
        self.assertEqual({"present": True, "dirty": None}, result)

    def test_detect_git_state_nonzero_returncode_returns_dirty_none(self):
        from scripts.lifecycle._xanad._state import detect_git_state
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".git").mkdir()

            fake_result = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
            with patch("subprocess.run", return_value=fake_result):
                result = detect_git_state(workspace)
        self.assertEqual({"present": True, "dirty": None}, result)

    def test_lockfile_needs_migration_predecessor_name(self):
        from scripts.lifecycle._xanad._state import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "copilot-instructions-template"},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {},
            "selectedPacks": [],
            "files": [],
        }
        result = _lockfile_needs_migration(data)
        self.assertTrue(result)

    def test_lockfile_needs_migration_manifest_not_dict(self):
        """_state.py line 85: return True when manifest_block is not a dict."""
        from scripts.lifecycle._xanad._state import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanadAssistant"},
            "manifest": "not-a-dict",
            "timestamps": {},
            "selectedPacks": [],
            "files": [],
        }
        result = _lockfile_needs_migration(data)
        self.assertTrue(result)

    def test_lockfile_needs_migration_current_name(self):
        from scripts.lifecycle._xanad._state import _lockfile_needs_migration
        data = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanadAssistant"},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:abc"},
            "timestamps": {},
            "selectedPacks": [],
            "files": [],
        }
        result = _lockfile_needs_migration(data)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# _progress.py
# ---------------------------------------------------------------------------

class ProgressGapTests(unittest.TestCase):
    def test_emit_agent_progress_inspect_with_warnings(self):
        """Line 59: the warnings branch in emit_agent_progress for inspect command."""
        from scripts.lifecycle._xanad._progress import emit_agent_progress
        import io
        payload = {
            "command": "inspect",
            "result": {
                "installState": "not-installed",
                "manifestSummary": {"declared": 0},
            },
            "warnings": [{"code": "manifest_missing", "message": "not found"}],
        }
        # Redirect stderr to capture output without polluting test output
        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            emit_agent_progress(payload)
        output = mock_stderr.getvalue()
        self.assertIn("Warnings", output)


# ---------------------------------------------------------------------------
# _inspect.py  (via collect_context / build_inspect_result)
# ---------------------------------------------------------------------------

class InspectGapTests(unittest.TestCase):
    def _make_minimal_package_root(self, tmp: Path) -> Path:
        """Create a minimal package root with policy but NO manifest."""
        pkg_root = tmp / "pkg"
        pkg_root.mkdir()

        # Copy the real policy into the temp package root
        real_policy_path = REPO_ROOT / "template" / "setup" / "install-policy.json"
        real_policy = json.loads(real_policy_path.read_text())

        # Override manifest output to a path that won't exist
        real_policy.setdefault("generationSettings", {})["manifestOutput"] = "nonexistent-manifest.json"

        (pkg_root / "template").mkdir(parents=True, exist_ok=True)
        (pkg_root / "template" / "setup").mkdir(parents=True, exist_ok=True)
        (pkg_root / "template" / "setup" / "install-policy.json").write_text(
            json.dumps(real_policy), encoding="utf-8"
        )
        # Copy schemas needed by load_contract_artifacts
        for schema_file in ["install-policy.schema.json", "install-manifest.schema.json", "install-lock.schema.json"]:
            src = REPO_ROOT / "template" / "setup" / schema_file
            if src.exists():
                (pkg_root / "template" / "setup" / schema_file).write_text(
                    src.read_text(encoding="utf-8"), encoding="utf-8"
                )
        return pkg_root

    def test_collect_context_warns_manifest_missing(self):
        """Line 44: warning added when manifest is not loaded."""
        from scripts.lifecycle._xanad._inspect import collect_context
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            # Use REPO_ROOT as package root — it HAS a manifest, so use a temp pkg without it
            # Actually, it's simpler to use REPO_ROOT as package_root but point to a workspace;
            # the manifest_missing warning fires when manifest file doesn't exist.
            # Build minimal pkg root without the manifest file
            real_policy_path = REPO_ROOT / "template" / "setup" / "install-policy.json"
            real_policy = json.loads(real_policy_path.read_text())
            # The manifest path is template/setup/install-manifest.json by default
            # Let's create a pkg root structure that has policy but no manifest
            pkg_root = Path(tmp) / "pkg"
            pkg_root.mkdir()

            # Symlink (or copy) entire template/setup except the manifest itself
            setup_dir = pkg_root / "template" / "setup"
            setup_dir.mkdir(parents=True)
            for fname in ["install-policy.json", "install-policy.schema.json",
                          "install-manifest.schema.json", "install-lock.schema.json"]:
                src = REPO_ROOT / "template" / "setup" / fname
                if src.exists():
                    (setup_dir / fname).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

            # Also need the source files the policy references — surface dirs
            # Simplest: copy just enough to not crash on validate calls
            for subdir in ["agents", "skills", "hooks", "template", "template/prompts"]:
                src_dir = REPO_ROOT / subdir
                if src_dir.is_dir():
                    (pkg_root / subdir).mkdir(parents=True, exist_ok=True)
            # Populate with real source dirs for surfaces
            import shutil
            for surface_dir in ["agents", "skills"]:
                src = REPO_ROOT / surface_dir
                dst = pkg_root / surface_dir
                if src.is_dir() and dst.exists():
                    shutil.rmtree(str(dst))
                    shutil.copytree(str(src), str(dst))
            for subdir in ["hooks/scripts", "template/copilot-instructions.md",
                           "template/prompts", "template/instructions", "template/vscode"]:
                src = REPO_ROOT / subdir
                dst = pkg_root / subdir
                if src.is_dir():
                    if not dst.exists():
                        shutil.copytree(str(src), str(dst))
                elif src.is_file():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(dst))

            context = collect_context(workspace, pkg_root)
            warning_codes = [w["code"] for w in context["warnings"]]
            self.assertIn("manifest_missing", warning_codes)

    def test_collect_context_warns_package_name_mismatch(self):
        """Line 92: warning when lockfile package name is a predecessor."""
        from scripts.lifecycle._xanad._inspect import collect_context
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            (workspace / ".github").mkdir(parents=True)
            # Write lockfile with predecessor package name
            lockfile = {
                "schemaVersion": "0.1.0",
                "package": {"name": "copilot-instructions-template"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:fake"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [], "profile": "balanced",
                "ownershipBySurface": {}, "files": [],
            }
            (workspace / ".github" / "xanadAssistant-lock.json").write_text(
                json.dumps(lockfile), encoding="utf-8"
            )
            context = collect_context(workspace, REPO_ROOT)
            warning_codes = [w["code"] for w in context["warnings"]]
            self.assertIn("package_name_mismatch", warning_codes)

    def test_collect_context_warns_successor_cleanup_required(self):
        """_inspect.py line 92: successor_cleanup_required warning when predecessor files exist."""
        from scripts.lifecycle._xanad._inspect import collect_context
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            (workspace / ".github").mkdir(parents=True)
            # Lockfile with predecessor package name triggers predecessor_markers
            lockfile = {
                "schemaVersion": "0.1.0",
                "package": {"name": "copilot-instructions-template"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:fake"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [], "profile": "balanced",
                "ownershipBySurface": {}, "files": [],
            }
            (workspace / ".github" / "xanadAssistant-lock.json").write_text(
                json.dumps(lockfile), encoding="utf-8"
            )
            # Create a file in a successor migration root that is NOT in the managed set
            agents_dir = workspace / ".github" / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
            (agents_dir / "old-agent.agent.md").write_text("# Old agent", encoding="utf-8")
            context = collect_context(workspace, REPO_ROOT)
            warning_codes = [w["code"] for w in context["warnings"]]
            self.assertIn("successor_cleanup_required", warning_codes)

    def test_collect_context_warns_package_version_changed(self):
        """Line 73: warning when installed manifest hash != current manifest hash."""
        from scripts.lifecycle._xanad._inspect import collect_context
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            (workspace / ".github").mkdir(parents=True)
            # Write lockfile with a fake manifest hash (won't match real one)
            lockfile = {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanadAssistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:aaaaaaaaaaaa"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [], "profile": "balanced",
                "ownershipBySurface": {}, "files": [],
            }
            (workspace / ".github" / "xanadAssistant-lock.json").write_text(
                json.dumps(lockfile), encoding="utf-8"
            )
            context = collect_context(workspace, REPO_ROOT)
            warning_codes = [w["code"] for w in context["warnings"]]
            self.assertIn("package_version_changed", warning_codes)


# ---------------------------------------------------------------------------
# _check.py
# ---------------------------------------------------------------------------

class CheckGapTests(unittest.TestCase):
    def _make_ws_with_lockfile(self, tmp: Path, lockfile: dict) -> Path:
        ws = tmp / "ws"
        (ws / ".github").mkdir(parents=True)
        (ws / ".github" / "xanadAssistant-lock.json").write_text(
            json.dumps(lockfile), encoding="utf-8"
        )
        return ws

    def test_build_check_result_malformed_lockfile(self):
        """Line 20: counts['malformed'] += 1 when lockfile is malformed."""
        from scripts.lifecycle._xanad._check import build_check_result
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            (ws / ".github").mkdir(parents=True)
            (ws / ".github" / "xanadAssistant-lock.json").write_text(
                "this is not valid JSON {{{", encoding="utf-8"
            )
            result = build_check_result(ws, REPO_ROOT)
        self.assertGreater(result["result"]["summary"]["malformed"], 0)

    def test_build_check_result_malformed_legacy_version_file(self):
        """_check.py line 22: counts['malformed'] += 1 when legacyVersionState is malformed."""
        from scripts.lifecycle._xanad._check import build_check_result
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            (ws / ".github").mkdir(parents=True)
            # A copilot-version.md with no json block and no version: line is malformed
            (ws / ".github" / "copilot-version.md").write_text(
                "# No version info here\nJust some text without a version field.",
                encoding="utf-8",
            )
            result = build_check_result(ws, REPO_ROOT)
        self.assertGreater(result["result"]["summary"]["malformed"], 0)

    def test_build_check_result_skipped_files_not_in_targets(self):
        """Lines 29-30: skippedManagedFiles entries not in recorded_targets get appended."""
        from scripts.lifecycle._xanad._check import build_check_result
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanadAssistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:fake"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [], "profile": "balanced",
                "ownershipBySurface": {}, "files": [],
                # This file is skipped and definitely NOT a managed target → new skipped entry added
                "skippedManagedFiles": [".github/custom-completely-unique-file-xyz.md"],
            }
            ws = self._make_ws_with_lockfile(Path(tmp), lockfile)
            result = build_check_result(ws, REPO_ROOT)
        skipped_entries = [e for e in result["result"]["entries"] if e["status"] == "skipped"]
        targets = [e["target"] for e in skipped_entries]
        self.assertIn(".github/custom-completely-unique-file-xyz.md", targets)

    def test_build_check_result_unknown_file_status(self):
        """Lines 36-37: files with status 'unknown' in lockfile get counted."""
        from scripts.lifecycle._xanad._check import build_check_result
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = {
                "schemaVersion": "0.1.0",
                "package": {"name": "xanadAssistant"},
                "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:fake"},
                "timestamps": {"appliedAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"},
                "selectedPacks": [], "profile": "balanced",
                "ownershipBySurface": {}, "files": [
                    {"id": "test.unknown", "target": ".github/some-unknown-file.md", "status": "unknown"},
                ],
            }
            ws = self._make_ws_with_lockfile(Path(tmp), lockfile)
            result = build_check_result(ws, REPO_ROOT)
        unknown_entries = [e for e in result["result"]["entries"] if e.get("status") == "unknown"]
        self.assertGreater(len(unknown_entries), 0)


# ---------------------------------------------------------------------------
# _main.py lines 142-148
# ---------------------------------------------------------------------------

class MainPlanFactoryRestoreTests(unittest.TestCase):
    def test_plan_factory_restore_on_not_installed_workspace_triggers_error(self):
        """Lines 142-148: LifecycleCommandError handler in plan command."""
        from scripts.lifecycle._xanad._main import main
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            # workspace has no .github dir → install_state == "not-installed"
            exit_code = main([
                "plan", "factory-restore",
                "--workspace", str(workspace),
                "--package-root", str(REPO_ROOT),
                "--json",
                "--non-interactive",
            ])
        # Should return a nonzero exit code (not crash)
        self.assertNotEqual(0, exit_code)


# ---------------------------------------------------------------------------
# check_loc.py lines 54-57
# ---------------------------------------------------------------------------

class CheckLocFallbackTests(unittest.TestCase):
    def test_collect_files_falls_back_when_subprocess_fails(self):
        """Lines 54-57: fallback os.walk when git ls-files raises CalledProcessError."""
        import scripts.check_loc as check_loc_mod
        error = subprocess.CalledProcessError(1, ["git", "ls-files"])
        with patch("subprocess.run", side_effect=error):
            files = check_loc_mod.collect_files([])
        # Should return a list of paths (from os.walk fallback), not raise
        self.assertIsInstance(files, list)


# ---------------------------------------------------------------------------
# check_manifest_freshness.py lines 59-61, 70-72
# ---------------------------------------------------------------------------

class CheckManifestFreshnessTests(unittest.TestCase):
    def test_main_stale_manifest_returns_exit_code_1(self):
        """Lines 59-61: stale manifest prints error message and returns 1."""
        from scripts.lifecycle.check_manifest_freshness import main as fresh_main
        import io
        with tempfile.TemporaryDirectory() as tmp:
            # Write a stale manifest (empty dict) to a temp file
            stale_manifest = Path(tmp) / "stale-manifest.json"
            stale_manifest.write_text('{"schemaVersion":"0.1.0","managedFiles":[],"retiredFiles":[]}',
                                     encoding="utf-8")
            policy_path = str(REPO_ROOT / "template" / "setup" / "install-policy.json")
            argv = [
                "check_manifest_freshness",
                "--package-root", str(REPO_ROOT),
                "--policy", policy_path,
                "--manifest", str(stale_manifest),
            ]
            with patch("sys.argv", argv), patch("sys.stderr", new_callable=io.StringIO):
                exit_code = fresh_main()
        self.assertEqual(1, exit_code)

    def test_main_stale_catalog_returns_exit_code_1(self):
        """Lines 70-72: stale catalog prints error message and returns 1."""
        from scripts.lifecycle.check_manifest_freshness import main as fresh_main
        import io
        with tempfile.TemporaryDirectory() as tmp:
            stale_catalog = Path(tmp) / "stale-catalog.json"
            stale_catalog.write_text('{"commands":[]}', encoding="utf-8")
            policy_path = str(REPO_ROOT / "template" / "setup" / "install-policy.json")
            real_manifest = str(REPO_ROOT / "template" / "setup" / "install-manifest.json")
            argv = [
                "check_manifest_freshness",
                "--package-root", str(REPO_ROOT),
                "--policy", policy_path,
                "--manifest", real_manifest,
                "--catalog", str(stale_catalog),
            ]
            with patch("sys.argv", argv), patch("sys.stderr", new_callable=io.StringIO):
                exit_code = fresh_main()
        self.assertEqual(1, exit_code)


# ---------------------------------------------------------------------------
# generate_manifest.py lines 100, 103, 151, 153
# ---------------------------------------------------------------------------

class GenerateManifestGapTests(unittest.TestCase):
    def _load_real_policy(self) -> dict:
        import copy
        return copy.deepcopy(json.loads(
            (REPO_ROOT / "template" / "setup" / "install-policy.json").read_text()
        ))

    def test_validate_unmanaged_sources_skips_unused_source_root(self):
        """Line 100: source root in sourceRoots but not referenced by any surface → continue."""
        from scripts.lifecycle.generate_manifest import validate_unmanaged_sources
        policy = self._load_real_policy()
        # Add an extra source root that is not referenced by any canonical surface
        policy["sourceRoots"]["orphan-root"] = "docs"
        # Should not raise (the orphan root gets a 'continue' at line 100)
        validate_unmanaged_sources(REPO_ROOT, policy)

    def test_validate_unmanaged_sources_skips_nonexistent_dir(self):
        """Line 103: source root referenced by a surface but directory doesn't exist → continue."""
        from scripts.lifecycle.generate_manifest import validate_unmanaged_sources
        policy = self._load_real_policy()
        # Point an existing surface's source root to a nonexistent dir
        # We need a source root that IS in root_to_surfaces
        # root_to_surfaces is built from canonicalSurfaces
        # Let's find the first canonical surface and point its root to nonexistent path
        first_surface = policy["canonicalSurfaces"][0]
        source_root_key = policy["surfaceSources"][first_surface]["sourceRoot"]
        # Change that source root path to a nonexistent directory
        policy["sourceRoots"][source_root_key] = "nonexistent-dir-xyz"
        # Should not raise (the nonexistent dir gets a 'continue' at line 103)
        validate_unmanaged_sources(REPO_ROOT, policy)

    def test_generate_manifest_raises_on_invalid_ownership_mode(self):
        """Line 151: generate_manifest raises ValueError for unknown ownershipMode."""
        from scripts.lifecycle.generate_manifest import generate_manifest
        policy = self._load_real_policy()
        first_surface = policy["canonicalSurfaces"][0]
        policy["ownershipDefaults"][first_surface] = "invalid-mode-xyz"
        with self.assertRaises(ValueError) as ctx:
            generate_manifest(REPO_ROOT, policy)
        self.assertIn("Unsupported ownership mode", str(ctx.exception))

    def test_generate_manifest_raises_on_invalid_strategy(self):
        """Line 153: generate_manifest raises ValueError for unknown write strategy."""
        from scripts.lifecycle.generate_manifest import generate_manifest
        policy = self._load_real_policy()
        first_surface = policy["canonicalSurfaces"][0]
        policy["strategyDefaults"][first_surface] = "invalid-strategy-xyz"
        with self.assertRaises(ValueError) as ctx:
            generate_manifest(REPO_ROOT, policy)
        self.assertIn("Unsupported write strategy", str(ctx.exception))


# ---------------------------------------------------------------------------
# _plan_utils.py
# ---------------------------------------------------------------------------

class PlanUtilsGapTests(unittest.TestCase):
    def _make_entry(self, strategy: str, source_rel: str = "source.json") -> dict:
        return {
            "strategy": strategy,
            "source": source_rel,
        }

    def test_expected_entry_bytes_merge_json_not_dict_returns_none(self):
        """Line 33: merge-json-object source that is not a dict → None."""
        from scripts.lifecycle._xanad._plan_utils import expected_entry_bytes
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            # Source file is a list, not a dict
            (pkg_root / "source.json").write_text("[1, 2, 3]", encoding="utf-8")
            entry = self._make_entry("merge-json-object")
            result = expected_entry_bytes(pkg_root, entry, {}, target_path=None)
        self.assertIsNone(result)

    def test_expected_entry_bytes_merge_json_target_not_dict_returns_none(self):
        """_plan_utils.py line 41: merge-json-object when target JSON is not a dict → None."""
        from scripts.lifecycle._xanad._plan_utils import expected_entry_bytes
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            (pkg_root / "source.json").write_text('{"a": 1}', encoding="utf-8")
            target = Path(tmp) / "target.json"
            # Target file contains a list (not a dict)
            target.write_text('[1, 2, 3]', encoding="utf-8")
            entry = self._make_entry("merge-json-object")
            result = expected_entry_bytes(pkg_root, entry, {}, target_path=target)
        self.assertIsNone(result)

    def test_expected_entry_bytes_merge_json_json_decode_error_returns_none(self):
        """Lines 38-39: merge-json-object with corrupted target → None."""
        from scripts.lifecycle._xanad._plan_utils import expected_entry_bytes
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            (pkg_root / "source.json").write_text('{"key": "val"}', encoding="utf-8")
            corrupt_target = Path(tmp) / "corrupt.json"
            corrupt_target.write_text("{not valid json", encoding="utf-8")
            entry = self._make_entry("merge-json-object")
            result = expected_entry_bytes(pkg_root, entry, {}, target_path=corrupt_target)
        self.assertIsNone(result)

    def test_expected_entry_bytes_merge_json_existing_and_source_valid(self):
        """Line 41: merge-json-object when both target and source are valid dicts."""
        from scripts.lifecycle._xanad._plan_utils import expected_entry_bytes
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            (pkg_root / "source.json").write_text('{"a": 1}', encoding="utf-8")
            target = Path(tmp) / "target.json"
            target.write_text('{"b": 2}', encoding="utf-8")
            entry = self._make_entry("merge-json-object")
            result = expected_entry_bytes(pkg_root, entry, {}, target_path=target)
        self.assertIsNotNone(result)
        data = json.loads(result)
        self.assertIn("a", data)
        self.assertIn("b", data)

    def test_expected_entry_hash_returns_none_when_bytes_none(self):
        """Line 63: expected_entry_hash returns None when expected_entry_bytes returns None."""
        from scripts.lifecycle._xanad._plan_utils import expected_entry_hash
        with tempfile.TemporaryDirectory() as tmp:
            pkg_root = Path(tmp)
            # merge-json-object with non-dict source → bytes is None → hash is None
            (pkg_root / "source.json").write_text("[1, 2]", encoding="utf-8")
            entry = self._make_entry("merge-json-object")
            result = expected_entry_hash(pkg_root, entry, {}, target_path=None)
        self.assertIsNone(result)

    def test_build_backup_plan_not_required(self):
        """Line 91: backup_required=False returns empty backup plan."""
        from scripts.lifecycle._xanad._plan_utils import build_backup_plan
        result = build_backup_plan({}, [], backup_required=False)
        self.assertFalse(result["required"])
        self.assertIsNone(result["root"])
        self.assertEqual([], result["targets"])

    def test_build_backup_plan_with_archive_retired_action(self):
        """Lines 105+: archive-retired action with archive_root → archive_targets populated."""
        from scripts.lifecycle._xanad._plan_utils import build_backup_plan
        policy = {"retiredFilePolicy": {"archiveRoot": ".archive"}}
        actions = [
            {"action": "archive-retired", "target": "old-file.md"},
        ]
        result = build_backup_plan(policy, actions, backup_required=True)
        self.assertTrue(result["required"])
        self.assertEqual(1, len(result["archiveTargets"]))

    def test_build_backup_plan_with_replace_action_adds_backup_target(self):
        """_plan_utils.py line 105: replace action → backup_targets populated."""
        from scripts.lifecycle._xanad._plan_utils import build_backup_plan
        policy = {}
        actions = [
            {"action": "replace", "target": ".github/copilot-instructions.md"},
        ]
        result = build_backup_plan(policy, actions, backup_required=True)
        self.assertTrue(result["required"])
        self.assertEqual(1, len(result["targets"]))

    def test_build_backup_plan_with_archive_retired_report_only(self):
        """Line 105: archive-retired with report-retired strategy → NOT in archive_targets."""
        from scripts.lifecycle._xanad._plan_utils import build_backup_plan
        policy = {"retiredFilePolicy": {"archiveRoot": ".archive"}}
        actions = [
            {"action": "archive-retired", "target": "old-file.md", "strategy": "report-retired"},
        ]
        result = build_backup_plan(policy, actions, backup_required=True)
        self.assertEqual(0, len(result["archiveTargets"]))

    def test_build_token_plan_summary_populated(self):
        """Line 117+: build_token_plan_summary with matching tokens."""
        from scripts.lifecycle._xanad._plan_utils import build_token_plan_summary
        policy = {
            "tokenRules": [
                {"token": "{{WORKSPACE_NAME}}", "required": True},
            ]
        }
        actions = [
            {"action": "add", "target": ".github/copilot-instructions.md",
             "tokens": ["{{WORKSPACE_NAME}}"]},
        ]
        token_values = {"{{WORKSPACE_NAME}}": "my-project"}
        result = build_token_plan_summary(policy, actions, token_values)
        self.assertEqual(1, len(result))
        self.assertEqual("{{WORKSPACE_NAME}}", result[0]["token"])
        self.assertEqual("my-project", result[0]["value"])
        self.assertTrue(result[0]["required"])


# ---------------------------------------------------------------------------
# _source.py line 167 — parse_github_source called when source_arg is not None
# ---------------------------------------------------------------------------

class SourceGapTests(unittest.TestCase):
    def test_resolve_effective_package_root_calls_parse_github_source(self):
        """_source.py line 167: owner/repo = parse_github_source(source_arg) is executed."""
        from unittest.mock import patch as _patch
        from scripts.lifecycle._xanad._source import resolve_effective_package_root
        with tempfile.TemporaryDirectory() as tmp:
            with _patch("scripts.lifecycle._xanad._source.resolve_github_ref") as mock_ref:
                mock_ref.return_value = REPO_ROOT
                result = resolve_effective_package_root(
                    None, "github:owner/repo", None, None,
                )
        # The function should return (REPO_ROOT, {...}) via the pragma'd else branch
        self.assertIsNotNone(result)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
