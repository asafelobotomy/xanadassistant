from __future__ import annotations

import json
from pathlib import Path

from scripts.lifecycle._xanad._conditions import entry_required_for_plan, render_tokenized_text
from scripts.lifecycle._xanad._errors import _State
from scripts.lifecycle._xanad._loader import load_json
from scripts.lifecycle._xanad._merge import (
    merge_json_objects,
    merge_markdown_with_preserved_blocks,
    serialize_json_object,
    sha256_bytes,
    sha256_json,
)


def expected_entry_bytes(
    package_root: Path,
    entry: dict,
    token_values: dict[str, str],
    target_path: Path | None = None,
) -> bytes | None:
    source_path = package_root / entry["source"]
    strategy = entry.get("strategy")

    if strategy == "token-replace":
        rendered_text = render_tokenized_text(source_path.read_text(encoding="utf-8"), token_values)
        return rendered_text.encode("utf-8")

    if strategy == "merge-json-object":
        if target_path is None or not target_path.exists():
            source_data = load_json(source_path)
            if not isinstance(source_data, dict):
                return None
            return serialize_json_object(source_data)
        try:
            existing_data = load_json(target_path)
            source_data = load_json(source_path)
        except json.JSONDecodeError:
            return None
        if not isinstance(existing_data, dict) or not isinstance(source_data, dict):
            return None
        return serialize_json_object(merge_json_objects(existing_data, source_data))

    if strategy == "preserve-marked-markdown-blocks":
        source_text = source_path.read_text(encoding="utf-8")
        rendered_text = render_tokenized_text(source_text, token_values)
        if target_path is None or not target_path.exists():
            return rendered_text.encode("utf-8")
        existing_text = target_path.read_text(encoding="utf-8")
        return merge_markdown_with_preserved_blocks(existing_text, rendered_text).encode("utf-8")

    return source_path.read_bytes()


def expected_entry_hash(
    package_root: Path,
    entry: dict,
    token_values: dict[str, str],
    target_path: Path | None = None,
) -> str | None:
    expected_bytes = expected_entry_bytes(package_root, entry, token_values, target_path)
    if expected_bytes is None:
        return None
    return sha256_bytes(expected_bytes)


def build_token_plan_summary(policy: dict, actions: list[dict], token_values: dict[str, str]) -> list[dict]:
    active_targets_by_token: dict[str, list[str]] = {}
    token_requirements = {rule["token"]: rule for rule in policy.get("tokenRules", [])}

    for action in actions:
        for token in action.get("tokens", []):
            active_targets_by_token.setdefault(token, []).append(action["target"])

    summary = []
    for token in sorted(active_targets_by_token):
        summary.append(
            {
                "token": token,
                "value": token_values.get(token),
                "required": bool(token_requirements.get(token, {}).get("required", False)),
                "targets": sorted(active_targets_by_token[token]),
            }
        )
    return summary


def build_backup_plan(policy: dict, actions: list[dict], backup_required: bool) -> dict:
    archive_root = policy.get("retiredFilePolicy", {}).get("archiveRoot")
    if not backup_required:
        return {
            "required": False,
            "root": None,
            "targets": [],
            "archiveRoot": archive_root,
            "archiveTargets": [],
        }

    backup_root = ".xanadAssistant/backups/<apply-timestamp>"
    backup_targets = []
    archive_targets = []

    for action in actions:
        if action["action"] in {"replace", "merge"}:
            backup_targets.append(
                {
                    "target": action["target"],
                    "action": action["action"],
                    "backupPath": f"{backup_root}/{action['target']}",
                }
            )
        elif action["action"] == "delete":
            backup_targets.append(
                {
                    "target": action["target"],
                    "action": "delete",
                    "backupPath": f"{backup_root}/{action['target']}",
                }
            )
        elif (
            action["action"] == "archive-retired"
            and action.get("strategy", "archive-retired") != "report-retired"
            and archive_root is not None
        ):
            archive_targets.append(
                {
                    "target": action["target"],
                    "archivePath": f"{archive_root}/{action['target']}",
                }
            )

    return {
        "required": True,
        "root": backup_root,
        "targets": backup_targets,
        "archiveRoot": archive_root,
        "archiveTargets": archive_targets,
    }


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
    consumer_resolutions: dict | None = None,
) -> dict:
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
        "consumerResolutions": consumer_resolutions or {},
        "unknownValues": {},
    }
    if backup_plan.get("required") and backup_plan.get("root"):
        lockfile_contents["lastBackup"] = {"path": backup_plan["root"]}

    return {"path": ".github/xanadAssistant-lock.json", "contents": lockfile_contents}
