from __future__ import annotations

from pathlib import Path

from scripts.lifecycle._xanad._conditions import normalize_plan_answers, resolve_token_values
from scripts.lifecycle._xanad._errors import LifecycleCommandError, _State
from scripts.lifecycle._xanad._inspect import collect_context
from scripts.lifecycle._xanad._interview import (
    build_interview_questions,
    load_answers,
    resolve_question_answers,
)
from scripts.lifecycle._xanad._merge import sha256_json
from scripts.lifecycle._xanad._plan_a import (
    build_conflict_summary,
    build_setup_plan_actions,
    classify_plan_conflicts,
    resolve_ownership_by_surface,
    write_plan_output,
)
from scripts.lifecycle._xanad._plan_c import (
    determine_repair_reasons,
    seed_answers_from_install_state,
    seed_answers_from_profile,
)
from scripts.lifecycle._xanad._pack_conflicts import (
    build_conflict_questions,
    collect_conflict_resolutions,
    detect_pack_token_conflicts,
)
from scripts.lifecycle._xanad._plan_utils import (
    build_backup_plan,
    build_token_plan_summary,
    _build_lockfile_package_info,  # noqa: F401 – re-exported
    build_planned_lockfile,  # noqa: F401 – re-exported
)
from scripts.lifecycle._xanad._prescan import scan_consumer_kept_updates, scan_existing_copilot_files
from scripts.lifecycle._xanad._progress import build_not_implemented_payload
from scripts.lifecycle._xanad._resolutions import (
    apply_resolutions_to_plan_actions,
    build_delete_actions,
    load_resolutions,
    validate_resolutions,
)
from scripts.lifecycle._xanad._source import build_source_summary


def _conflict_blocked_plan(
    workspace: Path,
    package_root: Path,
    mode: str,
    context: dict,
    resolved_answers: dict,
    questions: list,
    pack_conflicts: list,
    repair_reasons: list,
) -> dict:
    """Return the approval-required plan payload for unresolved pack token conflicts."""
    ownership_by_surface = resolve_ownership_by_surface(
        context["policy"], context["manifest"], context["lockfileState"], resolved_answers,
    )
    return {
        "command": "plan", "mode": mode, "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "approval-required", "warnings": [], "errors": [],
        "result": {
            "installState": context["installState"],
            "installPaths": context["installPaths"],
            "contracts": context["artifacts"],
            "discoveryMetadata": context["metadataArtifacts"],
            "approvalRequired": True, "backupRequired": False,
            "backupPlan": build_backup_plan(context["policy"], [], False),
            "plannedLockfile": None,
            "writes": {"add": 0, "replace": 0, "merge": 0, "archiveRetired": 0, "deleted": 0},
            "conflicts": [], "conflictSummary": build_conflict_summary([]),
            "conflictDetails": pack_conflicts,
            "actions": [], "skippedActions": [], "tokenSubstitutions": [],
            "ownershipBySurface": ownership_by_surface,
            "packs": resolved_answers.get("packs.selected", []),
            "profile": resolved_answers.get("profile.selected"),
            "factoryRestore": mode == "factory-restore",
            "repairReasons": repair_reasons, "retired": [],
            "questionsResolved": False,
            "resolvedAnswers": resolved_answers, "questions": questions,
        },
    }


