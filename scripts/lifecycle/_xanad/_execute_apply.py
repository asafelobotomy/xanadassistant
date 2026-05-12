from __future__ import annotations

import json
import shutil
from pathlib import Path

import scripts.lifecycle._xanad._check as _check

from scripts.lifecycle._xanad._apply import (
    apply_chmod_rule, build_copilot_version_summary, generate_apply_timestamps,
    materialize_apply_timestamp, merge_json_object_file, merge_markdown_file,
    render_entry_bytes,
)
from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH, LifecycleCommandError
from scripts.lifecycle._xanad._inspect import collect_unmanaged_files
from scripts.lifecycle._xanad._loader import load_json, load_manifest
from scripts.lifecycle._xanad._plan_b import build_plan_result
from scripts.lifecycle._xanad._source import build_source_summary


def execute_apply_plan(workspace: Path, package_root: Path, plan_payload: dict, dry_run: bool = False) -> dict:
    manifest = load_manifest(package_root, load_json(package_root / DEFAULT_POLICY_PATH)) or {"managedFiles": []}
    manifest_entries = {entry["id"]: entry for entry in manifest.get("managedFiles", [])}
    actions = plan_payload["result"].get("actions", [])
    backup_plan = plan_payload["result"].get("backupPlan", {})
    planned_lockfile = json.loads(json.dumps(plan_payload["result"]["plannedLockfile"]))
    factory_restore = bool(plan_payload["result"].get("factoryRestore", False))
    apply_timestamp, path_timestamp = generate_apply_timestamps()

    if dry_run:
        plan_writes = plan_payload["result"].get("writes", {})
        skipped_count = len(plan_payload["result"].get("skippedActions", []))
        return {
            "backup": {"created": False, "path": None},
            "writes": {
                "added": plan_writes.get("add", 0), "replaced": plan_writes.get("replace", 0),
                "merged": plan_writes.get("merge", 0),
                "retiredArchived": plan_writes.get("archiveRetired", 0),
                "retiredReported": 0, "skipped": skipped_count,
            },
            "retired": [],
            "lockfile": {"written": False, "path": planned_lockfile["path"]},
            "summary": {"written": False, "path": ".github/copilot-version.md"},
            "validation": {"status": "skipped"},
            "dryRun": True,
        }

    backup_root = materialize_apply_timestamp(backup_plan.get("root"), path_timestamp)
    if backup_root is not None:
        (workspace / backup_root).mkdir(parents=True, exist_ok=True)

    for backup_target in backup_plan.get("targets", []):
        source_path = workspace / backup_target["target"]
        if not source_path.exists():
            continue
        backup_path = materialize_apply_timestamp(backup_target["backupPath"], path_timestamp)
        if backup_path is None:
            continue
        destination = workspace / backup_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)

    if factory_restore:
        managed_targets = {entry["target"] for entry in manifest.get("managedFiles", [])}
        unmanaged_files = collect_unmanaged_files(workspace, manifest, managed_targets)
        for relative_path in unmanaged_files:
            source_path = workspace / relative_path
            if backup_root is not None and source_path.exists():
                backup_path = workspace / backup_root / relative_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, backup_path)
            if source_path.exists():
                source_path.unlink()

    archive_targets_map = {
        entry["target"]: entry["archivePath"]
        for entry in backup_plan.get("archiveTargets", [])
    }
    retired_records: list[dict] = []
    writes = {
        "added": 0, "replaced": 0, "merged": 0,
        "retiredArchived": 0, "retiredReported": 0,
        "skipped": len(plan_payload["result"].get("skippedActions", [])),
    }

    try:
        for action in actions:
            if action["action"] == "archive-retired":
                target_path = workspace / action["target"]
                if action.get("strategy", "archive-retired") == "report-retired":
                    retired_records.append({"target": action["target"], "action": "reported"})
                    writes["retiredReported"] += 1
                else:
                    archive_path_str = archive_targets_map.get(action["target"])
                    if archive_path_str is not None:
                        archive_dest = workspace / archive_path_str
                        archive_dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(target_path), archive_dest)
                    elif target_path.exists():
                        target_path.unlink()
                    retired_records.append({
                        "target": action["target"], "action": "archived",
                        "archivePath": archive_path_str,
                    })
                    writes["retiredArchived"] += 1
                continue
            if action["action"] == "merge" and action["strategy"] not in {"merge-json-object", "preserve-marked-markdown-blocks"}:
                raise LifecycleCommandError(
                    "apply_failure", "Merge actions are not implemented in the current apply slice.", 9,
                    {"target": action["target"], "strategy": action["strategy"]},
                )

            manifest_entry = manifest_entries.get(action["id"])
            if manifest_entry is None:
                raise LifecycleCommandError(
                    "apply_failure", "Plan references a managed entry missing from the manifest.", 9,
                    {"id": action["id"]},
                )

            target_path = workspace / action["target"]
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if action["action"] == "merge":
                if action["strategy"] == "merge-json-object":
                    merge_json_object_file(target_path, package_root, manifest_entry)
                else:
                    merge_markdown_file(target_path, package_root, manifest_entry, action.get("tokenValues", {}))
                writes["merged"] += 1
                continue

            target_path.write_bytes(render_entry_bytes(package_root, manifest_entry, action.get("tokenValues", {})))
            apply_chmod_rule(target_path, manifest_entry.get("chmod", "none"))
            if action["action"] == "add":
                writes["added"] += 1
            elif action["action"] == "replace":
                writes["replaced"] += 1
    except LifecycleCommandError:
        raise
    except Exception as exc:
        raise LifecycleCommandError(
            "apply_failure",
            f"Workspace write failed mid-apply, partial state may exist: {exc}",
            9,
            {"backupPath": str(backup_root) if backup_root is not None else None},
        ) from exc

    planned_lockfile["contents"]["timestamps"] = {
        "appliedAt": apply_timestamp, "updatedAt": apply_timestamp,
    }
    if "lastBackup" in planned_lockfile["contents"]:
        planned_lockfile["contents"]["lastBackup"]["path"] = materialize_apply_timestamp(
            planned_lockfile["contents"]["lastBackup"]["path"], path_timestamp,
        )

    lockfile_path = workspace / planned_lockfile["path"]
    if backup_root is not None and lockfile_path.exists():
        lockfile_backup = workspace / backup_root / planned_lockfile["path"]
        lockfile_backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(lockfile_path, lockfile_backup)
    lockfile_path.parent.mkdir(parents=True, exist_ok=True)
    lockfile_path.write_text(json.dumps(planned_lockfile["contents"], indent=2) + "\n", encoding="utf-8")

    summary_path = workspace / ".github" / "copilot-version.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        build_copilot_version_summary(planned_lockfile["contents"], manifest), encoding="utf-8",
    )

    validation = _check.build_check_result(workspace, package_root)
    if validation["status"] != "clean":
        raise LifecycleCommandError(
            "apply_failure", "Applied workspace did not validate cleanly.", 9,
            {"backupPath": backup_root, "summary": validation["result"]["summary"]},
        )

    return {
        "backup": {"created": backup_root is not None, "path": backup_root},
        "writes": writes, "retired": retired_records,
        "lockfile": {"written": True, "path": planned_lockfile["path"]},
        "summary": {"written": True, "path": ".github/copilot-version.md"},
        "validation": {"status": "passed"},
    }


def build_execution_result(
    command: str, mode: str, workspace: Path, package_root: Path,
    answers_path: str | None, non_interactive: bool, dry_run: bool = False,
) -> dict:
    plan_payload = build_plan_result(workspace, package_root, mode, answers_path, non_interactive)
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
    non_interactive: bool, dry_run: bool = False,
) -> dict:
    return build_execution_result("apply", "setup", workspace, package_root, answers_path, non_interactive, dry_run=dry_run)
