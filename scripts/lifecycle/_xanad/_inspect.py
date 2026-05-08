from __future__ import annotations

from pathlib import Path

from scripts.lifecycle.generate_manifest import sha256_file
from scripts.lifecycle._xanad._conditions import entry_required_for_plan, resolve_token_values
from scripts.lifecycle._xanad._defaults import derive_effective_plan_defaults
from scripts.lifecycle._xanad._loader import load_contract_artifacts, load_discovery_metadata, load_manifest
from scripts.lifecycle._xanad._merge import sha256_json
from scripts.lifecycle._xanad._plan_utils import expected_entry_hash
from scripts.lifecycle._xanad._source import build_source_summary
from scripts.lifecycle._xanad._state import (
    CURRENT_PACKAGE_NAME,
    detect_existing_surfaces,
    detect_git_state,
    determine_install_state,
    get_lockfile_package_name,
    get_predecessor_package_name,
    parse_legacy_version_file,
    parse_lockfile_state,
    summarize_manifest_targets,
)


_SUCCESSOR_MIGRATION_ROOTS = (
    ".github/agents",
    ".github/skills",
    ".github/prompts",
    ".github/instructions",
    ".github/hooks",
    ".copilot/workspace",
)
_SUCCESSOR_MIGRATION_FILES = (
    ".mcp.json",
)


def annotate_manifest_entries(
    workspace: Path,
    package_root: Path,
    manifest: dict | None,
    ownership_by_surface: dict,
    resolved_answers: dict,
    token_values: dict[str, str],
) -> dict | None:
    if manifest is None:
        return None

    annotated_manifest = dict(manifest)
    annotated_entries = []
    for entry in manifest.get("managedFiles", []):
        annotated_entry = dict(entry)
        ownership_mode = ownership_by_surface.get(entry["surface"], entry["ownership"][0])
        if ownership_mode != "local":
            annotated_entry["status"] = "skipped"
            annotated_entry["skipReason"] = "plugin-backed-ownership"
        elif not entry_required_for_plan(entry, resolved_answers):
            annotated_entry["status"] = "skipped"
            annotated_entry["skipReason"] = "condition-not-selected"
        else:
            target_path = workspace / entry["target"]
            if not target_path.exists():
                annotated_entry["status"] = "missing"
            else:
                installed_hash = sha256_file(target_path)
                expected_hash = expected_entry_hash(package_root, entry, token_values, target_path)
                annotated_entry["status"] = (
                    "clean"
                    if expected_hash is not None and installed_hash == expected_hash
                    else "stale"
                )
        annotated_entries.append(annotated_entry)

    annotated_manifest["managedFiles"] = annotated_entries
    return annotated_manifest


def classify_manifest_entries(workspace: Path, manifest: dict | None) -> tuple[dict, list[dict], set[str]]:
    counts = {
        "clean": 0, "missing": 0, "stale": 0, "malformed": 0,
        "skipped": 0, "retired": 0, "unmanaged": 0, "unknown": 0,
    }
    entries = []
    managed_targets: set[str] = set()

    if manifest is None:
        return counts, entries, managed_targets

    for entry in manifest.get("managedFiles", []):
        target = entry["target"]
        managed_targets.add(target)
        status = entry.get("status")
        if status is None:
            raise ValueError(f"Managed manifest entry must be annotated with status before classification: {entry['id']}")

        counts[status] += 1
        entries.append({"id": entry["id"], "target": target, "status": status})

    for retired in manifest.get("retiredFiles", []):
        retired_target = retired.get("target")
        retired_action = retired.get("action", "archive-retired")
        if retired_target and (workspace / retired_target).exists() and retired_action != "report-retired":
            counts["retired"] += 1
            entries.append({"id": retired["id"], "target": retired_target, "status": "retired"})

    return counts, entries, managed_targets


def collect_unmanaged_files(workspace: Path, manifest: dict | None, managed_targets: set[str]) -> list[str]:
    if manifest is None:
        return []

    retired_targets = {entry.get("target") for entry in manifest.get("retiredFiles", [])}
    candidate_dirs = {str(Path(target).parent) for target in managed_targets}
    unmanaged: set[str] = set()

    for candidate in sorted(candidate_dirs):
        if candidate in {"", "."}:
            continue
        base_dir = workspace / candidate
        if not base_dir.exists() or not base_dir.is_dir():
            continue
        for file_path in sorted(path for path in base_dir.rglob("*") if path.is_file()):
            relative = file_path.relative_to(workspace).as_posix()
            if relative in managed_targets or relative in retired_targets:
                continue
            if relative in {".github/xanad-assistant-lock.json", ".github/copilot-version.md"}:
                continue
            unmanaged.add(relative)

    return sorted(unmanaged)


