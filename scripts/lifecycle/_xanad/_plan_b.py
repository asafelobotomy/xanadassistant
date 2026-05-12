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
from scripts.lifecycle._xanad._plan_utils import build_backup_plan, build_token_plan_summary
from scripts.lifecycle._xanad._progress import build_not_implemented_payload
from scripts.lifecycle._xanad._source import build_source_summary


def _build_lockfile_package_info() -> dict:
    """Return the lockfile package dict, populated from session source info when available."""
    source_info = _State.session_source_info
    info: dict = {"name": "xanadAssistant"}
    if source_info is not None:
        if "packageRoot" in source_info:
            info["packageRoot"] = source_info["packageRoot"]
        if "version" in source_info:
            info["version"] = source_info["version"]
        if "source" in source_info:
            info["source"] = source_info["source"]
        if "ref" in source_info:
            info["ref"] = source_info["ref"]
    return info


def build_planned_lockfile(
    workspace: Path,
    context: dict,
    ownership_by_surface: dict,
    resolved_answers: dict,
    token_values: dict[str, str],
    actions: list[dict],
    skipped_actions: list[dict],
    retired_targets: list[str],
    backup_plan: dict,
) -> dict:
    from scripts.lifecycle._xanad._plan_utils import expected_entry_hash

    manifest = context["manifest"] or {"schemaVersion": "unknown", "managedFiles": [], "retiredFiles": []}
    manifest_entries = {entry["id"]: entry for entry in manifest.get("managedFiles", [])}
    file_records = []

    for action in actions:
        if action["action"] == "archive-retired":
            continue
        manifest_entry = manifest_entries.get(action["id"])
        if manifest_entry is None:
            continue
        file_records.append({
            "id": action["id"],
            "target": action["target"],
            "sourceHash": manifest_entry["hash"],
            "installedHash": expected_entry_hash(
                context["packageRoot"],
                manifest_entry,
                token_values,
                workspace / action["target"],
            ) or "unknown",
            "ownershipMode": action["ownershipMode"],
            "status": "applied",
        })

    archive_targets = {entry["target"]: entry["archivePath"] for entry in backup_plan.get("archiveTargets", [])}
    retired_records = []
    for action in actions:
        if action["action"] != "archive-retired":
            continue
        target = action.get("target")
        retired_record = {
            "id": action["id"],
            "action": "archived" if target in archive_targets else "reported",
        }
        if target is not None:
            retired_record["target"] = target
        if target in archive_targets:
            retired_record["archivePath"] = archive_targets[target]
        retired_records.append(retired_record)

    lockfile_contents = {
        "schemaVersion": "0.1.0",
        "package": _build_lockfile_package_info(),
        "manifest": {
            "schemaVersion": manifest.get("schemaVersion", "0.1.0"),
            "hash": sha256_json(manifest),
        },
        "timestamps": {"appliedAt": "<apply-timestamp>", "updatedAt": "<apply-timestamp>"},
        "selectedPacks": resolved_answers.get("packs.selected", []),
        "profile": resolved_answers.get("profile.selected"),
        "ownershipBySurface": ownership_by_surface,
        "setupAnswers": resolved_answers,
        "resolvedTokenConflicts": {
            key[len("resolvedTokenConflicts."):]: value
            for key, value in resolved_answers.items()
            if key.startswith("resolvedTokenConflicts.") and isinstance(value, str)
        },
        "installMetadata": {
            "mcpAvailable": True,
            "mcpEnabled": bool(resolved_answers.get("mcp.enabled", False)),
        },
        "files": sorted(file_records, key=lambda record: record["target"]),
        "skippedManagedFiles": sorted(entry["target"] for entry in skipped_actions),
        "retiredManagedFiles": retired_records,
        "unknownValues": {},
    }
    if backup_plan.get("required") and backup_plan.get("root"):
        lockfile_contents["lastBackup"] = {"path": backup_plan["root"]}

    return {"path": ".github/xanadAssistant-lock.json", "contents": lockfile_contents}


def build_plan_result(workspace: Path, package_root: Path, mode: str, answers_path: str | None, non_interactive: bool) -> dict:
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
    answers = seed_answers_from_install_state(mode, questions, context["lockfileState"], load_answers(answers_path))
    answers = seed_answers_from_profile(context["metadata"].get("profileRegistry") or {}, answers, question_ids)
    resolved_answers, unresolved, unknown_answer_ids = resolve_question_answers(questions, answers)
    resolved_answers = normalize_plan_answers(context["policy"], resolved_answers)
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
        raw_answers = load_answers(answers_path)
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
                    "writes": {"add": 0, "replace": 0, "merge": 0, "archiveRetired": 0},
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

    ownership_by_surface = resolve_ownership_by_surface(
        context["policy"], context["manifest"], context["lockfileState"], resolved_answers,
    )
    token_values = resolve_token_values(context["policy"], workspace, resolved_answers, package_root=package_root)

    writes, actions, skipped_actions, retired_targets = build_setup_plan_actions(
        workspace, package_root, context["manifest"], ownership_by_surface,
        resolved_answers, token_values, force_reinstall=(mode == "factory-restore"),
    )
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
    if unknown_answer_ids:
        warnings.append({
            "code": "unknown_answer_ids_ignored",
            "message": "Answer file keys not present in the current question set were ignored.",
            "details": {"questionIds": unknown_answer_ids},
        })
    token_plan = build_token_plan_summary(context["policy"], actions, token_values)
    backup_required = any(count > 0 for count in writes.values())
    backup_plan = build_backup_plan(context["policy"], actions, backup_required)
    planned_lockfile = build_planned_lockfile(
        workspace, context, ownership_by_surface, resolved_answers, token_values,
        actions, skipped_actions, retired_targets, backup_plan,
    )
    approval_required = backup_required

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
        },
    }
