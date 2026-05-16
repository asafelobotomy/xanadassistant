from __future__ import annotations

import json
import shutil
from pathlib import Path

import scripts.lifecycle._xanad._check as _check

from scripts.lifecycle._xanad._apply import (
    apply_chmod_rule,
    build_copilot_version_summary,
    generate_apply_timestamps,
    materialize_apply_timestamp,
    merge_json_object_file,
    merge_markdown_file,
    render_entry_bytes,
)
from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH, LifecycleCommandError
from scripts.lifecycle._xanad._inspect import collect_unmanaged_files
from scripts.lifecycle._xanad._loader import load_json, load_manifest


def _apply_memory_gitignore(workspace: Path, setup_answers: dict) -> None:
    if not setup_answers.get("memory.gitignore"):
        return
    entry = ".github/xanadAssistant/memory/"
    gitignore_path = workspace / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines()]
        if entry in lines or entry.rstrip("/") in lines:
            return
        gitignore_path.write_text(content.rstrip("\n") + "\n" + entry + "\n", encoding="utf-8")
        return
    gitignore_path.write_text(entry + "\n", encoding="utf-8")


def _snapshot_file(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def _restore_snapshot(path: Path, snapshot: bytes | None) -> None:
    if snapshot is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(snapshot)


def _copy_backup_file(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination_path)


def _write_lockfile(path: Path, contents: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contents, indent=2) + "\n", encoding="utf-8")


def _write_summary(path: Path, lockfile_contents: dict, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_copilot_version_summary(lockfile_contents, manifest), encoding="utf-8")


def _rollback_apply(
    workspace: Path,
    backup_root: str | None,
    created_paths: set[str],
    archive_paths: set[str],
    snapshots: dict[str, bytes | None],
) -> None:
    for relative_path in sorted(archive_paths):
        (workspace / relative_path).unlink(missing_ok=True)

    for relative_path, snapshot in snapshots.items():
        _restore_snapshot(workspace / relative_path, snapshot)

    if backup_root is not None:
        backup_root_path = workspace / backup_root
        if backup_root_path.exists():
            for backup_path in sorted(backup_root_path.rglob("*")):
                if not backup_path.is_file():
                    continue
                restore_path = workspace / backup_path.relative_to(backup_root_path)
                restore_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, restore_path)

    for relative_path in sorted(created_paths):
        (workspace / relative_path).unlink(missing_ok=True)


def _rollback_metadata(
    workspace: Path,
    backup_root: str | None,
    created_paths: set[str],
    archive_paths: set[str],
    snapshots: dict[str, bytes | None],
) -> dict:
    try:
        _rollback_apply(workspace, backup_root, created_paths, archive_paths, snapshots)
    except Exception as rollback_error:  # pragma: no cover - defensive path
        return {
            "backupPath": backup_root,
            "rolledBack": False,
            "rollbackError": str(rollback_error),
        }
    return {"backupPath": backup_root, "rolledBack": True}


def _build_dry_run_result(plan_payload: dict, planned_lockfile: dict) -> dict:
    plan_writes = plan_payload["result"].get("writes", {})
    skipped_count = len(plan_payload["result"].get("skippedActions", []))
    return {
        "backup": {"created": False, "path": None},
        "writes": {
            "added": plan_writes.get("add", 0),
            "replaced": plan_writes.get("replace", 0),
            "merged": plan_writes.get("merge", 0),
            "retiredArchived": plan_writes.get("archiveRetired", 0),
            "deleted": plan_writes.get("deleted", 0),
            "retiredReported": 0,
            "skipped": skipped_count,
        },
        "retired": [],
        "lockfile": {"written": False, "path": planned_lockfile["path"]},
        "summary": {"written": False, "path": ".github/copilot-version.md"},
        "validation": {"status": "skipped"},
        "dryRun": True,
    }


