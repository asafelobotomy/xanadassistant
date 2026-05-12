from __future__ import annotations

from pathlib import Path

from scripts.lifecycle._xanad._inspect import collect_context
from scripts.lifecycle._xanad._inspect_helpers import (
    classify_manifest_entries,
    collect_unmanaged_files,
)
from scripts.lifecycle._xanad._source import build_source_summary


def build_check_result(workspace: Path, package_root: Path) -> dict:
    context = collect_context(workspace, package_root)
    counts, entries, managed_targets = classify_manifest_entries(workspace, context["manifestWithStatus"])
    unmanaged_files = collect_unmanaged_files(workspace, context["manifestWithStatus"], managed_targets)
    counts["unmanaged"] = len(unmanaged_files)

    if context["lockfileState"]["malformed"]:
        counts["malformed"] += 1
    if context["legacyVersionState"]["malformed"]:
        counts["malformed"] += 1

    skipped_files = context["lockfileState"].get("skippedManagedFiles", [])
    recorded_targets = {entry["target"] for entry in entries}
    for skipped_target in skipped_files:
        if skipped_target in recorded_targets:
            continue
        counts["skipped"] += 1
        entries.append({"id": skipped_target, "target": skipped_target, "status": "skipped"})

    unknown_values = context["lockfileState"].get("unknownValues", {})
    unknown_count = len(unknown_values)
    for file_record in context["lockfileState"].get("files", []):
        if file_record.get("status") == "unknown" or file_record.get("installedHash") == "unknown":
            unknown_count += 1
            entries.append({
                "id": file_record.get("id", file_record.get("target", "unknown")),
                "target": file_record.get("target", "unknown"),
                "status": "unknown",
            })
    counts["unknown"] = unknown_count

    status = "clean"
    if any(counts[key] > 0 for key in ("missing", "stale", "malformed", "retired", "unmanaged", "unknown")):
        status = "drift"

    return {
        "command": "check",
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": status,
        "warnings": context["warnings"],
        "errors": [],
        "result": {
            "installState": context["installState"],
            "installPaths": context["installPaths"],
            "contracts": context["artifacts"],
            "existingSurfaces": context["existingSurfaces"],
            "legacyVersionState": context["legacyVersionState"],
            "lockfileState": context["lockfileState"],
            "summary": counts,
            "entries": entries,
            "unmanagedFiles": unmanaged_files,
        },
    }