def collect_successor_migration_files(
    workspace: Path,
    manifest: dict | None,
    lockfile_state: dict,
    legacy_version_state: dict,
) -> list[str]:
    if manifest is None:
        return []

    predecessor_package = get_predecessor_package_name(lockfile_state)
    predecessor_markers = predecessor_package is not None or legacy_version_state.get("present", False)
    if not predecessor_markers:
        marker_paths = [workspace / ".github" / "hooks" / "copilot-hooks.json", workspace / ".mcp.json", workspace / ".copilot" / "workspace"]
        predecessor_markers = any(path.exists() for path in marker_paths)
    if not predecessor_markers:
        return []

    managed_targets = {entry.get("target") for entry in manifest.get("managedFiles", [])}
    retired_targets = {entry.get("target") for entry in manifest.get("retiredFiles", [])}
    excluded = managed_targets | retired_targets | {
        ".github/xanad-assistant-lock.json",
        ".github/copilot-version.md",
    }
    cleanup_targets: set[str] = set()

    for root in _SUCCESSOR_MIGRATION_ROOTS:
        root_path = workspace / root
        if not root_path.exists():
            continue
        for file_path in sorted(path for path in root_path.rglob("*") if path.is_file()):
            relative = file_path.relative_to(workspace).as_posix()
            if relative not in excluded:
                cleanup_targets.add(relative)

    for relative in _SUCCESSOR_MIGRATION_FILES:
        file_path = workspace / relative
        if file_path.exists() and relative not in excluded:
            cleanup_targets.add(relative)

    return sorted(cleanup_targets)


def collect_context(workspace: Path, package_root: Path) -> dict:
    warnings: list[dict] = []
    policy, artifacts = load_contract_artifacts(package_root)
    metadata, metadata_artifacts = load_discovery_metadata(package_root)
    manifest = load_manifest(package_root, policy)
    install_state, install_paths = determine_install_state(workspace)
    legacy_version_state = parse_legacy_version_file(workspace)
    lockfile_state = parse_lockfile_state(workspace)
    default_answers, ownership_by_surface = derive_effective_plan_defaults(policy, metadata, manifest, lockfile_state)
    token_values = resolve_token_values(policy, workspace, default_answers)
    manifest_with_status = annotate_manifest_entries(
        workspace, package_root, manifest, ownership_by_surface, default_answers, token_values,
    )
    manifest_summary = summarize_manifest_targets(workspace, manifest_with_status)

    if not artifacts["manifest"]["loaded"]:
        warnings.append({
            "code": "manifest_missing",
            "message": "Generated manifest not found at package root.",
            "details": {"path": artifacts["manifest"]["path"]},
        })

    if (
        install_state == "installed"
        and not lockfile_state.get("malformed")
        and manifest is not None
    ):
        installed_manifest_hash = lockfile_state.get("data", {}).get("manifest", {}).get("hash")
        if installed_manifest_hash:
            current_manifest_hash = sha256_json(manifest)
            if current_manifest_hash != installed_manifest_hash:
                warnings.append({
                    "code": "package_version_changed",
                    "message": (
                        "The resolved package manifest differs from the installed lockfile. "
                        "Run 'update' to apply the latest package version."
                    ),
                    "details": {
                        "installedHash": installed_manifest_hash,
                        "currentHash": current_manifest_hash,
                    },
                })

    installed_package_name = lockfile_state.get("originalPackageName") or get_lockfile_package_name(lockfile_state)
    if installed_package_name is not None and installed_package_name != CURRENT_PACKAGE_NAME:
        warnings.append({
            "code": "package_name_mismatch",
            "message": (
                "The installed lockfile belongs to a predecessor package and requires successor migration. "
                "Run 'repair' or 'update' to adopt xanad-assistant ownership."
            ),
            "details": {
                "installedPackageName": installed_package_name,
                "currentPackageName": CURRENT_PACKAGE_NAME,
            },
        })

    successor_migration_targets = collect_successor_migration_files(
        workspace,
        manifest,
        lockfile_state,
        legacy_version_state,
    )
    if successor_migration_targets:
        warnings.append({
            "code": "successor_cleanup_required",
            "message": "Predecessor copilot-instructions-template files must be archived during migration.",
            "details": {"targets": successor_migration_targets},
        })

    return {
        "policy": policy,
        "packageRoot": package_root,
        "artifacts": artifacts,
        "metadata": metadata,
        "metadataArtifacts": metadata_artifacts,
        "manifest": manifest,
        "manifestWithStatus": manifest_with_status,
        "installState": install_state,
        "installPaths": install_paths,
        "git": detect_git_state(workspace),
        "existingSurfaces": detect_existing_surfaces(workspace),
        "legacyVersionState": legacy_version_state,
        "lockfileState": lockfile_state,
        "manifestSummary": manifest_summary,
        "defaultPlanAnswers": default_answers,
        "defaultOwnershipBySurface": ownership_by_surface,
        "successorMigrationTargets": successor_migration_targets,
        "warnings": warnings,
    }


def build_inspect_result(workspace: Path, package_root: Path) -> dict:
    context = collect_context(workspace, package_root)
    return {
        "command": "inspect",
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "ok",
        "warnings": context["warnings"],
        "errors": [],
        "result": {
            "installState": context["installState"],
            "installPaths": context["installPaths"],
            "git": context["git"],
            "contracts": context["artifacts"],
            "discoveryMetadata": context["metadataArtifacts"],
            "existingSurfaces": context["existingSurfaces"],
            "legacyVersionState": context["legacyVersionState"],
            "lockfileState": context["lockfileState"],
            "manifestSummary": context["manifestSummary"],
        },
    }
