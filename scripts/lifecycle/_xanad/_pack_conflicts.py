from __future__ import annotations

import json
from pathlib import Path


def detect_pack_token_conflicts(package_root: Path, selected_packs: list[str]) -> list[dict]:
    """
    Return conflict records for token keys defined by two or more selected non-core packs.

    Core defaults are not considered conflicting — conflict detection only scans selected
    (non-core) packs.  Each record::

        {
            "token": "pack:token-name",
            "questionId": "resolvedTokenConflicts.pack:token-name",
            "packs": ["packA", "packB"],
            "candidates": {"packA": "value A", "packB": "value B"},
        }
    """
    if not selected_packs:
        return []

    token_providers: dict[str, list[str]] = {}
    token_values_by_pack: dict[str, dict[str, str]] = {}

    for pack_name in selected_packs:
        pack_file = package_root / "packs" / pack_name / "tokens.json"
        if not pack_file.is_file():
            continue
        try:
            data = json.loads(pack_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        pack_tokens: dict[str, str] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                token_providers.setdefault(key, []).append(pack_name)
                pack_tokens[key] = value
        token_values_by_pack[pack_name] = pack_tokens

    conflicts = []
    for token_key, packs in sorted(token_providers.items()):
        if len(packs) < 2:
            continue
        candidates = {
            pack_name: token_values_by_pack[pack_name][token_key]
            for pack_name in packs
        }
        conflicts.append({
            "token": token_key,
            "questionId": f"resolvedTokenConflicts.{token_key}",
            "packs": packs,
            "candidates": candidates,
        })

    return conflicts


def build_conflict_questions(pack_conflicts: list[dict]) -> list[dict]:
    """Return interview-format choice questions for each pack token conflict."""
    questions = []
    for conflict in pack_conflicts:
        questions.append({
            "id": conflict["questionId"],
            "label": f"Conflict: {conflict['token']}",
            "description": (
                f"Multiple selected packs define '{conflict['token']}'. "
                "Choose which pack's value to use."
            ),
            "type": "choice",
            "options": list(conflict["packs"]),
            "required": True,
        })
    return questions


def collect_conflict_resolutions(
    pack_conflicts: list[dict],
    lockfile_state: dict,
    raw_answers: dict,
) -> tuple[dict[str, str], list[str]]:
    """
    Return ``(resolutions, unresolved_ids)``.

    *resolutions* maps raw token name → winning pack ID for every conflict that
    already has a valid answer.  *unresolved_ids* is the list of question IDs for
    conflicts that still need a user choice.

    Resolution candidates are drawn from, in priority order:

    1. ``raw_answers`` (from an answers file passed to the plan command)
    2. ``lockfile_state["resolvedTokenConflicts"]`` (winners from a prior apply)
    """
    lockfile_conflicts = lockfile_state.get("resolvedTokenConflicts", {})
    if not isinstance(lockfile_conflicts, dict):
        lockfile_conflicts = {}

    resolutions: dict[str, str] = {}
    unresolved_ids: list[str] = []

    for conflict in pack_conflicts:
        token_key = conflict["token"]
        question_id = conflict["questionId"]
        valid_packs = conflict["packs"]

        answer = raw_answers.get(question_id)
        if not isinstance(answer, str):
            answer = lockfile_conflicts.get(token_key)

        if isinstance(answer, str) and answer in valid_packs:
            resolutions[token_key] = answer
        else:
            unresolved_ids.append(question_id)

    return resolutions, unresolved_ids
