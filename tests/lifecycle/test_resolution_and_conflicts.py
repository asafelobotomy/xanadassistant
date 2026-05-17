from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad import _pack_conflicts
from scripts.lifecycle._xanad import _resolutions
from scripts.lifecycle._xanad._errors import LifecycleCommandError


class ResolutionAndConflictTests(unittest.TestCase):
    def test_detect_pack_conflicts_and_collect_resolutions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "packs" / "docs").mkdir(parents=True)
            (root / "packs" / "secure").mkdir(parents=True)
            (root / "packs" / "docs" / "tokens.json").write_text(json.dumps({"voice": "docs"}), encoding="utf-8")
            (root / "packs" / "secure" / "tokens.json").write_text(json.dumps({"voice": "secure"}), encoding="utf-8")

            conflicts = _pack_conflicts.detect_pack_token_conflicts(root, ["docs", "secure"])
            questions = _pack_conflicts.build_conflict_questions(conflicts)
            resolutions, unresolved = _pack_conflicts.collect_conflict_resolutions(
                conflicts,
                {"resolvedTokenConflicts": {"voice": "secure"}},
                {},
            )

        self.assertEqual(conflicts[0]["token"], "voice")
        self.assertEqual(questions[0]["id"], "resolvedTokenConflicts.voice")
        self.assertEqual(resolutions, {"voice": "secure"})
        self.assertEqual(unresolved, [])

    def test_pack_conflict_helpers_cover_empty_invalid_and_fallback_resolution_paths(self) -> None:
        self.assertEqual(_pack_conflicts.detect_pack_token_conflicts(Path("."), []), [])

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "packs" / "docs").mkdir(parents=True)
            (root / "packs" / "broken").mkdir(parents=True)
            (root / "packs" / "listy").mkdir(parents=True)
            (root / "packs" / "docs" / "tokens.json").write_text(
                json.dumps({"voice": "docs", "numeric": 1}),
                encoding="utf-8",
            )
            (root / "packs" / "broken" / "tokens.json").write_text("{bad", encoding="utf-8")
            (root / "packs" / "listy" / "tokens.json").write_text("[]", encoding="utf-8")

            conflicts = _pack_conflicts.detect_pack_token_conflicts(root, ["docs", "broken", "listy", "missing"])

        self.assertEqual(conflicts, [])
        self.assertEqual(_pack_conflicts.build_conflict_questions([]), [])

        pack_conflicts = [
            {
                "token": "voice",
                "questionId": "resolvedTokenConflicts.voice",
                "packs": ["docs", "secure"],
                "candidates": {"docs": "docs", "secure": "secure"},
            },
            {
                "token": "tone",
                "questionId": "resolvedTokenConflicts.tone",
                "packs": ["docs", "lean"],
                "candidates": {"docs": "clear", "lean": "brief"},
            },
        ]
        resolutions, unresolved = _pack_conflicts.collect_conflict_resolutions(
            pack_conflicts,
            {"resolvedTokenConflicts": {"voice": "secure", "tone": "invalid"}},
            {"resolvedTokenConflicts.voice": "docs", "resolvedTokenConflicts.tone": None},
        )

        self.assertEqual(resolutions, {"voice": "docs"})
        self.assertEqual(unresolved, ["resolvedTokenConflicts.tone"])

        resolutions, unresolved = _pack_conflicts.collect_conflict_resolutions(
            pack_conflicts,
            {"resolvedTokenConflicts": []},
            {},
        )
        self.assertEqual(resolutions, {})
        self.assertEqual(unresolved, ["resolvedTokenConflicts.voice", "resolvedTokenConflicts.tone"])

    def test_resolution_helpers_validate_apply_and_build_delete_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            delete_target = workspace / ".github" / "mcp" / "scripts" / "custom.py"
            delete_target.parent.mkdir(parents=True)
            delete_target.write_text("x", encoding="utf-8")
            resolutions_file = workspace / "resolutions.json"
            resolutions_file.write_text(
                json.dumps({
                    ".github/mcp/scripts/custom.py": "remove",
                    ".github/instructions/main.instructions.md": "merge",
                    ".github/unknown.md": "keep",
                }),
                encoding="utf-8",
            )

            loaded = _resolutions.load_resolutions(str(resolutions_file))
            valid, warnings = _resolutions.validate_resolutions(
                loaded,
                [
                    {"path": ".github/mcp/scripts/custom.py", "type": "unmanaged", "surface": "hooks", "availableDecisions": ["keep", "remove"]},
                    {"path": ".github/instructions/main.instructions.md", "type": "collision", "surface": "instructions", "availableDecisions": ["keep", "replace", "merge"]},
                ],
            )
            actions, skipped = _resolutions.apply_resolutions_to_plan_actions(
                [{"target": ".github/instructions/main.instructions.md", "action": "replace"}],
                [],
                valid,
            )
            delete_actions = _resolutions.build_delete_actions(
                workspace,
                valid,
                [{"path": ".github/mcp/scripts/custom.py", "type": "unmanaged", "surface": "hooks"}],
            )

        self.assertEqual(valid, {
            ".github/mcp/scripts/custom.py": "remove",
            ".github/instructions/main.instructions.md": "merge",
        })
        self.assertEqual(len(warnings), 1)
        self.assertEqual(actions[0]["action"], "merge")
        self.assertEqual(skipped, [])
        self.assertEqual(delete_actions[0]["action"], "delete")

    def test_resolution_helpers_cover_missing_files_noop_paths_and_keep_behavior(self) -> None:
        self.assertEqual(_resolutions.load_resolutions(None), {})

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            self.assertEqual(_resolutions.load_resolutions(str(workspace / "missing.json")), {})

            resolutions_file = workspace / "resolutions.json"
            resolutions_file.write_text(json.dumps({"ok": 1}), encoding="utf-8")
            with self.assertRaises(LifecycleCommandError):
                _resolutions.load_resolutions(str(resolutions_file))

            valid, warnings = _resolutions.validate_resolutions(
                {"known": "keep", "bad": "merge", "unknown": "keep"},
                [{"path": "known", "availableDecisions": ["keep", "replace"]}, {"path": "bad", "availableDecisions": ["replace"]}],
            )

            actions, skipped = _resolutions.apply_resolutions_to_plan_actions(
                [{"target": "known", "action": "replace"}, {"target": "other", "action": "replace"}],
                [{"target": "already-skipped", "reason": "existing"}],
                {"known": "keep", "other": "update"},
            )

            delete_actions = _resolutions.build_delete_actions(
                workspace,
                {"missing": "remove", "known": "keep"},
                [{"path": "missing", "type": "unmanaged", "surface": "hooks"}],
            )

        self.assertEqual(valid, {"known": "keep"})
        self.assertEqual({warning["code"] for warning in warnings}, {"resolution_invalid_decision", "resolution_unknown_path"})
        self.assertEqual(actions, [{"target": "other", "action": "replace"}])
        self.assertEqual(skipped[0], {"target": "already-skipped", "reason": "existing"})
        self.assertEqual(skipped[1]["reason"], "consumer-keep")
        self.assertEqual(delete_actions, [])

        passthrough_actions, passthrough_skipped = _resolutions.apply_resolutions_to_plan_actions(
            [{"target": "x", "action": "replace"}],
            [{"target": "y", "reason": "existing"}],
            {},
        )
        self.assertEqual(passthrough_actions, [{"target": "x", "action": "replace"}])
        self.assertEqual(passthrough_skipped, [{"target": "y", "reason": "existing"}])


if __name__ == "__main__":
    unittest.main()