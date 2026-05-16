from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from scripts.lifecycle._xanad._apply_executor import execute_apply_plan
from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH, LifecycleCommandError
from scripts.lifecycle._xanad._loader import load_json, load_manifest
from scripts.lifecycle._xanad._merge import sha256_json
from scripts.lifecycle._xanad._migration import CURRENT_PACKAGE_NAME
from scripts.lifecycle._xanad._plan_b import build_plan_result
from scripts.lifecycle._xanad._source import build_source_summary


def _validate_relative_plan_path(path_value: object, field: str) -> str:
    if not isinstance(path_value, str) or not path_value:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan file contains an invalid path field.",
            4,
            {"field": field, "value": path_value},
        )

    path = PurePosixPath(path_value)
    if path.is_absolute() or ".." in path.parts:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan file path fields must stay within the workspace.",
            4,
            {"field": field, "value": path_value},
        )
    return path.as_posix()


def validate_apply_plan_paths(plan_payload: dict, package_root: Path) -> None:
    result = plan_payload["result"]
    planned_lockfile = result["plannedLockfile"]
    lockfile_path = _validate_relative_plan_path(planned_lockfile.get("path"), "result.plannedLockfile.path")
    if lockfile_path != ".github/xanadAssistant-lock.json":
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan lockfile path does not match the lifecycle contract.",
            4,
            {"planned": lockfile_path, "current": ".github/xanadAssistant-lock.json"},
        )

    managed_targets: dict[str, str] | None = None
    retired_targets: dict[str, str] | None = None
    action_targets: set[str] = set()

    def ensure_manifest_targets() -> tuple[dict[str, str], dict[str, str]]:
        nonlocal managed_targets, retired_targets
        if managed_targets is None or retired_targets is None:
            manifest = load_manifest(package_root, load_json(package_root / DEFAULT_POLICY_PATH)) or {
                "managedFiles": [],
                "retiredFiles": [],
            }
            managed_targets = {entry["id"]: entry["target"] for entry in manifest.get("managedFiles", [])}
            retired_targets = {entry["id"]: entry["target"] for entry in manifest.get("retiredFiles", [])}
        return managed_targets, retired_targets

    for index, action in enumerate(result.get("actions", [])):
        if not isinstance(action, dict):
            raise LifecycleCommandError(
                "contract_input_failure",
                "Plan file contains an invalid action record.",
                4,
                {"index": index},
            )

        action_type = action.get("action")
        target = _validate_relative_plan_path(action.get("target"), f"result.actions[{index}].target")
        action_targets.add(target)
        action_id = action.get("id")

        if action_type in {"add", "replace", "merge"}:
            current_managed_targets, _ = ensure_manifest_targets()
            if current_managed_targets.get(action_id) != target:
                raise LifecycleCommandError(
                    "contract_input_failure",
                    "Plan action target does not match the current manifest entry.",
                    4,
                    {"id": action_id, "planned": target, "current": current_managed_targets.get(action_id)},
                )
        elif action_type == "delete":
            if action_id != f"delete:{target}":
                raise LifecycleCommandError(
                    "contract_input_failure",
                    "Plan delete action does not match its target path.",
                    4,
                    {"id": action_id, "target": target},
                )
        elif action_type == "archive-retired":
            _, current_retired_targets = ensure_manifest_targets()
            retired_target = current_retired_targets.get(action_id)
            if retired_target is not None and retired_target != target:
                raise LifecycleCommandError(
                    "contract_input_failure",
                    "Plan retired-file target does not match the current manifest entry.",
                    4,
                    {"id": action_id, "planned": target, "current": retired_target},
                )
            if retired_target is None and action_id != f"migration.cleanup.{target}":
                raise LifecycleCommandError(
                    "contract_input_failure",
                    "Plan archive-retired action is not recognized for the current workspace.",
                    4,
                    {"id": action_id, "target": target},
                )
        else:
            raise LifecycleCommandError(
                "contract_input_failure",
                "Plan file contains an unsupported action type.",
                4,
                {"id": action_id, "action": action_type},
            )

    backup_plan = result.get("backupPlan", {})
    backup_root = backup_plan.get("root")
    if backup_root is not None:
        backup_root = _validate_relative_plan_path(backup_root, "result.backupPlan.root")
        if not backup_root.startswith(".xanadAssistant/backups/"):
            raise LifecycleCommandError(
                "contract_input_failure",
                "Plan backup root does not match the lifecycle contract.",
                4,
                {"planned": backup_root},
            )

    archive_root = backup_plan.get("archiveRoot")
    if archive_root is not None:
        archive_root = _validate_relative_plan_path(archive_root, "result.backupPlan.archiveRoot")

    for index, entry in enumerate(backup_plan.get("targets", [])):
        target = _validate_relative_plan_path(entry.get("target"), f"result.backupPlan.targets[{index}].target")
        backup_path = _validate_relative_plan_path(entry.get("backupPath"), f"result.backupPlan.targets[{index}].backupPath")
        if target not in action_targets:
            raise LifecycleCommandError(
                "contract_input_failure",
                "Plan backup target is not referenced by the serialized action set.",
                4,
                {"target": target},
            )
        if backup_root is not None and not backup_path.startswith(f"{backup_root}/"):
            raise LifecycleCommandError(
                "contract_input_failure",
                "Plan backup path does not stay under the declared backup root.",
                4,
                {"target": target, "backupPath": backup_path, "backupRoot": backup_root},
            )

    for index, entry in enumerate(backup_plan.get("archiveTargets", [])):
        target = _validate_relative_plan_path(entry.get("target"), f"result.backupPlan.archiveTargets[{index}].target")
        archive_path = _validate_relative_plan_path(entry.get("archivePath"), f"result.backupPlan.archiveTargets[{index}].archivePath")
        if target not in action_targets:
            raise LifecycleCommandError(
                "contract_input_failure",
                "Plan archive target is not referenced by the serialized action set.",
                4,
                {"target": target},
            )
        if archive_root is not None and not archive_path.startswith(f"{archive_root}/"):
            raise LifecycleCommandError(
                "contract_input_failure",
                "Plan archive path does not stay under the declared archive root.",
                4,
                {"target": target, "archivePath": archive_path, "archiveRoot": archive_root},
            )


