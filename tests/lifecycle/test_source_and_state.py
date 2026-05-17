from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _loader
from scripts.lifecycle._xanad import _source
from scripts.lifecycle._xanad import _state
from scripts.lifecycle._xanad._errors import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_PACK_REGISTRY_PATH,
    DEFAULT_POLICY_PATH,
    DEFAULT_PROFILE_REGISTRY_PATH,
    LifecycleCommandError,
)


class LoaderTests(unittest.TestCase):
    def test_load_optional_json_returns_none_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertIsNone(_loader.load_optional_json(Path(tmpdir) / "missing.json"))

    def test_load_contract_artifacts_loads_policy_and_tracks_artifact_presence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            policy_path = root / DEFAULT_POLICY_PATH
            manifest_path = root / "template" / "setup" / "install-manifest.json"
            policy_path.parent.mkdir(parents=True)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(
                json.dumps({"generationSettings": {"manifestOutput": "template/setup/install-manifest.json"}}),
                encoding="utf-8",
            )
            manifest_path.write_text(json.dumps({"managedFiles": []}), encoding="utf-8")

            policy, artifacts = _loader.load_contract_artifacts(root)

        self.assertTrue(artifacts["policy"]["loaded"])
        self.assertTrue(artifacts["manifest"]["loaded"])
        self.assertIn("generationSettings", policy)

    def test_load_contract_artifacts_rejects_missing_or_malformed_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.assertRaises(LifecycleCommandError):
                _loader.load_contract_artifacts(root)

            policy_path = root / DEFAULT_POLICY_PATH
            policy_path.parent.mkdir(parents=True)
            policy_path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(LifecycleCommandError):
                _loader.load_contract_artifacts(root)

    def test_load_discovery_metadata_reads_optional_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for path, payload in (
                (DEFAULT_PACK_REGISTRY_PATH, {"packs": []}),
                (DEFAULT_PROFILE_REGISTRY_PATH, {"profiles": []}),
                (DEFAULT_CATALOG_PATH, {"entries": []}),
            ):
                full_path = root / path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(json.dumps(payload), encoding="utf-8")

            metadata, artifacts = _loader.load_discovery_metadata(root)

        self.assertEqual(metadata["packRegistry"], {"packs": []})
        self.assertTrue(artifacts["catalog"]["loaded"])


class SourceResolutionTests(unittest.TestCase):
    def test_resolve_package_root_and_parse_github_source_validate_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(_source.resolve_package_root(tmpdir), Path(tmpdir).resolve())

        with self.assertRaises(LifecycleCommandError):
            _source.resolve_package_root("/path/that/does/not/exist")
        self.assertEqual(_source.parse_github_source("github:owner/repo"), ("owner", "repo"))
        with self.assertRaises(LifecycleCommandError):
            _source.parse_github_source("github:owner/repo/extra")

    def test_get_cache_root_honors_environment_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch.dict(os.environ, {"XANAD_PKG_CACHE": tmpdir}):
            self.assertEqual(_source.get_cache_root(), Path(tmpdir).resolve())

    def test_resolve_effective_package_root_uses_package_root_and_inferred_git_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._source._detect_git_source_info",
            return_value={"source": "github:owner/repo", "ref": "main"},
        ):
            package_root, info = _source.resolve_effective_package_root(tmpdir, None, None, None)

        self.assertEqual(package_root, Path(tmpdir).resolve())
        self.assertEqual(info["source"], "github:owner/repo")
        self.assertEqual(info["ref"], "main")

    def test_resolve_effective_package_root_requires_source_when_package_root_absent(self) -> None:
        with self.assertRaises(LifecycleCommandError):
            _source.resolve_effective_package_root(None, None, None, None)

    def test_resolve_workspace_remote_source_and_build_source_summary_cover_remaining_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            resolved = _source.resolve_workspace(str(workspace), create=True)
            self.assertTrue(resolved.exists())

        with tempfile.TemporaryDirectory() as cache_dir, mock.patch.dict(os.environ, {"XANAD_PKG_CACHE": cache_dir}, clear=False), mock.patch(
            "scripts.lifecycle._xanad._source.resolve_github_release",
            return_value=Path(cache_dir) / "release",
        ), mock.patch(
            "scripts.lifecycle._xanad._source.resolve_github_ref",
            return_value=Path(cache_dir) / "ref",
        ):
            release_root, release_info = _source.resolve_effective_package_root(None, "github:owner/repo", "v1.2.3", None)
            ref_root, ref_info = _source.resolve_effective_package_root(None, "github:owner/repo", None, "dev")

        self.assertEqual(release_root, Path(cache_dir) / "release")
        self.assertEqual(release_info["kind"], "github-release")
        self.assertEqual(ref_root, Path(cache_dir) / "ref")
        self.assertEqual(ref_info["kind"], "github-ref")

        with mock.patch("scripts.lifecycle._xanad._source._State.session_source_info", {"kind": "github-ref", "source": "github:owner/repo"}):
            self.assertEqual(_source.build_source_summary(Path("/pkg"))["source"], "github:owner/repo")

    def test_parse_remote_url_and_git_detection_cover_success_and_failure_paths(self) -> None:
        self.assertEqual(_source._parse_github_remote_url("https://github.com/owner/repo.git"), "github:owner/repo")
        self.assertEqual(_source._parse_github_remote_url("ssh://git@github.com/owner/repo"), "github:owner/repo")
        self.assertEqual(_source._parse_github_remote_url("git@github.com:owner/repo.git"), "github:owner/repo")
        self.assertIsNone(_source._parse_github_remote_url("https://gitlab.com/owner/repo"))

        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._source.subprocess.run",
            side_effect=[
                mock.Mock(returncode=0, stdout="git@github.com:owner/repo.git\n"),
                mock.Mock(returncode=0, stdout="main\n"),
            ],
        ):
            detected = _source._detect_git_source_info(Path(tmpdir))

        self.assertEqual(detected, {"source": "github:owner/repo", "ref": "main"})

        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "scripts.lifecycle._xanad._source.subprocess.run",
            side_effect=OSError("git missing"),
        ):
            self.assertEqual(_source._detect_git_source_info(Path(tmpdir)), {})

    def test_parse_github_source_rejects_invalid_owner_repo_characters(self) -> None:
        with self.assertRaises(LifecycleCommandError):
            _source.parse_github_source("gitlab:owner/repo")
        with self.assertRaises(LifecycleCommandError):
            _source.parse_github_source("github:bad owner/repo")


