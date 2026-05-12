"""Unit tests for Phase 3 — pack token conflict detection and plan gate."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._pack_conflicts import (
    build_conflict_questions,
    collect_conflict_resolutions,
    detect_pack_token_conflicts,
)
from scripts.lifecycle._xanad._pack_tokens import load_pack_tokens

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# detect_pack_token_conflicts
# ---------------------------------------------------------------------------

class DetectConflictsNoPacksTests(unittest.TestCase):
    def test_no_selected_packs_no_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = detect_pack_token_conflicts(Path(tmp), [])
        self.assertEqual([], result)

    def test_single_pack_no_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "lean" / "tokens.json", {"pack:commit-style": "Terse."})
            result = detect_pack_token_conflicts(root, ["lean"])
        self.assertEqual([], result)

    def test_missing_pack_files_no_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = detect_pack_token_conflicts(Path(tmp), ["lean", "review"])
        self.assertEqual([], result)


class DetectConflictsWithConflictTests(unittest.TestCase):
    def test_two_packs_same_key_is_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "lean" / "tokens.json", {"pack:commit-style": "Terse."})
            _write_json(root / "packs" / "review" / "tokens.json", {"pack:commit-style": "Full."})
            result = detect_pack_token_conflicts(root, ["lean", "review"])
        self.assertEqual(1, len(result))
        conflict = result[0]
        self.assertEqual("pack:commit-style", conflict["token"])
        self.assertEqual("resolvedTokenConflicts.pack:commit-style", conflict["questionId"])
        self.assertIn("lean", conflict["packs"])
        self.assertIn("review", conflict["packs"])
        self.assertEqual("Terse.", conflict["candidates"]["lean"])
        self.assertEqual("Full.", conflict["candidates"]["review"])

    def test_non_overlapping_keys_no_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "lean" / "tokens.json", {"pack:commit-style": "Terse."})
            _write_json(root / "packs" / "review" / "tokens.json", {"pack:output-style": "Verbose."})
            result = detect_pack_token_conflicts(root, ["lean", "review"])
        self.assertEqual([], result)

    def test_core_does_not_contribute_to_conflict(self) -> None:
        """Core pack is excluded from conflict detection — only selected packs count."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:commit-style": "Full."})
            _write_json(root / "packs" / "lean" / "tokens.json", {"pack:commit-style": "Terse."})
            result = detect_pack_token_conflicts(root, ["lean"])
        self.assertEqual([], result)

    def test_multiple_conflicts_returned_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "lean" / "tokens.json", {
                "pack:commit-style": "L-commit.", "pack:output-style": "L-output.",
            })
            _write_json(root / "packs" / "review" / "tokens.json", {
                "pack:commit-style": "R-commit.", "pack:output-style": "R-output.",
            })
            result = detect_pack_token_conflicts(root, ["lean", "review"])
        self.assertEqual(2, len(result))
        tokens = [c["token"] for c in result]
        self.assertEqual(sorted(tokens), tokens)

    def test_malformed_pack_file_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "lean" / "tokens.json", {"pack:commit-style": "Terse."})
            bad = root / "packs" / "review" / "tokens.json"
            bad.parent.mkdir(parents=True)
            bad.write_text("{bad json", encoding="utf-8")
            result = detect_pack_token_conflicts(root, ["lean", "review"])
        self.assertEqual([], result)


# ---------------------------------------------------------------------------
# build_conflict_questions
# ---------------------------------------------------------------------------

class BuildConflictQuestionsTests(unittest.TestCase):
    def test_generates_choice_question_per_conflict(self) -> None:
        conflicts = [
            {
                "token": "pack:commit-style",
                "questionId": "resolvedTokenConflicts.pack:commit-style",
                "packs": ["lean", "review"],
                "candidates": {"lean": "Terse.", "review": "Full."},
            }
        ]
        questions = build_conflict_questions(conflicts)
        self.assertEqual(1, len(questions))
        q = questions[0]
        self.assertEqual("resolvedTokenConflicts.pack:commit-style", q["id"])
        self.assertEqual("choice", q["type"])
        self.assertIn("lean", q["options"])
        self.assertIn("review", q["options"])
        self.assertTrue(q["required"])

    def test_empty_conflicts_empty_questions(self) -> None:
        self.assertEqual([], build_conflict_questions([]))


