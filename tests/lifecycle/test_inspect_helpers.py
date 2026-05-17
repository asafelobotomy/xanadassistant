from __future__ import annotations

import tempfile
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._inspect_helpers import (
    annotate_manifest_entries,
    classify_manifest_entries,
    collect_successor_migration_files,
    collect_unmanaged_files,
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
