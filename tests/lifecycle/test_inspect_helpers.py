from __future__ import annotations

import tempfile
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._inspect_helpers import (
    annotate_manifest_entries,
    classify_manifest_entries,
    collect_sanitizable_unmanaged_files,
    collect_successor_migration_files,
    collect_unmanaged_files,
    is_copilot_shaped_unmanaged_path,
)


class CollectUnmanagedFilesTests(unittest.TestCase):
    def _minimal_manifest(self) -> dict:
        return {"retiredFiles": [], "files": []}

    def test_pycache_files_are_not_reported_as_unmanaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            hooks_dir = workspace / ".github" / "mcp" / "scripts"
            hooks_dir.mkdir(parents=True)

            managed = hooks_dir / "gitMcp.py"
            managed.write_text("# managed\n")
            managed_target = ".github/mcp/scripts/gitMcp.py"

            pycache_dir = hooks_dir / "__pycache__"
            pycache_dir.mkdir()
            (pycache_dir / "gitMcp.cpython-314.pyc").write_bytes(b"\x00")

            result = collect_unmanaged_files(
                workspace,
                self._minimal_manifest(),
                {managed_target},
            )

        self.assertNotIn(".github/mcp/scripts/__pycache__/gitMcp.cpython-314.pyc", result)
        self.assertEqual(result, [])

    def test_genuine_unmanaged_files_are_still_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            hooks_dir = workspace / ".github" / "mcp" / "scripts"
            hooks_dir.mkdir(parents=True)

            managed = hooks_dir / "gitMcp.py"
            managed.write_text("# managed\n")
            managed_target = ".github/mcp/scripts/gitMcp.py"

            lookalike = hooks_dir / "myCustomScript.py"
            lookalike.write_text("# not managed\n")

            result = collect_unmanaged_files(
                workspace,
                self._minimal_manifest(),
                {managed_target},
            )

        self.assertIn(".github/mcp/scripts/myCustomScript.py", result)

    def test_annotate_manifest_entries_marks_clean_missing_stale_and_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            (package_root / "template").mkdir(parents=True)
            (package_root / "template" / "prompt.md").write_text("hello\n", encoding="utf-8")
            clean_target = workspace / ".github" / "prompts" / "clean.prompt.md"
            stale_target = workspace / ".github" / "prompts" / "stale.prompt.md"
            clean_target.parent.mkdir(parents=True)
            clean_target.write_text("hello\n", encoding="utf-8")
            stale_target.write_text("stale\n", encoding="utf-8")

            manifest = {
                "managedFiles": [
                    {
                        "id": "prompts.clean",
                        "surface": "prompts",
                        "target": ".github/prompts/clean.prompt.md",
                        "source": "template/prompt.md",
                        "strategy": "replace",
                        "ownership": ["local"],
                    },
                    {
                        "id": "prompts.missing",
                        "surface": "prompts",
                        "target": ".github/prompts/missing.prompt.md",
                        "source": "template/prompt.md",
                        "strategy": "replace",
                        "ownership": ["local"],
                    },
                    {
                        "id": "prompts.stale",
                        "surface": "prompts",
                        "target": ".github/prompts/stale.prompt.md",
                        "source": "template/prompt.md",
                        "strategy": "replace",
                        "ownership": ["local"],
                    },
                    {
                        "id": "agents.plugin",
                        "surface": "agents",
                        "target": ".github/agents/plugin.agent.md",
                        "source": "template/prompt.md",
                        "strategy": "replace",
                        "ownership": ["local", "plugin-backed-copilot-format"],
                    },
                ],
                "retiredFiles": [],
            }

            annotated = annotate_manifest_entries(
                workspace,
                package_root,
                manifest,
                {"prompts": "local", "agents": "plugin-backed-copilot-format"},
                {},
                {},
                consumer_resolutions={".github/prompts/stale.prompt.md": "keep"},
            )

        statuses = {entry["id"]: entry["status"] for entry in annotated["managedFiles"]}
        self.assertEqual(statuses["prompts.clean"], "clean")
        self.assertEqual(statuses["prompts.missing"], "missing")
        self.assertEqual(statuses["prompts.stale"], "skipped")
        self.assertEqual(statuses["agents.plugin"], "skipped")

    def test_classify_manifest_entries_and_successor_migration_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            retired_path = workspace / ".github" / "prompts" / "retired.prompt.md"
            cleanup_path = workspace / ".github" / "skills" / "legacy.skill.md"
            retired_path.parent.mkdir(parents=True)
            cleanup_path.parent.mkdir(parents=True)
            retired_path.write_text("old\n", encoding="utf-8")
            cleanup_path.write_text("legacy\n", encoding="utf-8")
            manifest = {
                "managedFiles": [
                    {"id": "prompts.clean", "target": ".github/prompts/clean.prompt.md", "status": "clean"},
                    {"id": "prompts.missing", "target": ".github/prompts/missing.prompt.md", "status": "missing"},
                ],
                "retiredFiles": [{"id": "prompts.retired", "target": ".github/prompts/retired.prompt.md"}],
            }

            counts, entries, managed_targets = classify_manifest_entries(workspace, manifest)
            cleanup = collect_successor_migration_files(
                workspace,
                manifest,
                {"originalPackageName": "copilot-instructions-template", "present": True},
                {"present": False},
            )

        self.assertEqual(counts["clean"], 1)
        self.assertEqual(counts["missing"], 1)
        self.assertEqual(counts["retired"], 1)
        self.assertIn(".github/prompts/clean.prompt.md", managed_targets)
        self.assertIn({"id": "prompts.retired", "target": ".github/prompts/retired.prompt.md", "status": "retired"}, entries)
        self.assertEqual(cleanup, [".github/skills/legacy.skill.md"])

    def test_collect_unmanaged_files_skips_symlinked_managed_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside_dir:
            workspace = Path(tmpdir)
            outside = Path(outside_dir)
            (outside / "secret.txt").write_text("outside\n", encoding="utf-8")
            github_dir = workspace / ".github"
            github_dir.mkdir()
            (github_dir / "prompts").symlink_to(outside)
            managed_target = ".github/prompts/main.prompt.md"

            result = collect_unmanaged_files(
                workspace,
                self._minimal_manifest(),
                {managed_target},
            )

        self.assertNotIn(".github/prompts/secret.txt", result)

    def test_collect_successor_migration_files_skips_symlinked_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside_dir:
            workspace = Path(tmpdir)
            outside = Path(outside_dir)
            (outside / "legacy.skill.md").write_text("legacy\n", encoding="utf-8")
            github_dir = workspace / ".github"
            github_dir.mkdir()
            (github_dir / "skills").symlink_to(outside)
            # Place a marker so collect_successor_migration_files enters the scan loop
            (github_dir / "hooks").mkdir()
            (github_dir / "hooks" / "copilot-hooks.json").write_text("{}\n", encoding="utf-8")

            cleanup = collect_successor_migration_files(
                workspace,
                {"managedFiles": [], "retiredFiles": []},
                {"present": False},
                {"present": False},
            )

        self.assertNotIn(".github/skills/legacy.skill.md", cleanup)