# ---------------------------------------------------------------------------
# collect_conflict_resolutions
# ---------------------------------------------------------------------------

class CollectConflictResolutionsTests(unittest.TestCase):
    _CONFLICT = {
        "token": "pack:commit-style",
        "questionId": "resolvedTokenConflicts.pack:commit-style",
        "packs": ["lean", "review"],
        "candidates": {"lean": "Terse.", "review": "Full."},
    }

    def test_raw_answers_resolve_conflict(self) -> None:
        resolutions, unresolved = collect_conflict_resolutions(
            [self._CONFLICT],
            {},
            {"resolvedTokenConflicts.pack:commit-style": "lean"},
        )
        self.assertEqual({"pack:commit-style": "lean"}, resolutions)
        self.assertEqual([], unresolved)

    def test_lockfile_resolves_when_no_raw_answer(self) -> None:
        resolutions, unresolved = collect_conflict_resolutions(
            [self._CONFLICT],
            {"resolvedTokenConflicts": {"pack:commit-style": "review"}},
            {},
        )
        self.assertEqual({"pack:commit-style": "review"}, resolutions)
        self.assertEqual([], unresolved)

    def test_raw_answer_takes_precedence_over_lockfile(self) -> None:
        resolutions, unresolved = collect_conflict_resolutions(
            [self._CONFLICT],
            {"resolvedTokenConflicts": {"pack:commit-style": "review"}},
            {"resolvedTokenConflicts.pack:commit-style": "lean"},
        )
        self.assertEqual({"pack:commit-style": "lean"}, resolutions)

    def test_invalid_pack_id_leaves_unresolved(self) -> None:
        resolutions, unresolved = collect_conflict_resolutions(
            [self._CONFLICT],
            {},
            {"resolvedTokenConflicts.pack:commit-style": "nonexistent"},
        )
        self.assertEqual({}, resolutions)
        self.assertEqual(["resolvedTokenConflicts.pack:commit-style"], unresolved)

    def test_no_answer_leaves_unresolved(self) -> None:
        _, unresolved = collect_conflict_resolutions([self._CONFLICT], {}, {})
        self.assertEqual(["resolvedTokenConflicts.pack:commit-style"], unresolved)


# ---------------------------------------------------------------------------
# load_pack_tokens with resolved_token_conflicts
# ---------------------------------------------------------------------------

class LoadPackTokensConflictOverrideTests(unittest.TestCase):
    def test_explicit_winner_overrides_order_based_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:commit-style": "Core."})
            _write_json(root / "packs" / "lean" / "tokens.json", {"pack:commit-style": "Lean."})
            _write_json(root / "packs" / "review" / "tokens.json", {"pack:commit-style": "Review."})
            # Without explicit winner, lean is last-loaded (overrides core)... actually review is last
            result_no_winner = load_pack_tokens(root, ["lean", "review"])
            # With explicit winner lean
            result_lean_wins = load_pack_tokens(root, ["lean", "review"], {"pack:commit-style": "lean"})
        # Without winner, review is last (sequential loading)
        self.assertEqual("Review.", result_no_winner["{{pack:commit-style}}"])
        # With explicit lean winner
        self.assertEqual("Lean.", result_lean_wins["{{pack:commit-style}}"])

    def test_nonexistent_winning_pack_falls_back_to_loaded_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:commit-style": "Core."})
            result = load_pack_tokens(root, [], {"pack:commit-style": "nonexistent"})
        # nonexistent pack file is absent; core value remains
        self.assertEqual("Core.", result["{{pack:commit-style}}"])

    def test_none_resolved_conflicts_no_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:commit-style": "Core."})
            result = load_pack_tokens(root, [], None)
        self.assertEqual("Core.", result["{{pack:commit-style}}"])


if __name__ == "__main__":
    unittest.main()
