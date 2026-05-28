from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad import _conditions
from scripts.lifecycle._xanad._errors import LifecycleCommandError
from scripts.lifecycle._xanad._pack_customization import build_pack_customization_questions


def _tdd_pack(status: str = "active") -> dict:
    return {
        "id": "tdd",
        "status": status,
        "customization": {
            "questions": [
                {
                    "id": "cycle-strictness",
                    "answerKey": "pack.tdd.cycleStrictness",
                    "kind": "choice",
                    "tokens": ["{{pack:scope-discipline}}"],
                    "render": {
                        "strict": "One failing test at a time.",
                        "guided": "Prefer test-first; allow multi-test scope when stated.",
                    },
                }
            ]
        },
    }


def _secure_pack() -> dict:
    return {
        "id": "secure",
        "status": "active",
        "customization": {
            "questions": [
                {
                    "id": "owasp-scope",
                    "answerKey": "pack.secure.owaspScope",
                    "kind": "choice",
                    "tokens": ["{{pack:review-depth}}"],
                    "render": {
                        "full-top-10": "Flag all OWASP Top 10:2025 entries.",
                        "critical-and-high-only": "Flag OWASP Top 10:2025 only at Critical/High.",
                    },
                }
            ]
        },
    }


class BuildPackCustomizationQuestionsTests(unittest.TestCase):
    def test_returns_empty_when_no_packs_selected(self) -> None:
        pack_registry = {"packs": [_tdd_pack()]}
        result = build_pack_customization_questions(pack_registry, {})
        self.assertEqual(result, [])

    def test_returns_empty_when_selected_packs_is_empty_list(self) -> None:
        pack_registry = {"packs": [_tdd_pack()]}
        result = build_pack_customization_questions(pack_registry, {"packs.selected": []})
        self.assertEqual(result, [])

    def test_returns_questions_only_for_selected_packs(self) -> None:
        pack_registry = {"packs": [_tdd_pack(), _secure_pack()]}
        result = build_pack_customization_questions(
            pack_registry, {"packs.selected": ["tdd"]}
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["packId"], "tdd")
        self.assertEqual(result[0]["id"], "pack.tdd.cycleStrictness")

    def test_returns_questions_for_multiple_selected_packs(self) -> None:
        pack_registry = {"packs": [_tdd_pack(), _secure_pack()]}
        result = build_pack_customization_questions(
            pack_registry, {"packs.selected": ["tdd", "secure"]}
        )
        self.assertEqual(len(result), 2)
        pack_ids = {q["packId"] for q in result}
        self.assertEqual(pack_ids, {"tdd", "secure"})

    def test_skips_inactive_packs_even_when_selected(self) -> None:
        pack_registry = {"packs": [_tdd_pack(status="retired")]}
        result = build_pack_customization_questions(
            pack_registry, {"packs.selected": ["tdd"]}
        )
        self.assertEqual(result, [])

    def test_skips_packs_with_no_customization(self) -> None:
        pack_registry = {
            "packs": [{"id": "oss", "status": "active"}]
        }
        result = build_pack_customization_questions(
            pack_registry, {"packs.selected": ["oss"]}
        )
        self.assertEqual(result, [])

    def test_expanded_question_has_id_equal_to_answer_key(self) -> None:
        pack_registry = {"packs": [_tdd_pack()]}
        result = build_pack_customization_questions(
            pack_registry, {"packs.selected": ["tdd"]}
        )
        self.assertEqual(result[0]["id"], "pack.tdd.cycleStrictness")

    def test_expanded_question_has_batch_pack_by_default(self) -> None:
        pack_registry = {"packs": [_tdd_pack()]}
        result = build_pack_customization_questions(
            pack_registry, {"packs.selected": ["tdd"]}
        )
        self.assertEqual(result[0]["batch"], "pack")

    def test_expanded_question_preserves_explicit_batch(self) -> None:
        pack = {
            "id": "tdd",
            "status": "active",
            "customization": {
                "questions": [
                    {"answerKey": "pack.tdd.x", "batch": "advanced", "tokens": []}
                ]
            },
        }
        result = build_pack_customization_questions(
            {"packs": [pack]}, {"packs.selected": ["tdd"]}
        )
        self.assertEqual(result[0]["batch"], "advanced")

    def test_expanded_question_required_is_false_by_default(self) -> None:
        pack_registry = {"packs": [_tdd_pack()]}
        result = build_pack_customization_questions(
            pack_registry, {"packs.selected": ["tdd"]}
        )
        self.assertFalse(result[0]["required"])

    def test_expanded_question_has_pack_id(self) -> None:
        pack_registry = {"packs": [_tdd_pack()]}
        result = build_pack_customization_questions(
            pack_registry, {"packs.selected": ["tdd"]}
        )
        self.assertEqual(result[0]["packId"], "tdd")

    def test_raises_on_question_missing_answer_key(self) -> None:
        pack = {
            "id": "tdd",
            "status": "active",
            "customization": {
                "questions": [{"id": "bad", "tokens": ["{{pack:scope-discipline}}"]}]
            },
        }
        with self.assertRaises(LifecycleCommandError) as ctx:
            build_pack_customization_questions(
                {"packs": [pack]}, {"packs.selected": ["tdd"]}
            )
        self.assertEqual(ctx.exception.exit_code, 4)

    def test_does_not_mutate_source_question(self) -> None:
        pack_registry = {"packs": [_tdd_pack()]}
        source_question = pack_registry["packs"][0]["customization"]["questions"][0]
        self.assertNotIn("packId", source_question)
        build_pack_customization_questions(pack_registry, {"packs.selected": ["tdd"]})
        self.assertNotIn("packId", source_question)