class CollectSanitizableUnmanagedFilesTests(unittest.TestCase):
    def _minimal_manifest(self, managed: list[str] | None = None, retired: list[str] | None = None) -> dict:
        return {
            "managedFiles": [{"id": t, "target": t} for t in (managed or [])],
            "retiredFiles": [{"id": t, "target": t} for t in (retired or [])],
        }

    def _minimal_policy(self) -> dict:
        return {"targetPathRules": {}}

    def test_collects_only_copilot_shaped_unmanaged_files_under_managed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            github = workspace / ".github"
            github.mkdir()
            (github / "some.agent.md").write_text("# agent\n")
            (github / "instructions.instructions.md").write_text("# inst\n")
            (github / "SKILL.md").write_text("# skill\n")
            (github / "copilot-instructions.md").write_text("# copilot\n")
            (github / "my.prompt.md").write_text("# prompt\n")
            vscode = workspace / ".vscode"
            vscode.mkdir()
            (vscode / "mcp.json").write_text('{"servers":{}}')
            (github / "unrelated.py").write_text("# unrelated\n")
            (github / "README.md").write_text("# readme\n")

            result = collect_sanitizable_unmanaged_files(workspace, self._minimal_policy(), self._minimal_manifest())

        self.assertIn(".github/some.agent.md", result)
        self.assertIn(".github/instructions.instructions.md", result)
        self.assertIn(".github/SKILL.md", result)
        self.assertIn(".github/copilot-instructions.md", result)
        self.assertIn(".github/my.prompt.md", result)
        self.assertIn(".vscode/mcp.json", result)
        self.assertNotIn(".github/unrelated.py", result)
        self.assertNotIn(".github/README.md", result)

    def test_excludes_manifest_managed_and_retired_targets_and_disallowed_mcp_json_locations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            github = workspace / ".github"
            github.mkdir()
            managed_agent = ".github/managed.agent.md"
            (workspace / managed_agent).write_text("# managed\n")
            retired_agent = ".github/retired.agent.md"
            (workspace / retired_agent).write_text("# retired\n")
            unmanaged_agent = ".github/unmanaged.agent.md"
            (workspace / unmanaged_agent).write_text("# unmanaged\n")
            # mcp.json outside .github/.vscode should not be collected
            other_dir = workspace / "tools"
            other_dir.mkdir()
            (other_dir / "mcp.json").write_text('{"servers":{}}')

            manifest = self._minimal_manifest(managed=[managed_agent], retired=[retired_agent])
            result = collect_sanitizable_unmanaged_files(workspace, self._minimal_policy(), manifest)

        self.assertIn(unmanaged_agent, result)
        self.assertNotIn(managed_agent, result)
        self.assertNotIn(retired_agent, result)
        self.assertNotIn("tools/mcp.json", result)

    def test_is_copilot_shaped_unmanaged_path_matches_expected_patterns(self) -> None:
        self.assertTrue(is_copilot_shaped_unmanaged_path(".github/agents/foo.agent.md"))
        self.assertTrue(is_copilot_shaped_unmanaged_path(".github/prompts/bar.prompt.md"))
        self.assertTrue(is_copilot_shaped_unmanaged_path(".github/instructions/baz.instructions.md"))
        self.assertTrue(is_copilot_shaped_unmanaged_path(".github/skills/mySkill/SKILL.md"))
        self.assertTrue(is_copilot_shaped_unmanaged_path(".github/copilot-instructions.md"))
        self.assertTrue(is_copilot_shaped_unmanaged_path(".vscode/mcp.json"))
        self.assertTrue(is_copilot_shaped_unmanaged_path(".github/mcp.json"))
        self.assertFalse(is_copilot_shaped_unmanaged_path(".github/README.md"))
        self.assertFalse(is_copilot_shaped_unmanaged_path(".github/hooks/myHook.py"))
        self.assertFalse(is_copilot_shaped_unmanaged_path("tools/mcp.json"))