def build_plan_result(
    workspace: Path,
    package_root: Path,
    mode: str,
    answers_path: str | None,
    non_interactive: bool,
    resolutions_path: str | None = None,
) -> dict:
    if mode not in {"setup", "update", "repair", "factory-restore"}:
        return build_not_implemented_payload("plan", workspace, package_root, mode)

    context = collect_context(workspace, package_root)
    if mode == "update" and context["installState"] == "not-installed":
        raise LifecycleCommandError(
            "inspection_failure", "Update planning requires an existing install state.", 5,
            {"installState": context["installState"]},
        )
    if mode == "repair":
        repair_reasons = determine_repair_reasons(context)
        if context["installState"] == "not-installed":
            raise LifecycleCommandError(
                "inspection_failure", "Repair planning requires an existing install state.", 5,
                {"installState": context["installState"]},
            )
        if not repair_reasons:  # pragma: no cover
            raise LifecycleCommandError(
                "inspection_failure",
                "Repair planning requires legacy, malformed, or incomplete managed state.", 5,
                {"installState": context["installState"]},
            )
    else:
        repair_reasons = []
    if mode == "factory-restore" and context["installState"] == "not-installed":
        raise LifecycleCommandError(
            "inspection_failure", "Factory-restore planning requires an existing install state.", 5,
            {"installState": context["installState"]},
        )

    questions = build_interview_questions(context["policy"], context["metadata"], mode)
    question_ids = {q["id"] for q in questions}
    raw_answers = load_answers(answers_path)
    answers = seed_answers_from_install_state(mode, questions, context["lockfileState"], raw_answers)
    answers = seed_answers_from_profile(context["metadata"].get("profileRegistry") or {}, answers, question_ids)
    resolved_answers, unresolved, unknown_answer_ids = resolve_question_answers(questions, answers)
    resolved_answers = normalize_plan_answers(context["policy"], resolved_answers)

    # Prescan: detect pre-existing files and load consumer per-file resolutions.
    _res_warnings: list[dict] = []
    if mode == "setup":
        existing_files = scan_existing_copilot_files(workspace, context["manifest"])
        resolutions, _res_warnings = validate_resolutions(
            load_resolutions(resolutions_path), existing_files
        )
    elif mode == "update":
        _prior = context["lockfileState"].get("consumerResolutions", {})
        existing_files = scan_consumer_kept_updates(
            workspace, context["manifest"], context["lockfileState"]
        )
        _new, _res_warnings = validate_resolutions(
            load_resolutions(resolutions_path), existing_files
        )
        resolutions = {**_prior, **_new}
    else:
        existing_files = []
        resolutions = {}

    if non_interactive and unresolved:  # pragma: no cover
        raise LifecycleCommandError(
            "approval_or_answers_required",
            "Required answers are missing for non-interactive planning.", 6,
            {"questionIds": unresolved},
        )

    # Phase 3: Detect and gate on pack token conflicts.
    selected_packs = resolved_answers.get("packs.selected") or []
    pack_conflicts = detect_pack_token_conflicts(package_root, selected_packs)
    unresolved_conflicts: list[str] = []
    if pack_conflicts:
        conflict_resolutions, unresolved_conflicts = collect_conflict_resolutions(
            pack_conflicts, context["lockfileState"], raw_answers
        )
        resolved_answers.update({
            f"resolvedTokenConflicts.{k}": v for k, v in conflict_resolutions.items()
        })
        questions = questions + build_conflict_questions(pack_conflicts)
        if unresolved_conflicts:
            if non_interactive:
                raise LifecycleCommandError(
                    "approval_or_answers_required",
                    "Pack token conflicts must be resolved before planning can proceed.", 6,
                    {"questionIds": unresolved_conflicts, "conflicts": pack_conflicts},
                )
            return _conflict_blocked_plan(
                workspace, package_root, mode, context,
                resolved_answers, questions, pack_conflicts, repair_reasons,
            )

    ownership_by_surface = resolve_ownership_by_surface(
        context["policy"], context["manifest"], context["lockfileState"], resolved_answers,
    )
    token_values = resolve_token_values(context["policy"], workspace, resolved_answers, package_root=package_root)

    writes, actions, skipped_actions, retired_targets = build_setup_plan_actions(
        workspace, package_root, context["manifest"], ownership_by_surface,
        resolved_answers, token_values, force_reinstall=(mode == "factory-restore"),
    )
    # Apply consumer per-file resolutions (keep / replace / merge / update).
    actions, skipped_actions = apply_resolutions_to_plan_actions(actions, skipped_actions, resolutions)
    delete_actions = build_delete_actions(workspace, resolutions, existing_files)
    actions.extend(delete_actions)
    writes["deleted"] = len(delete_actions)

    for target in context.get("successorMigrationTargets", []):
        if target in retired_targets:  # pragma: no cover
            continue
        writes["archiveRetired"] += 1
        retired_targets.append(target)
        actions.append({
            "id": f"migration.cleanup.{target}",
            "target": target,
            "action": "archive-retired",
            "ownershipMode": None,
            "strategy": "archive-retired",
        })
    conflicts, warnings = classify_plan_conflicts(workspace, context, actions, retired_targets)
    warnings.extend(_res_warnings)
    if unknown_answer_ids:
        warnings.append({
            "code": "unknown_answer_ids_ignored",
            "message": "Answer file keys not present in the current question set were ignored.",
            "details": {"questionIds": unknown_answer_ids},
        })
    token_plan = build_token_plan_summary(context["policy"], actions, token_values)
    backup_required = (
        writes.get("replace", 0) + writes.get("merge", 0)
        + writes.get("archiveRetired", 0) + writes.get("deleted", 0)
    ) > 0
    backup_plan = build_backup_plan(context["policy"], actions, backup_required)
    keep_resolutions = {k: v for k, v in resolutions.items() if v == "keep"}
    planned_lockfile = build_planned_lockfile(
        workspace, context, ownership_by_surface, resolved_answers, token_values,
        actions, skipped_actions, retired_targets, backup_plan,
        consumer_resolutions=keep_resolutions,
    )
    approval_required = any(count > 0 for count in writes.values())

    return {
        "command": "plan",
        "mode": mode,
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "approval-required" if approval_required else "ok",
        "warnings": warnings,
        "errors": [],
        "result": {
            "installState": context["installState"],
            "installPaths": context["installPaths"],
            "contracts": context["artifacts"],
            "discoveryMetadata": context["metadataArtifacts"],
            "approvalRequired": approval_required,
            "backupRequired": backup_required,
            "backupPlan": backup_plan,
            "plannedLockfile": planned_lockfile,
            "writes": writes,
            "conflicts": conflicts,
            "conflictSummary": build_conflict_summary(conflicts),
            # [] when all conflicts resolved or no conflicts — the apply gate is truthy-based.
            "conflictDetails": pack_conflicts if unresolved_conflicts else [],
            "actions": actions,
            "skippedActions": skipped_actions,
            "tokenSubstitutions": token_plan,
            "ownershipBySurface": ownership_by_surface,
            "packs": resolved_answers.get("packs.selected", []),
            "profile": resolved_answers.get("profile.selected"),
            "factoryRestore": mode == "factory-restore",
            "repairReasons": repair_reasons,
            "retired": retired_targets,
            "questionsResolved": not unresolved,
            "resolvedAnswers": resolved_answers,
            "questions": questions,
            "existingFiles": existing_files,
            "consumerResolutions": resolutions,
        },
    }
