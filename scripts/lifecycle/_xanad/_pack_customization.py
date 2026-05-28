from __future__ import annotations

from copy import deepcopy

from scripts.lifecycle._xanad._errors import LifecycleCommandError


def build_pack_customization_questions(
    pack_registry: dict,
    resolved_answers: dict,
) -> list[dict]:
    """Return pack-specific customization questions for all selected active packs.

    Questions are filtered to only the packs present in ``packs.selected``.
    Each question is expanded with ``id = answerKey``, ``batch = "pack"``
    (unless already set), ``required = False`` (unless already set), and
    ``packId`` for identification.
    """
    selected_packs = resolved_answers.get("packs.selected") or []
    if not isinstance(selected_packs, list):
        selected_packs = []

    questions: list[dict] = []
    for pack in (pack_registry or {}).get("packs", []):
        if pack.get("status") != "active":
            continue
        pack_id = pack.get("id")
        if pack_id not in selected_packs:
            continue
        customization = pack.get("customization") or {}
        for question in customization.get("questions") or []:
            answer_key = question.get("answerKey")
            if not isinstance(answer_key, str) or not answer_key:
                raise LifecycleCommandError(
                    "contract_input_failure",
                    "Pack customization questions must declare a non-empty answerKey.",
                    4,
                    {"packId": pack_id, "question": question},
                )
            expanded = deepcopy(question)
            expanded["id"] = answer_key
            expanded.setdefault("batch", "pack")
            expanded.setdefault("required", False)
            expanded["packId"] = pack_id
            questions.append(expanded)
    return questions