def load_apply_plan(plan_path: str | None, workspace: Path) -> dict:
    if not plan_path:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Apply requires --plan pointing to a serialized lifecycle plan.",
            4,
            {"workspace": str(workspace)},
        )

    path = Path(plan_path).resolve()
    if not path.is_file():
        raise LifecycleCommandError(
            "contract_input_failure",
            f"Plan file does not exist: {path}",
            4,
            {"path": str(path)},
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise LifecycleCommandError(
            "contract_input_failure",
            f"Cannot parse plan file {path!r}: {exc}",
            4,
            {"path": str(path), "error": str(exc)},
        ) from exc

    if not isinstance(payload, dict):
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan file must contain a JSON object payload.",
            4,
            {"path": str(path)},
        )

    if payload.get("command") != "plan" or not isinstance(payload.get("result"), dict):
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan file is not a valid serialized lifecycle plan.",
            4,
            {"path": str(path)},
        )

    if payload.get("workspace") != str(workspace):
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan file workspace does not match the apply target workspace.",
            4,
            {"path": str(path), "planWorkspace": payload.get("workspace"), "workspace": str(workspace)},
        )

    mode = payload.get("mode")
    if mode not in {"setup", "update", "repair", "factory-restore"}:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan file has an unsupported lifecycle mode.",
            4,
            {"path": str(path), "mode": mode},
        )

    if payload.get("result", {}).get("plannedLockfile") is None:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan file is incomplete and cannot be applied.",
            4,
            {"path": str(path)},
        )

    planned_lockfile = payload["result"].get("plannedLockfile")
    if not isinstance(planned_lockfile, dict):
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan file has an invalid planned lockfile payload.",
            4,
            {"path": str(path)},
        )

    if not isinstance(planned_lockfile.get("path"), str) or not isinstance(planned_lockfile.get("contents"), dict):
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan file is missing required planned lockfile fields.",
            4,
            {"path": str(path)},
        )

    return payload


