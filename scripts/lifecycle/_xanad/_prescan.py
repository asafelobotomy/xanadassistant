from __future__ import annotations

from pathlib import Path

_MANAGED_SCAN_DIRS: tuple[str, ...] = (
    ".github/agents",
    ".github/skills",
    ".github/prompts",
    ".github/instructions",
    ".github/hooks/scripts",
    ".vscode",
)

_MERGE_STRATEGIES: frozenset[str] = frozenset({
    "preserve-marked-markdown-blocks",
    "merge-json-object",
})

_EXCLUDE_NAMES: frozenset[str] = frozenset({
    ".xanadAssistant-lock.json",
    "xanadAssistant-lock.json",
    "copilot-version.md",
    ".complete",
})


def _infer_surface(rel_str: str) -> str:
    parts = rel_str.split("/")
    if len(parts) >= 2 and parts[0] == ".github":
        return parts[1]
    if parts[0] == ".vscode":
        return "mcp"
    return "unknown"


def scan_existing_copilot_files(workspace: Path, manifest: dict | None) -> list[dict]:
    """Return records for pre-existing files in managed directories.

    Each record describes whether the file collides with a manifest-managed
    entry or is simply unmanaged.  Callers use this to surface per-file
    decisions (keep / replace / merge / remove) before running plan/apply.
    """
    if manifest is None:
        return []

    manifest_by_target: dict[str, dict] = {
        entry["target"]: entry
        for entry in manifest.get("managedFiles", [])
    }

    results: list[dict] = []
    for scan_dir_rel in _MANAGED_SCAN_DIRS:
        scan_dir = workspace / scan_dir_rel
        if not scan_dir.is_dir():
            continue
        for file_path in sorted(scan_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name in _EXCLUDE_NAMES:
                continue
            rel_str = str(file_path.relative_to(workspace))
            entry = manifest_by_target.get(rel_str)
            if entry is not None:
                # copy-if-missing entries are never forcibly overwritten; skip.
                if entry.get("strategy") == "copy-if-missing":
                    continue
                strategy = entry.get("strategy")
                merge_strategy = strategy if strategy in _MERGE_STRATEGIES else None
                merge_supported = merge_strategy is not None
                available = ["keep", "replace"]
                if merge_supported:
                    available.append("merge")
                results.append({
                    "path": rel_str,
                    "type": "collision",
                    "conflictsWith": entry["id"],
                    "surface": entry.get("surface", _infer_surface(rel_str)),
                    "mergeSupported": merge_supported,
                    "mergeStrategy": merge_strategy,
                    "availableDecisions": available,
                })
            else:
                results.append({
                    "path": rel_str,
                    "type": "unmanaged",
                    "conflictsWith": None,
                    "surface": _infer_surface(rel_str),
                    "mergeSupported": False,
                    "mergeStrategy": None,
                    "availableDecisions": ["keep", "remove"],
                })
    return results


def scan_consumer_kept_updates(
    workspace: Path,
    manifest: dict | None,
    lockfile_state: dict,
) -> list[dict]:
    """Return records for previously-kept files whose source has since changed.

    Compares the source hash stored in the lockfile (at install time) with the
    current manifest hash.  Only files the consumer explicitly chose to keep are
    re-offered.  Files whose source is unchanged are silently re-kept.
    """
    if manifest is None:
        return []

    consumer_resolutions: dict[str, str] = lockfile_state.get("consumerResolutions", {})
    if not consumer_resolutions:
        return []

    lockfile_source_hashes: dict[str, str] = {
        f["target"]: f.get("sourceHash", "")
        for f in lockfile_state.get("files", [])
    }

    manifest_by_target: dict[str, dict] = {
        entry["target"]: entry
        for entry in manifest.get("managedFiles", [])
    }

    results: list[dict] = []
    for target, decision in consumer_resolutions.items():
        if decision != "keep":
            continue
        entry = manifest_by_target.get(target)
        if entry is None:
            # Entry removed from manifest; no longer applicable.
            continue
        stored_hash = lockfile_source_hashes.get(target, "")
        if stored_hash == entry.get("hash", ""):
            # Source unchanged; auto-keep silently.
            continue
        strategy = entry.get("strategy")
        merge_strategy = strategy if strategy in _MERGE_STRATEGIES else None
        merge_supported = merge_strategy is not None
        results.append({
            "path": target,
            "type": "consumer-kept-updated",
            "conflictsWith": entry["id"],
            "surface": entry.get("surface", _infer_surface(target)),
            "mergeSupported": merge_supported,
            "mergeStrategy": merge_strategy,
            "availableDecisions": ["keep", "update"],
        })
    return results
