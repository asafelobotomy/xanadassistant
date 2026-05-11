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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
