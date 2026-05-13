from __future__ import annotations

import json
import sys
from pathlib import Path


def load_resolutions(path: str | None) -> dict[str, str]:
    """Load a conflict-resolutions.json file, returning {} when absent or None."""
    if path is None:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        sys.exit(f"[xanadAssistant] Cannot parse resolutions file {path!r}: {exc}")
    if not isinstance(data, dict):
        sys.exit(f"[xanadAssistant] Resolutions file must be a JSON object: {path!r}")
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            sys.exit(
                f"[xanadAssistant] Resolutions file keys and values must be strings: {path!r}"
            )
    return data


def validate_resolutions(
    resolutions: dict[str, str],
    existing_files: list[dict],
) -> tuple[dict[str, str], list[dict]]:
    """Return (valid_resolutions, warnings) after checking decisions against available choices."""
    available_by_path: dict[str, list[str]] = {
        record["path"]: record["availableDecisions"]
        for record in existing_files
    }
    valid: dict[str, str] = {}
    warnings: list[dict] = []
    for path, decision in resolutions.items():
        if path not in available_by_path:
            warnings.append({
                "code": "resolution_unknown_path",
                "message": f"Resolution for unknown path ignored: {path!r}",
                "details": {"path": path, "decision": decision},
            })
            continue
        if decision not in available_by_path[path]:
            warnings.append({
                "code": "resolution_invalid_decision",
                "message": (
                    f"Invalid decision {decision!r} for {path!r}; entry dropped."
                ),
                "details": {
                    "path": path,
                    "decision": decision,
                    "available": available_by_path[path],
                },
            })
            continue
        valid[path] = decision
    return valid, warnings


def apply_resolutions_to_plan_actions(
    actions: list[dict],
    skipped_actions: list[dict],
    resolutions: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    """Re-classify actions according to consumer resolutions.

    "keep"    → move action to skipped with reason "consumer-keep"
    "merge"   → change action field to "merge"
    "replace" → keep action as-is (xanadAssistant wins)
    "update"  → keep action as-is (consumer accepted the updated source)
    no entry  → keep action as-is
    """
    if not resolutions:
        return actions, skipped_actions
    new_actions: list[dict] = []
    new_skipped: list[dict] = list(skipped_actions)
    for action in actions:
        target = action["target"]
        decision = resolutions.get(target)
        if decision == "keep":
            skipped = dict(action)
            skipped["reason"] = "consumer-keep"
            new_skipped.append(skipped)
        elif decision == "merge":
            merged = dict(action)
            merged["action"] = "merge"
            new_actions.append(merged)
        else:
            new_actions.append(action)
    return new_actions, new_skipped


def build_delete_actions(
    workspace: Path,
    resolutions: dict[str, str],
    existing_files: list[dict],
) -> list[dict]:
    """Build delete actions for unmanaged files the consumer chose to remove."""
    unmanaged_by_path: dict[str, dict] = {
        record["path"]: record
        for record in existing_files
        if record["type"] == "unmanaged"
    }
    delete_actions: list[dict] = []
    for path, decision in resolutions.items():
        if decision != "remove":
            continue
        record = unmanaged_by_path.get(path)
        if record is None:
            continue
        if not (workspace / path).exists():
            continue
        delete_actions.append({
            "id": f"delete:{path}",
            "surface": record["surface"],
            "target": path,
            "action": "delete",
            "strategy": "delete",
            "ownershipMode": "local",
            "tokens": [],
            "tokenValues": {},
        })
    return delete_actions