def execute_apply_plan(workspace: Path, package_root: Path, plan_payload: dict, dry_run: bool = False) -> dict:
    manifest = load_manifest(package_root, load_json(package_root / DEFAULT_POLICY_PATH)) or {"managedFiles": []}
    manifest_entries = {entry["id"]: entry for entry in manifest.get("managedFiles", [])}
    actions = plan_payload["result"].get("actions", [])
    backup_plan = plan_payload["result"].get("backupPlan", {})
    planned_lockfile = json.loads(json.dumps(plan_payload["result"]["plannedLockfile"]))
    factory_restore = bool(plan_payload["result"].get("factoryRestore", False))
    apply_timestamp, path_timestamp = generate_apply_timestamps()

    if dry_run:
        return _build_dry_run_result(plan_payload, planned_lockfile)

    backup_root = materialize_apply_timestamp(backup_plan.get("root"), path_timestamp)
    archive_targets_map = {
        entry["target"]: entry["archivePath"]
        for entry in backup_plan.get("archiveTargets", [])
    }
    retired_records: list[dict] = []
    writes = {
        "added": 0,
        "replaced": 0,
        "merged": 0,
        "retiredArchived": 0,
        "retiredReported": 0,
        "deleted": 0,
        "skipped": len(plan_payload["result"].get("skippedActions", [])),
    }
    created_paths: set[str] = set()
    archive_paths: set[str] = set()
    snapshots: dict[str, bytes | None] = {}

    def remember_snapshot(relative_path: str) -> None:
        snapshots.setdefault(relative_path, _snapshot_file(workspace / relative_path))

    try:
        if backup_root is not None:
            (workspace / backup_root).mkdir(parents=True, exist_ok=True)

        for backup_target in backup_plan.get("targets", []):
            source_path = workspace / backup_target["target"]
            if not source_path.exists():
                continue
            backup_path = materialize_apply_timestamp(backup_target["backupPath"], path_timestamp)
            if backup_path is None:
                continue
            _copy_backup_file(source_path, workspace / backup_path)

        if factory_restore:
            managed_targets = {entry["target"] for entry in manifest.get("managedFiles", [])}
            unmanaged_files = collect_unmanaged_files(workspace, manifest, managed_targets)
            for relative_path in unmanaged_files:
                source_path = workspace / relative_path
                if backup_root is not None and source_path.exists():
                    _copy_backup_file(source_path, workspace / backup_root / relative_path)
                if source_path.exists():
                    source_path.unlink()

        for action in actions:
            if action["action"] == "archive-retired":
                target_path = workspace / action["target"]
                if action.get("strategy", "archive-retired") == "report-retired":
                    retired_records.append({"target": action["target"], "action": "reported"})
                    writes["retiredReported"] += 1
                    continue

                archive_path_str = archive_targets_map.get(action["target"])
                if target_path.exists() and backup_root is not None:
                    _copy_backup_file(target_path, workspace / backup_root / action["target"])
                if archive_path_str is not None:
                    archive_dest = workspace / archive_path_str
                    archive_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(target_path), archive_dest)
                    archive_paths.add(archive_path_str)
                elif target_path.exists():
                    target_path.unlink()
                retired_records.append({
                    "target": action["target"],
                    "action": "archived",
                    "archivePath": archive_path_str,
                })
                writes["retiredArchived"] += 1
                continue

            if action["action"] == "delete":
                target_path = workspace / action["target"]
                if not target_path.exists():
                    continue
                if backup_root is not None:
                    _copy_backup_file(target_path, workspace / backup_root / action["target"])
                target_path.unlink()
                writes["deleted"] += 1
                continue

            if action["action"] == "merge" and action["strategy"] not in {"merge-json-object", "preserve-marked-markdown-blocks"}:
                raise LifecycleCommandError(
                    "apply_failure",
                    "Merge actions are not implemented in the current apply slice.",
                    9,
                    {"target": action["target"], "strategy": action["strategy"]},
                )

            manifest_entry = manifest_entries.get(action["id"])
            if manifest_entry is None:
                raise LifecycleCommandError(
                    "apply_failure",
                    "Plan references a managed entry missing from the manifest.",
                    9,
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
                created_paths.add(action["target"])
            elif action["action"] == "replace":
                writes["replaced"] += 1

        planned_lockfile["contents"]["timestamps"] = {
            "appliedAt": apply_timestamp,
            "updatedAt": apply_timestamp,
        }
        if "lastBackup" in planned_lockfile["contents"]:
            planned_lockfile["contents"]["lastBackup"]["path"] = materialize_apply_timestamp(
                planned_lockfile["contents"]["lastBackup"]["path"],
                path_timestamp,
            )

        remember_snapshot(planned_lockfile["path"])
        _write_lockfile(workspace / planned_lockfile["path"], planned_lockfile["contents"])
        if snapshots[planned_lockfile["path"]] is None:
            created_paths.add(planned_lockfile["path"])

        remember_snapshot(".github/copilot-version.md")
        _write_summary(workspace / ".github" / "copilot-version.md", planned_lockfile["contents"], manifest)
        if snapshots[".github/copilot-version.md"] is None:
            created_paths.add(".github/copilot-version.md")

        remember_snapshot(".gitignore")
        _apply_memory_gitignore(workspace, planned_lockfile["contents"].get("setupAnswers", {}))
        if snapshots[".gitignore"] is None and (workspace / ".gitignore").exists():
            created_paths.add(".gitignore")

        validation = _check.build_check_result(workspace, package_root)
        if validation["status"] != "clean":
            details = _rollback_metadata(workspace, backup_root, created_paths, archive_paths, snapshots)
            details["summary"] = validation["result"]["summary"]
            raise LifecycleCommandError(
                "apply_failure",
                "Applied workspace did not validate cleanly.",
                9,
                details,
            )
    except LifecycleCommandError as error:
        if isinstance(error.details, dict) and "rolledBack" in error.details:
            raise
        details = dict(error.details or {})
        details.update(_rollback_metadata(workspace, backup_root, created_paths, archive_paths, snapshots))
        raise LifecycleCommandError(
            error.code,
            error.message,
            error.exit_code,
            details,
        ) from error
    except Exception as exc:
        details = _rollback_metadata(workspace, backup_root, created_paths, archive_paths, snapshots)
        raise LifecycleCommandError(
            "apply_failure",
            f"Workspace write failed mid-apply and was rolled back: {exc}",
            9,
            details,
        ) from exc

    return {
        "backup": {"created": backup_root is not None, "path": backup_root},
        "writes": writes,
        "retired": retired_records,
        "lockfile": {"written": True, "path": planned_lockfile["path"]},
        "summary": {"written": True, "path": ".github/copilot-version.md"},
        "validation": {"status": "passed"},
    }