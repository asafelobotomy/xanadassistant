from __future__ import annotations

from scripts.lifecycle._xanad._conditions import normalize_plan_answers


def derive_effective_plan_defaults(
    policy: dict,
    metadata: dict,
    manifest: dict | None,
    lockfile_state: dict,
) -> tuple[dict, dict]:
    from scripts.lifecycle._xanad._interview import prepare_questions
    from scripts.lifecycle._xanad._plan_a import resolve_ownership_by_surface

    questions, resolved_answers, _, _ = prepare_questions(
        policy, metadata, manifest, "setup", lockfile_state, seed_mode="update",
    )
    resolved_answers = normalize_plan_answers(policy, resolved_answers)
    ownership_by_surface = resolve_ownership_by_surface(policy, manifest, lockfile_state, resolved_answers)
    return resolved_answers, ownership_by_surface