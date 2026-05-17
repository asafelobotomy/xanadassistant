from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _plan_a
from scripts.lifecycle._xanad._errors import LifecycleCommandError


class PlanActionHelpersTests(unittest.TestCase):
    def test_resolve_ownership_by_surface_uses_existing_answers_and_defaults(self) -> None:
        policy = {"ownershipDefaults": {"agents": "plugin-backed-copilot-format"}}
        manifest = {
            "managedFiles": [
                {
                    "id": "agents.cleaner",
                    "surface": "agents",
                    "ownership": ["local", "plugin-backed-copilot-format"],
                },
                {
                    "id": "instructions.main",
                    "surface": "instructions",
                    "ownership": ["local"],
                },
            ]
        }

        result = _plan_a.resolve_ownership_by_surface(
            policy,
            manifest,
            {"ownershipBySurface": {"instructions": "local"}},
            {"ownership.agents": "plugin-backed-copilot-format"},
        )

        self.assertEqual(
            result,
            {
                "agents": "plugin-backed-copilot-format",
                "instructions": "local",
            },
        )

    def test_resolve_ownership_by_surface_handles_missing_manifest_and_canonical_fallback(self) -> None:
        self.assertEqual(_plan_a.resolve_ownership_by_surface({}, None, {}, {}), {})

        manifest = {
            "managedFiles": [
                {
                    "id": "agents.cleaner",
                    "surface": "agent-files",
                    "ownership": ["local", "plugin-backed-copilot-format"],
                }
            ]
        }
        result = _plan_a.resolve_ownership_by_surface(
            {"ownershipDefaults": {"agents": "local"}},
            manifest,
            {"ownershipBySurface": {"agents": "plugin-backed-copilot-format"}},
            {},
        )
        self.assertEqual(result, {"agent-files": "plugin-backed-copilot-format"})

    def test_resolve_ownership_by_surface_rejects_unsupported_mode(self) -> None:
        with self.assertRaises(LifecycleCommandError):
            _plan_a.resolve_ownership_by_surface(
                {},
                {"managedFiles": [{"id": "agents.cleaner", "surface": "agents", "ownership": ["local"]}]},
                {},
                {"ownership.agents": "plugin-backed-copilot-format"},
            )

    def test_build_setup_plan_actions_covers_add_replace_skip_and_retired(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            (package_root / "template").mkdir(parents=True)
            (workspace / ".github" / "prompts").mkdir(parents=True)
            (workspace / ".github" / "mcp" / "scripts").mkdir(parents=True)

            source_file = package_root / "template" / "prompt.md"
            source_file.write_text("hello {{NAME}}\n", encoding="utf-8")
            existing_target = workspace / ".github" / "prompts" / "managed.prompt.md"
            existing_target.write_text("outdated\n", encoding="utf-8")
            copy_if_missing_target = workspace / ".github" / "mcp" / "scripts" / "gitMcp.py"
            copy_if_missing_target.write_text("existing\n", encoding="utf-8")
            retired_target = workspace / ".github" / "prompts" / "retired.prompt.md"
            retired_target.write_text("legacy\n", encoding="utf-8")

            manifest = {
                "managedFiles": [
                    {
                        "id": "prompts.managed",
                        "surface": "prompts",
                        "target": ".github/prompts/managed.prompt.md",
                        "source": "template/prompt.md",
                        "strategy": "token-replace",
                        "tokens": ["{{NAME}}"],
                        "ownership": ["local"],
                    },
                    {
                        "id": "prompts.extra",
                        "surface": "prompts",
                        "target": ".github/prompts/extra.prompt.md",
                        "source": "template/prompt.md",
                        "strategy": "token-replace",
                        "tokens": ["{{NAME}}"],
                        "ownership": ["local"],
                    },
                    {
                        "id": "hooks.git",
                        "surface": "hooks",
                        "target": ".github/mcp/scripts/gitMcp.py",
                        "source": "template/prompt.md",
                        "strategy": "copy-if-missing",
                        "tokens": [],
                        "ownership": ["local"],
                    },
                    {
                        "id": "agents.cleaner",
                        "surface": "agents",
                        "target": ".github/agents/cleaner.agent.md",
                        "source": "template/prompt.md",
                        "strategy": "replace",
                        "tokens": [],
                        "requiredWhen": ["mcp.enabled=true"],
                        "ownership": ["local", "plugin-backed-copilot-format"],
                    },
                ],
                "retiredFiles": [{"id": "retired.prompt", "target": ".github/prompts/retired.prompt.md"}],
            }

            writes, actions, skipped_actions, retired_targets = _plan_a.build_setup_plan_actions(
                workspace,
                package_root,
                manifest,
                {"prompts": "local", "hooks": "local", "agents": "plugin-backed-copilot-format"},
                {"mcp.enabled": False},
                {"{{NAME}}": "demo"},
            )

        self.assertEqual(writes, {"add": 1, "replace": 1, "merge": 0, "archiveRetired": 1})
        self.assertEqual(
            {action["target"]: action["action"] for action in actions},
            {
                ".github/prompts/managed.prompt.md": "replace",
                ".github/prompts/extra.prompt.md": "add",
                ".github/prompts/retired.prompt.md": "archive-retired",
            },
        )
        self.assertEqual(retired_targets, [".github/prompts/retired.prompt.md"])
        self.assertEqual({entry["reason"] for entry in skipped_actions}, {"copy-if-missing-present", "plugin-backed-ownership"})

    def test_build_setup_plan_actions_covers_manifest_none_force_reinstall_and_missing_tokens(self) -> None:
        writes, actions, skipped_actions, retired_targets = _plan_a.build_setup_plan_actions(
            Path("."),
            Path("."),
            None,
            {},
            {},
            {},
        )
        self.assertEqual((writes, actions, skipped_actions, retired_targets), ({"add": 0, "replace": 0, "merge": 0, "archiveRetired": 0}, [], [], []))

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            (package_root / "template").mkdir()
            source = package_root / "template" / "config.json"
            source.write_text(json.dumps({"setting": True}), encoding="utf-8")
            target = workspace / ".github" / "settings.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"setting": False}), encoding="utf-8")

            manifest = {
                "managedFiles": [
                    {
                        "id": "config.main",
                        "surface": "config",
                        "target": ".github/settings.json",
                        "source": "template/config.json",
                        "strategy": "merge-json-object",
                        "tokens": ["{{MISSING}}"],
                        "ownership": ["local"],
                    },
                    {
                        "id": "hooks.git",
                        "surface": "hooks",
                        "target": ".github/mcp/scripts/gitMcp.py",
                        "source": "template/config.json",
                        "strategy": "copy-if-missing",
                        "tokens": [],
                        "ownership": ["local"],
                    },
                ],
                "retiredFiles": [],
            }

            writes, actions, skipped_actions, retired_targets = _plan_a.build_setup_plan_actions(
                workspace,
                package_root,
                manifest,
                {"config": "local", "hooks": "local"},
                {},
                {},
                force_reinstall=True,
            )

        self.assertEqual(writes, {"add": 1, "replace": 0, "merge": 1, "archiveRetired": 0})
        self.assertEqual(retired_targets, [])
        self.assertEqual(actions[0]["action"], "merge")
        self.assertEqual(actions[0]["missingTokenValues"], ["{{MISSING}}"])
        self.assertEqual(actions[1]["action"], "add")
        self.assertEqual(skipped_actions, [])

    def test_build_setup_plan_actions_skips_already_matching_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            workspace = root / "workspace"
            package_root = root / "package"
            workspace.mkdir()
            package_root.mkdir()
            (package_root / "template").mkdir()
            source = package_root / "template" / "prompt.md"
            source.write_text("hello\n", encoding="utf-8")
            target = workspace / ".github" / "prompts" / "managed.prompt.md"
            target.parent.mkdir(parents=True)
            target.write_text("hello\n", encoding="utf-8")

            manifest = {
                "managedFiles": [
                    {
                        "id": "prompts.managed",
                        "surface": "prompts",
                        "target": ".github/prompts/managed.prompt.md",
                        "source": "template/prompt.md",
                        "strategy": "replace",
                        "tokens": [],
                        "ownership": ["local"],
                    }
                ],
                "retiredFiles": [],
            }

            writes, actions, skipped_actions, retired_targets = _plan_a.build_setup_plan_actions(
                workspace,
                package_root,
                manifest,
                {"prompts": "local"},
                {},
                {},
            )

        self.assertEqual(writes, {"add": 0, "replace": 0, "merge": 0, "archiveRetired": 0})
        self.assertEqual(actions, [])
        self.assertEqual(skipped_actions, [])
        self.assertEqual(retired_targets, [])

    def test_classify_plan_conflicts_reports_drift_unmanaged_and_retired_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / ".github" / "mcp" / "scripts").mkdir(parents=True)
            (workspace / ".github" / "mcp" / "scripts" / "custom.py").write_text("x", encoding="utf-8")
            context = {
                "warnings": [],
                "manifest": {"managedFiles": [{"target": ".github/mcp/scripts/gitMcp.py"}]},
                "legacyVersionState": {"malformed": True},
                "lockfileState": {"malformed": False},
            }

            conflicts, warnings = _plan_a.classify_plan_conflicts(
                workspace,
                context,
                [{"target": ".github/mcp/scripts/gitMcp.py", "action": "replace"}],
                [".github/prompts/retired.prompt.md"],
            )

        self.assertEqual(
            _plan_a.build_conflict_summary(conflicts),
            {
                "managed-drift": 1,
                "unmanaged-lookalike": 1,
                "malformed-managed-state": 1,
                "retired-file-present": 1,
            },
        )
        self.assertEqual({warning["code"] for warning in warnings}, {"managed_drift", "unmanaged_lookalike", "malformed_managed_state", "retired_file_present"})

    def test_write_plan_output_persists_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "plans" / "plan.json"
            written_path = _plan_a.write_plan_output(str(output), {"status": "ok"})

            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"status": "ok"})
            self.assertEqual(written_path, str(output.resolve()))

    def test_verify_manifest_integrity_covers_short_circuits_mismatch_and_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)

            self.assertEqual(_plan_a.verify_manifest_integrity(package_root, {"present": False}), (True, None))
            self.assertEqual(_plan_a.verify_manifest_integrity(package_root, {"present": True, "malformed": True}), (True, None))
            self.assertEqual(_plan_a.verify_manifest_integrity(package_root, {"present": True, "malformed": False, "data": []}), (True, None))
            self.assertEqual(_plan_a.verify_manifest_integrity(package_root, {"present": True, "malformed": False, "data": {"manifest": {}}}), (True, None))

            with mock.patch(
                "scripts.lifecycle._xanad._plan_a.load_optional_json",
                return_value=None,
            ):
                self.assertEqual(
                    _plan_a.verify_manifest_integrity(
                        package_root,
                        {"present": True, "malformed": False, "data": {"manifest": {"hash": "sha256:old"}}},
                    ),
                    (True, None),
                )

            with mock.patch(
                "scripts.lifecycle._xanad._plan_a.load_optional_json",
                return_value={"generationSettings": {}},
            ), mock.patch(
                "scripts.lifecycle._xanad._plan_a.load_manifest",
                return_value=None,
            ):
                self.assertEqual(
                    _plan_a.verify_manifest_integrity(
                        package_root,
                        {"present": True, "malformed": False, "data": {"manifest": {"hash": "sha256:old"}}},
                    ),
                    (False, "Manifest not found at resolved package root."),
                )

            with mock.patch(
                "scripts.lifecycle._xanad._plan_a.load_optional_json",
                return_value={"generationSettings": {}},
            ), mock.patch(
                "scripts.lifecycle._xanad._plan_a.load_manifest",
                return_value={"managedFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._plan_a.sha256_json",
                return_value="sha256:new",
            ):
                ok, reason = _plan_a.verify_manifest_integrity(
                    package_root,
                    {"present": True, "malformed": False, "data": {"manifest": {"hash": "sha256:old"}}},
                )
                self.assertFalse(ok)
                self.assertIn("Manifest hash mismatch", reason)

            with mock.patch(
                "scripts.lifecycle._xanad._plan_a.load_optional_json",
                return_value={"generationSettings": {}},
            ), mock.patch(
                "scripts.lifecycle._xanad._plan_a.load_manifest",
                return_value={"managedFiles": []},
            ), mock.patch(
                "scripts.lifecycle._xanad._plan_a.sha256_json",
                return_value="sha256:match",
            ):
                self.assertEqual(
                    _plan_a.verify_manifest_integrity(
                        package_root,
                        {"present": True, "malformed": False, "data": {"manifest": {"hash": "sha256:match"}}},
                    ),
                    (True, None),
                )


if __name__ == "__main__":
    unittest.main()