class StateParsingTests(unittest.TestCase):
    def test_lockfile_path_git_state_and_install_state_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            github_dir = workspace / ".github"
            github_dir.mkdir()
            legacy_lockfile = github_dir / "xanad-assistant-lock.json"
            legacy_lockfile.write_text("{}", encoding="utf-8")

            self.assertEqual(_state._resolve_lockfile_path(workspace), legacy_lockfile)

            self.assertEqual(_state.detect_git_state(workspace), {"present": False, "dirty": None})
            (workspace / ".git").mkdir()
            with mock.patch("scripts.lifecycle._xanad._state.subprocess.run", return_value=mock.Mock(returncode=0, stdout=" M file\n")):
                self.assertEqual(_state.detect_git_state(workspace), {"present": True, "dirty": True})

            install_state, details = _state.determine_install_state(workspace)
            self.assertEqual(install_state, "installed")
            self.assertTrue(details["lockfile"].endswith("xanad-assistant-lock.json"))

    def test_package_name_and_lockfile_status_helpers_cover_missing_and_malformed(self) -> None:
        self.assertIsNone(_state.get_lockfile_package_name({"data": {}}))
        self.assertIsNone(_state.get_predecessor_package_name({"data": {"package": {"name": "xanadAssistant"}}}))

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            lockfile = workspace / ".github" / "xanadAssistant-lock.json"
            lockfile.parent.mkdir(parents=True)
            lockfile.write_text("{bad", encoding="utf-8")

            status = _state.read_lockfile_status(workspace)
            parsed = _state.parse_lockfile_state(workspace)

        self.assertTrue(status["present"])
        self.assertTrue(status["malformed"])
        self.assertTrue(parsed["malformed"])

    def test_parse_legacy_version_file_supports_json_fence_and_plain_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            github_dir = workspace / ".github"
            github_dir.mkdir()
            legacy = github_dir / "copilot-version.md"
            legacy.write_text("```json\n{\"version\": \"1.0.0\"}\n```\n", encoding="utf-8")
            json_result = _state.parse_legacy_version_file(workspace)
            legacy.write_text("Version: 2.0.0\n", encoding="utf-8")
            plain_result = _state.parse_legacy_version_file(workspace)

        self.assertEqual(json_result["data"]["version"], "1.0.0")
        self.assertEqual(plain_result["data"]["version"], "2.0.0")

    def test_parse_lockfile_state_marks_migration_and_preserves_original_package_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            lockfile = workspace / ".github" / "xanadAssistant-lock.json"
            lockfile.parent.mkdir(parents=True)
            lockfile.write_text(
                json.dumps({"package": {"name": "copilot-instructions-template"}, "manifest": {}, "files": []}),
                encoding="utf-8",
            )

            result = _state.parse_lockfile_state(workspace)

        self.assertTrue(result["present"])
        self.assertTrue(result["needsMigration"])
        self.assertEqual(result["originalPackageName"], "copilot-instructions-template")
        self.assertEqual(result["data"]["package"]["name"], _state.CURRENT_PACKAGE_NAME)

    def test_detect_existing_surfaces_and_manifest_summary_report_presence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / ".github" / "agents").mkdir(parents=True)
            (workspace / ".github" / "agents" / "cleaner.agent.md").write_text("x", encoding="utf-8")
            (workspace / ".vscode").mkdir()
            (workspace / ".vscode" / "mcp.json").write_text("{}", encoding="utf-8")
            (workspace / ".copilot" / "workspace").mkdir(parents=True)
            (workspace / ".copilot" / "workspace" / "rule.md").write_text("x", encoding="utf-8")
            (workspace / ".github" / "managed.md").write_text("x", encoding="utf-8")

            surfaces = _state.detect_existing_surfaces(workspace)
            summary = _state.summarize_manifest_targets(
                workspace,
                {
                    "managedFiles": [
                        {"target": ".github/managed.md"},
                        {"target": ".github/missing.md"},
                        {"target": ".github/skipped.md", "status": "skipped"},
                    ],
                    "retiredFiles": [{"target": ".github/old.md"}],
                },
            )

        self.assertEqual(surfaces["agents"]["count"], 1)
        self.assertTrue(surfaces["mcp"]["present"])
        self.assertEqual(summary, {"declared": 3, "present": 1, "missing": 1, "skipped": 1, "retired": 1})

    def test_count_files_and_manifest_summary_cover_empty_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            empty_dir = workspace / "empty"
            empty_dir.mkdir()

            self.assertEqual(_state.count_files(empty_dir), 0)
            self.assertEqual(_state.summarize_manifest_targets(workspace, None), {"declared": 0, "present": 0, "missing": 0, "skipped": 0, "retired": 0})


if __name__ == "__main__":
    unittest.main()