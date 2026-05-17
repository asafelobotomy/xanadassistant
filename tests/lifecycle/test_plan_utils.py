from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad import _plan_utils
from scripts.lifecycle._xanad._errors import _State


class PlanUtilsTests(unittest.TestCase):
    def test_expected_entry_bytes_covers_render_merge_markdown_and_default_strategies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            package_root = root / "package"
            package_root.mkdir()

            (package_root / "tokens.txt").write_text("Hello {{NAME}}\n", encoding="utf-8")
            rendered = _plan_utils.expected_entry_bytes(
                package_root,
                {"source": "tokens.txt", "strategy": "token-replace"},
                {"{{NAME}}": "World"},
            )
            self.assertEqual(rendered, b"Hello World\n")

            (package_root / "config.json").write_text(json.dumps({"setting": True}), encoding="utf-8")
            merged_missing_target = _plan_utils.expected_entry_bytes(
                package_root,
                {"source": "config.json", "strategy": "merge-json-object"},
                {},
                root / "missing.json",
            )
            self.assertEqual(json.loads(merged_missing_target.decode("utf-8")), {"setting": True})

            bad_source = package_root / "bad.json"
            bad_source.write_text("[]", encoding="utf-8")
            self.assertIsNone(
                _plan_utils.expected_entry_bytes(
                    package_root,
                    {"source": "bad.json", "strategy": "merge-json-object"},
                    {},
                    root / "target.json",
                )
            )

            target = root / "target.json"
            target.write_text("{invalid", encoding="utf-8")
            self.assertIsNone(
                _plan_utils.expected_entry_bytes(
                    package_root,
                    {"source": "config.json", "strategy": "merge-json-object"},
                    {},
                    target,
                )
            )

            (package_root / "doc.md").write_text("# Title\n\nBody\n", encoding="utf-8")
            doc_target = root / "doc.md"
            doc_target.write_text("# Title\n\n<!-- user-added -->Keep<!-- /user-added -->\n", encoding="utf-8")
            merged_markdown = _plan_utils.expected_entry_bytes(
                package_root,
                {"source": "doc.md", "strategy": "preserve-marked-markdown-blocks"},
                {},
                doc_target,
            )
            self.assertIn(b"<!-- user-added -->Keep<!-- /user-added -->", merged_markdown)

            plain = package_root / "plain.bin"
            plain.write_bytes(b"abc")
            self.assertEqual(
                _plan_utils.expected_entry_bytes(package_root, {"source": "plain.bin"}, {}, None),
                b"abc",
            )

    def test_expected_entry_hash_and_token_summary_cover_none_required_and_sorted_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            (package_root / "bad.json").write_text("[]", encoding="utf-8")
            self.assertIsNone(
                _plan_utils.expected_entry_hash(
                    package_root,
                    {"source": "bad.json", "strategy": "merge-json-object"},
                    {},
                )
            )

        summary = _plan_utils.build_token_plan_summary(
            {"tokenRules": [{"token": "VOICE", "required": True}, {"token": "STYLE", "required": False}]},
            [
                {"target": "b.txt", "tokens": ["STYLE", "VOICE"]},
                {"target": "a.txt", "tokens": ["VOICE"]},
            ],
            {"VOICE": "balanced", "STYLE": "plain"},
        )

        self.assertEqual(summary[0], {"token": "STYLE", "value": "plain", "required": False, "targets": ["b.txt"]})
        self.assertEqual(summary[1], {"token": "VOICE", "value": "balanced", "required": True, "targets": ["a.txt", "b.txt"]})

    def test_build_backup_plan_covers_disabled_and_archive_reporting_branches(self) -> None:
        disabled = _plan_utils.build_backup_plan({"retiredFilePolicy": {"archiveRoot": ".xanad/archive"}}, [], False)
        self.assertFalse(disabled["required"])
        self.assertEqual(disabled["archiveRoot"], ".xanad/archive")

        backup = _plan_utils.build_backup_plan(
            {"retiredFilePolicy": {"archiveRoot": ".xanad/archive"}},
            [
                {"target": "replace.txt", "action": "replace"},
                {"target": "delete.txt", "action": "delete"},
                {"target": "archive.txt", "action": "archive-retired"},
                {"target": "report.txt", "action": "archive-retired", "strategy": "report-retired"},
            ],
            True,
        )

        self.assertTrue(backup["required"])
        self.assertEqual(backup["targets"][0]["backupPath"], ".xanadAssistant/backups/<apply-timestamp>/replace.txt")
        self.assertEqual(backup["targets"][1]["backupPath"], ".xanadAssistant/backups/<apply-timestamp>/delete.txt")
        self.assertEqual(backup["archiveTargets"], [{"target": "archive.txt", "archivePath": ".xanad/archive/archive.txt"}])

    def test_build_planned_lockfile_records_files_retired_entries_and_session_source_info(self) -> None:
        previous = _State.session_source_info
        try:
            _State.session_source_info = {
                "packageRoot": "/tmp/pkg",
                "version": "1.2.3",
                "source": "github:owner/repo",
                "ref": "main",
            }
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                workspace = root / "workspace"
                package_root = root / "package"
                workspace.mkdir()
                package_root.mkdir()

                template = package_root / "template"
                template.mkdir()
                (template / "prompt.md").write_text("Prompt\n", encoding="utf-8")
                existing_target = workspace / ".github" / "prompts" / "main.prompt.md"
                existing_target.parent.mkdir(parents=True)
                existing_target.write_text("Old prompt\n", encoding="utf-8")

                context = {
                    "packageRoot": package_root,
                    "manifest": {
                        "schemaVersion": "0.1.0",
                        "managedFiles": [
                            {
                                "id": "prompts.main",
                                "target": ".github/prompts/main.prompt.md",
                                "source": "template/prompt.md",
                                "hash": "sha256:source",
                            }
                        ],
                        "retiredFiles": [],
                    },
                }
                actions = [
                    {
                        "id": "prompts.main",
                        "target": ".github/prompts/main.prompt.md",
                        "action": "replace",
                        "ownershipMode": "local",
                    },
                    {
                        "id": "retired.prompt",
                        "target": ".github/prompts/old.prompt.md",
                        "action": "archive-retired",
                    },
                    {
                        "id": "retired.report",
                        "target": ".github/prompts/reported.prompt.md",
                        "action": "archive-retired",
                    },
                ]
                backup_plan = {
                    "required": True,
                    "root": ".xanadAssistant/backups/<apply-timestamp>",
                    "archiveTargets": [{
                        "target": ".github/prompts/old.prompt.md",
                        "archivePath": ".xanad/archive/.github/prompts/old.prompt.md",
                    }],
                }

                result = _plan_utils.build_planned_lockfile(
                    workspace,
                    context,
                    {"prompts": "local"},
                    {
                        "packs.selected": ["docs"],
                        "profile.selected": "balanced",
                        "mcp.enabled": True,
                        "resolvedTokenConflicts.voice": "docs",
                    },
                    {},
                    actions,
                    [{"target": ".github/mcp/scripts/gitMcp.py"}],
                    [".github/prompts/old.prompt.md"],
                    backup_plan,
                    consumer_resolutions={".github/prompts/main.prompt.md": "keep"},
                )

            lockfile = result["contents"]
            self.assertEqual(result["path"], ".github/xanadAssistant-lock.json")
            self.assertEqual(lockfile["package"]["packageRoot"], "/tmp/pkg")
            self.assertEqual(lockfile["package"]["version"], "1.2.3")
            self.assertEqual(lockfile["selectedPacks"], ["docs"])
            self.assertEqual(lockfile["profile"], "balanced")
            self.assertEqual(lockfile["resolvedTokenConflicts"], {"voice": "docs"})
            self.assertTrue(lockfile["installMetadata"]["mcpEnabled"])
            self.assertEqual(lockfile["consumerResolutions"], {".github/prompts/main.prompt.md": "keep"})
            self.assertEqual(lockfile["skippedManagedFiles"], [".github/mcp/scripts/gitMcp.py"])
            self.assertEqual(lockfile["retiredManagedFiles"][0]["action"], "archived")
            self.assertEqual(lockfile["retiredManagedFiles"][0]["archivePath"], ".xanad/archive/.github/prompts/old.prompt.md")
            self.assertEqual(lockfile["retiredManagedFiles"][1]["action"], "reported")
            self.assertEqual(lockfile["files"][0]["status"], "applied")
            self.assertEqual(lockfile["ownershipBySurface"], {"prompts": "local"})
            self.assertEqual(lockfile["lastBackup"], {"path": ".xanadAssistant/backups/<apply-timestamp>"})
        finally:
            _State.session_source_info = previous


if __name__ == "__main__":
    unittest.main()