def validate_apply_plan_package(plan_payload: dict, package_root: Path) -> None:
    planned_lockfile = plan_payload["result"]["plannedLockfile"]["contents"]
    planned_package = planned_lockfile.get("package", {})
    planned_manifest = planned_lockfile.get("manifest", {})

    if planned_package.get("name") not in {None, CURRENT_PACKAGE_NAME}:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan package name does not match the current lifecycle package.",
            4,
            {"planned": planned_package.get("name"), "current": CURRENT_PACKAGE_NAME},
        )

    current_source = build_source_summary(package_root)
    for field in ("source", "ref", "version"):
        planned_value = planned_package.get(field)
        current_value = current_source.get(field)
        if planned_value is not None and current_value is not None and planned_value != current_value:
            raise LifecycleCommandError(
                "contract_input_failure",
                "Plan package source does not match the current apply package source.",
                4,
                {"field": field, "planned": planned_value, "current": current_value},
            )

    current_manifest = load_manifest(package_root, load_json(package_root / DEFAULT_POLICY_PATH)) or {"managedFiles": []}
    current_manifest_hash = sha256_json(current_manifest)
    if planned_manifest.get("hash") != current_manifest_hash:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Plan manifest hash does not match the current apply package state.",
            4,
            {
                "plannedManifestHash": planned_manifest.get("hash"),
                "currentManifestHash": current_manifest_hash,
            },
        )


def build_execution_result(
    command: str, mode: str, workspace: Path, package_root: Path,
    answers_path: str | None, non_interactive: bool, dry_run: bool = False,
    resolutions_path: str | None = None,
) -> dict:
    plan_payload = build_plan_result(workspace, package_root, mode, answers_path, non_interactive, resolutions_path=resolutions_path)
    if plan_payload["result"].get("conflictDetails"):
        raise LifecycleCommandError(
            "approval_or_answers_required",
            "Pack token conflicts must be resolved before applying.", 6,
            {"questionIds": [c["questionId"] for c in plan_payload["result"]["conflictDetails"]]},
        )
    apply_result = execute_apply_plan(workspace, package_root, plan_payload, dry_run=dry_run)
    return {
        "command": command, "mode": mode,
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "ok",
        "warnings": plan_payload["warnings"],
        "errors": [],
        "result": apply_result,
    }


def build_apply_result(
    workspace: Path, package_root: Path, answers_path: str | None,
    non_interactive: bool, dry_run: bool = False, resolutions_path: str | None = None,
    plan_path: str | None = None,
) -> dict:
    if resolutions_path is not None:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Apply does not accept --resolutions; conflict decisions must be recorded in the serialized plan.",
            4,
            {"argument": "--resolutions"},
        )
    plan_payload = load_apply_plan(plan_path, workspace)
    validate_apply_plan_paths(plan_payload, package_root)
    validate_apply_plan_package(plan_payload, package_root)
    if plan_payload["result"].get("conflictDetails"):
        raise LifecycleCommandError(
            "approval_or_answers_required",
            "Pack token conflicts must be resolved before applying.",
            6,
            {"questionIds": [c["questionId"] for c in plan_payload["result"]["conflictDetails"]]},
        )
    apply_result = execute_apply_plan(workspace, package_root, plan_payload, dry_run=dry_run)
    return {
        "command": "apply",
        "mode": plan_payload["mode"],
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "ok",
        "warnings": plan_payload.get("warnings", []),
        "errors": [],
        "result": apply_result,
    }