class PackCustomizationTokenResolutionTests(unittest.TestCase):
    def _make_root(self, tmpdir: str, core_tokens: dict, tdd_tokens: dict | None = None) -> Path:
        root = Path(tmpdir)
        (root / "packs" / "core").mkdir(parents=True)
        (root / "packs" / "core" / "tokens.json").write_text(
            json.dumps(core_tokens), encoding="utf-8"
        )
        if tdd_tokens is not None:
            (root / "packs" / "tdd").mkdir(parents=True)
            (root / "packs" / "tdd" / "tokens.json").write_text(
                json.dumps(tdd_tokens), encoding="utf-8"
            )
        (root / "workspace").mkdir()
        return root

    def test_pack_customization_answer_overrides_base_pack_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_root(
                tmpdir,
                core_tokens={"pack:scope-discipline": "Core default."},
                tdd_tokens={"pack:scope-discipline": "TDD strict default."},
            )
            pack_registry = {
                "packs": [
                    {
                        "id": "tdd",
                        "status": "active",
                        "customization": {
                            "questions": [
                                {
                                    "answerKey": "pack.tdd.cycleStrictness",
                                    "tokens": ["{{pack:scope-discipline}}"],
                                    "render": {
                                        "guided": "Guided TDD mode.",
                                    },
                                }
                            ]
                        },
                    }
                ]
            }
            result = _conditions.resolve_token_values(
                {"tokenRules": []},
                root / "workspace",
                {"packs.selected": ["tdd"], "pack.tdd.cycleStrictness": "guided"},
                package_root=root,
                metadata={"packRegistry": pack_registry},
            )
        self.assertEqual(result["{{pack:scope-discipline}}"], "Guided TDD mode.")

    def test_no_answer_preserves_base_pack_token_from_tokens_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_root(
                tmpdir,
                core_tokens={"pack:scope-discipline": "Core default."},
                tdd_tokens={"pack:scope-discipline": "TDD strict default."},
            )
            pack_registry = {
                "packs": [
                    {
                        "id": "tdd",
                        "status": "active",
                        "customization": {
                            "questions": [
                                {
                                    "answerKey": "pack.tdd.cycleStrictness",
                                    "tokens": ["{{pack:scope-discipline}}"],
                                    "render": {"guided": "Guided TDD mode."},
                                }
                            ]
                        },
                    }
                ]
            }
            result = _conditions.resolve_token_values(
                {"tokenRules": []},
                root / "workspace",
                {"packs.selected": ["tdd"]},
                package_root=root,
                metadata={"packRegistry": pack_registry},
            )
        self.assertEqual(result["{{pack:scope-discipline}}"], "TDD strict default.")

    def test_pack_customization_runs_before_agent_token_values(self) -> None:
        """Agent fallbackToken should see the pack-customized value, not the base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_root(
                tmpdir,
                core_tokens={"pack:scope-discipline": "Core default."},
                tdd_tokens={"pack:scope-discipline": "TDD strict default."},
            )
            pack_registry = {
                "packs": [
                    {
                        "id": "tdd",
                        "status": "active",
                        "customization": {
                            "questions": [
                                {
                                    "answerKey": "pack.tdd.cycleStrictness",
                                    "tokens": ["{{pack:scope-discipline}}"],
                                    "render": {"guided": "Guided TDD mode."},
                                }
                            ]
                        },
                    }
                ]
            }
            agent_registry = {
                "agents": [
                    {
                        "id": "planner",
                        "status": "active",
                        "customization": {
                            "tokenNamespace": "agent:planner",
                            "questions": [
                                {
                                    "answerKey": "agent.planner.scope",
                                    "tokens": ["{{agent:planner:scope}}"],
                                    "fallbackToken": "{{pack:scope-discipline}}",
                                    "render": {},
                                }
                            ],
                        },
                    }
                ]
            }
            result = _conditions.resolve_token_values(
                {"tokenRules": [{"token": "{{agent:planner:scope}}"}]},
                root / "workspace",
                {"packs.selected": ["tdd"], "pack.tdd.cycleStrictness": "guided"},
                package_root=root,
                metadata={
                    "packRegistry": pack_registry,
                    "agentRegistry": agent_registry,
                },
            )
        # Agent fallback should inherit the pack-customized value.
        self.assertEqual(result["{{agent:planner:scope}}"], "Guided TDD mode.")

    def test_unselected_pack_customization_has_no_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = self._make_root(
                tmpdir,
                core_tokens={"pack:scope-discipline": "Core default."},
            )
            pack_registry = {
                "packs": [
                    {
                        "id": "tdd",
                        "status": "active",
                        "customization": {
                            "questions": [
                                {
                                    "answerKey": "pack.tdd.cycleStrictness",
                                    "tokens": ["{{pack:scope-discipline}}"],
                                    "render": {"guided": "Guided TDD mode."},
                                }
                            ]
                        },
                    }
                ]
            }
            result = _conditions.resolve_token_values(
                {"tokenRules": []},
                root / "workspace",
                {"packs.selected": [], "pack.tdd.cycleStrictness": "guided"},
                package_root=root,
                metadata={"packRegistry": pack_registry},
            )
        self.assertEqual(result["{{pack:scope-discipline}}"], "Core default.")
