from __future__ import annotations

import json
from pathlib import Path

from scripts.lifecycle._xanad._conditions import entry_required_for_plan, render_tokenized_text
from scripts.lifecycle._xanad._loader import load_json
from scripts.lifecycle._xanad._merge import (
    merge_json_objects,
    merge_markdown_with_preserved_blocks,
    serialize_json_object,
    sha256_bytes,
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
            return source_path.read_bytes()
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
        if target_path is None or not target_path.exists():
            return source_path.read_bytes()
        existing_text = target_path.read_text(encoding="utf-8")
        return merge_markdown_with_preserved_blocks(existing_text, source_text).encode("utf-8")

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

    backup_root = ".xanad-assistant/backups/<apply-timestamp>"
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
