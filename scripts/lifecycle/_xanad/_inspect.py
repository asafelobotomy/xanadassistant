from __future__ import annotations

from pathlib import Path

from scripts.lifecycle._xanad._conditions import resolve_token_values
from scripts.lifecycle._xanad._defaults import derive_effective_plan_defaults
from scripts.lifecycle._xanad._inspect_helpers import (
    annotate_manifest_entries,
    classify_manifest_entries,
    collect_successor_migration_files,
    collect_unmanaged_files,
)
from scripts.lifecycle._xanad._loader import load_contract_artifacts, load_discovery_metadata, load_manifest
from scripts.lifecycle._xanad._merge import sha256_json
from scripts.lifecycle._xanad._source import build_source_summary
from scripts.lifecycle._xanad._state import (
    CURRENT_PACKAGE_NAME,
    detect_existing_surfaces,
    detect_git_state,
    determine_install_state,
    get_lockfile_package_name,
    parse_legacy_version_file,
    parse_lockfile_state,
    summarize_manifest_targets,
)


def collect_context(workspace: Path, package_root: Path) -> dict:
    warnings: list[dict] = []
    policy, artifacts = load_contract_artifacts(package_root)
    metadata, metadata_artifacts = load_discovery_metadata(package_root)
    manifest = load_manifest(package_root, policy)
    install_state, install_paths = determine_install_state(workspace)
    legacy_version_state = parse_legacy_version_file(workspace)
    lockfile_state = parse_lockfile_state(workspace)
    default_answers, ownership_by_surface = derive_effective_plan_defaults(policy, metadata, manifest, lockfile_state)
    # Inject resolved token conflict winners from the lockfile so token resolution
    # uses the same choices that were in effect when the files were installed.
    resolved_conflicts = lockfile_state.get("resolvedTokenConflicts", {})
    if isinstance(resolved_conflicts, dict):
        for token_name, winning_pack in resolved_conflicts.items():
            if isinstance(winning_pack, str):
                default_answers[f"resolvedTokenConflicts.{token_name}"] = winning_pack
    token_values = resolve_token_values(policy, workspace, default_answers, package_root=package_root)
    manifest_with_status = annotate_manifest_entries(
        workspace, package_root, manifest, ownership_by_surface, default_answers, token_values,
        consumer_resolutions=lockfile_state.get("consumerResolutions", {}),
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
                "Run 'repair' or 'update' to adopt xanadAssistant ownership."
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
