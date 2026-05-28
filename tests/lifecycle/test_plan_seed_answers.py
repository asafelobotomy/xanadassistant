from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.lifecycle._xanad import _conditions
from scripts.lifecycle._xanad import _interview
from scripts.lifecycle._xanad import _migration
from scripts.lifecycle._xanad import _plan_c
from scripts.lifecycle._xanad._errors import LifecycleCommandError


class SeedAnswersFromInstallStateTests(unittest.TestCase):
    def test_non_repair_modes_do_not_seed_answers(self) -> None:
        questions = [{"id": "profile.selected", "options": ["balanced"]}]

        result = _plan_c.seed_answers_from_install_state(
            "setup",
            questions,
            {"profile": "balanced"},
            {},
        )

        self.assertEqual(result, {})

    def test_update_mode_seeds_only_known_answers_and_filters_invalid_packs(self) -> None:
        questions = [
            {"id": "profile.selected", "options": ["balanced", "lean"]},
            {"id": "packs.selected", "options": ["tdd", "docs"]},
            {"id": "response.style", "options": ["balanced", "verbose"]},
            {"id": "mcp.enabled", "options": [True, False]},
        ]

        result = _plan_c.seed_answers_from_install_state(
            "update",
            questions,
            {
                "profile": "balanced",
                "selectedPacks": ["tdd", "unknown-pack"],
                "setupAnswers": {"response.style": "verbose", "ignored": "value"},
                "mcpEnabled": True,
            },
            {},
        )

        self.assertEqual(
            result,
            {
                "profile.selected": "balanced",
                "packs.selected": ["tdd"],
                "response.style": "verbose",
                "mcp.enabled": True,
            },
        )

    def test_existing_answers_are_not_overwritten_when_seeding(self) -> None:
        questions = [
            {"id": "profile.selected", "options": ["balanced", "lean"]},
            {"id": "packs.selected", "options": ["tdd", "docs"]},
            {"id": "mcp.enabled", "options": [True, False]},
        ]

        result = _plan_c.seed_answers_from_install_state(
            "repair",
            questions,
            {
                "profile": "balanced",
                "selectedPacks": ["tdd"],
                "mcpEnabled": False,
            },
            {
                "profile.selected": "lean",
                "packs.selected": ["docs"],
                "mcp.enabled": True,
            },
        )

        self.assertEqual(result["profile.selected"], "lean")
        self.assertEqual(result["packs.selected"], ["docs"])
        self.assertTrue(result["mcp.enabled"])

    def test_update_mode_seeds_packs_correctly_with_dict_options(self) -> None:
        questions = [
            {
                "id": "profile.selected",
                "options": [{"id": "balanced", "label": "Balanced", "description": "Default"}],
            },
            {
                "id": "packs.selected",
                "options": [
                    {"id": "tdd", "label": "TDD", "description": "Test-driven"},
                    {"id": "docs", "label": "Docs", "description": "Documentation"},
                ],
            },
        ]

        result = _plan_c.seed_answers_from_install_state(
            "update",
            questions,
            {
                "profile": "balanced",
                "selectedPacks": ["tdd", "removed-pack"],
                "setupAnswers": {},
            },
            {},
        )

        self.assertEqual(result["profile.selected"], "balanced")
        self.assertEqual(result["packs.selected"], ["tdd"])


class SeedAnswersFromProfileTests(unittest.TestCase):
    def test_selected_profile_seeds_defaults_and_default_packs(self) -> None:
        registry = {
            "profiles": [
                {
                    "id": "balanced",
                    "defaultPacks": ["tdd"],
                    "setupAnswerDefaults": {
                        "response.style": "balanced",
                        "autonomy.level": "ask-first",
                    },
                }
            ]
        }

        result = _plan_c.seed_answers_from_profile(
            registry,
            {"profile.selected": "balanced"},
            {"response.style", "autonomy.level"},
        )

        self.assertEqual(
            result,
            {
                "profile.selected": "balanced",
                "response.style": "balanced",
                "autonomy.level": "ask-first",
                "packs.selected": ["tdd"],
            },
        )

    def test_unknown_profile_or_filtered_question_ids_do_not_seed(self) -> None:
        registry = {
            "profiles": [
                {
                    "id": "balanced",
                    "defaultPacks": ["tdd"],
                    "setupAnswerDefaults": {"response.style": "balanced"},
                }
            ]
        }

        filtered = _plan_c.seed_answers_from_profile(
            registry,
            {"profile.selected": "balanced", "packs.selected": ["docs"]},
            {"autonomy.level"},
        )
        unknown = _plan_c.seed_answers_from_profile(registry, {"profile.selected": "missing"})

        self.assertEqual(filtered, {"profile.selected": "balanced", "packs.selected": ["docs"]})
        self.assertEqual(unknown, {"profile.selected": "missing"})
