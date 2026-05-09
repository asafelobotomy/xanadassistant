from __future__ import annotations

from scripts.lifecycle._xanad._conditions import normalize_plan_answers
from scripts.lifecycle._xanad._plan_c import seed_answers_from_install_state, seed_answers_from_profile


def derive_effective_plan_defaults(
    policy: dict,
    metadata: dict,
    manifest: dict | None,
    lockfile_state: dict,
) -> tuple[dict, dict]:
    from scripts.lifecycle._xanad._interview import build_interview_questions, resolve_question_answers
    from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface

    questions = build_interview_questions(policy, metadata, "setup")
    question_ids = {question["id"] for question in questions}
    seeded_answers = seed_answers_from_install_state("update", questions, lockfile_state, {})
    seeded_answers = seed_answers_from_profile(
        metadata.get("profileRegistry") or {},
        seeded_answers,
        question_ids,
    )
    resolved_answers, _, _ = resolve_question_answers(questions, seeded_answers)
    resolved_answers = normalize_plan_answers(policy, resolved_answers)
    ownership_by_surface = resolve_ownership_by_surface(policy, manifest, lockfile_state, resolved_answers)
    return resolved_answers, ownership_by_surface