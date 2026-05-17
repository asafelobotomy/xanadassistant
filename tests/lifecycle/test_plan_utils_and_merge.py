from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad import _merge
from scripts.lifecycle._xanad import _plan_utils
from scripts.lifecycle._xanad._errors import _State


class PlanUtilsAndMergeTests(unittest.TestCase):
    def test_expected_entry_bytes_handles_token_replace_merge_json_and_markdown_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            package_root = root / "package"
            workspace = root / "workspace"
            package_root.mkdir()
            workspace.mkdir()

            token_source = package_root / "token.md"
            token_source.write_text("hello {{NAME}}\n", encoding="utf-8")
            json_source = package_root / "config.json"
            json_source.write_text(json.dumps({"a": 1, "nested": {"b": 2}}), encoding="utf-8")
            markdown_source = package_root / "instructions.md"
            markdown_source.write_text("# Title\n\nBase\n", encoding="utf-8")

            json_target = workspace / "config.json"
            json_target.write_text(json.dumps({"nested": {"keep": True}}), encoding="utf-8")
            markdown_target = workspace / "instructions.md"
            markdown_target.write_text(
                "# Title\n\nOld\n\n<!-- user-added -->note<!-- /user-added -->\n",
                encoding="utf-8",
            )

            token_bytes = _plan_utils.expected_entry_bytes(
                package_root,
                {"source": "token.md", "strategy": "token-replace"},
                {"{{NAME}}": "world"},
            )
            json_bytes = _plan_utils.expected_entry_bytes(
                package_root,
                {"source": "config.json", "strategy": "merge-json-object"},
                {},
                json_target,
            )
            markdown_bytes = _plan_utils.expected_entry_bytes(
                package_root,
                {"source": "instructions.md", "strategy": "preserve-marked-markdown-blocks"},
                {},
                markdown_target,
            )

        self.assertEqual(token_bytes, b"hello world\n")
        self.assertEqual(json.loads(json_bytes.decode("utf-8")), {"nested": {"keep": True, "b": 2}, "a": 1})
        self.assertIn("<!-- user-added -->note<!-- /user-added -->", markdown_bytes.decode("utf-8"))

    def test_build_backup_plan_and_planned_lockfile_capture_actions(self) -> None:
        original = _State.session_source_info
        _State.session_source_info = {
            "packageRoot": "/tmp/package",
            "version": "1.2.3",
            "source": "package-root",
        }
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                package_root = root / "package"
                workspace = root / "workspace"
                (package_root / "template").mkdir(parents=True)
                (workspace / ".github" / "prompts").mkdir(parents=True)
                (package_root / "template" / "main.prompt.md").write_text("prompt\n", encoding="utf-8")
                (workspace / ".github" / "prompts" / "main.prompt.md").write_text("existing\n", encoding="utf-8")

                backup_plan = _plan_utils.build_backup_plan(
                    {"retiredFilePolicy": {"archiveRoot": ".xanad/archive"}},
                    [
                        {"target": ".github/prompts/main.prompt.md", "action": "replace"},
                        {"target": ".github/agents/custom.agent.md", "action": "delete"},
                        {"target": ".github/prompts/old.prompt.md", "action": "archive-retired", "strategy": "archive-retired"},
                    ],
                    True,
                )
                context = {
                    "manifest": {
                        "schemaVersion": "0.1.0",
                        "managedFiles": [
                            {
                                "id": "prompts.main",
                                "target": ".github/prompts/main.prompt.md",
                                "source": "template/main.prompt.md",
                                "strategy": "replace",
                                "hash": "sha256:source",
                            }
                        ],
                        "retiredFiles": [],
                    },
                    "packageRoot": package_root,
                }
                planned = _plan_utils.build_planned_lockfile(
                    workspace,
                    context,
                    {"prompts": "local"},
                    {"profile.selected": "balanced", "mcp.enabled": True, "resolvedTokenConflicts.voice": "docs"},
                    {},
                    [{"id": "prompts.main", "target": ".github/prompts/main.prompt.md", "action": "replace", "ownershipMode": "local"}],
                    [{"target": ".github/mcp/scripts/gitMcp.py"}],
                    [".github/prompts/old.prompt.md"],
                    backup_plan,
                    consumer_resolutions={".github/prompts/main.prompt.md": "keep"},
                )
        finally:
            _State.session_source_info = original

        contents = planned["contents"]
        self.assertEqual(contents["package"]["name"], "xanadAssistant")
        self.assertEqual(contents["package"]["version"], "1.2.3")
        self.assertEqual(contents["installMetadata"]["mcpEnabled"], True)
        self.assertEqual(contents["resolvedTokenConflicts"], {"voice": "docs"})
        self.assertEqual(contents["consumerResolutions"], {".github/prompts/main.prompt.md": "keep"})
        self.assertEqual(contents["skippedManagedFiles"], [".github/mcp/scripts/gitMcp.py"])
        self.assertEqual(contents["lastBackup"]["path"], ".xanadAssistant/backups/<apply-timestamp>")

    def test_merge_helpers_preserve_blocks_and_nested_json(self) -> None:
        merged_json = _merge.merge_json_objects({"a": {"keep": True}}, {"a": {"set": 1}, "b": 2})
        merged_markdown = _merge.merge_markdown_with_preserved_blocks(
            "# Title\n\n## §10 - Project-Specific Overrides\nKeep me\n",
            "# Title\n\nBase\n",
        )

        self.assertEqual(merged_json, {"a": {"keep": True, "set": 1}, "b": 2})
        self.assertIn("## §10 - Project-Specific Overrides", merged_markdown)


if __name__ == "__main__":
    unittest.main()