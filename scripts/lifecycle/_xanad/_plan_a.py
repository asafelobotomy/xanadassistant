from __future__ import annotations

import json
from pathlib import Path

from scripts.lifecycle._xanad._conditions import entry_required_for_plan, normalize_plan_answers
from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH, LifecycleCommandError
from scripts.lifecycle._xanad._inspect_helpers import collect_unmanaged_files
from scripts.lifecycle._xanad._loader import load_manifest, load_optional_json
from scripts.lifecycle._xanad._merge import sha256_json
from scripts.lifecycle._xanad._plan_utils import expected_entry_hash


def resolve_ownership_by_surface(policy: dict, manifest: dict | None, lockfile_state: dict, resolved_answers: dict) -> dict:
    ownership_defaults = policy.get("ownershipDefaults", {})
    existing_ownership = lockfile_state.get("ownershipBySurface", {})

    ownership_by_surface: dict[str, str] = {}
    if manifest is None:
        return ownership_by_surface

    for entry in manifest.get("managedFiles", []):
        canonical_surface = entry["id"].split(".", 1)[0]
        target_surface = entry["surface"]
        default_ownership = ownership_defaults.get(canonical_surface)
        if default_ownership is None:
            default_ownership = entry["ownership"][0]

        resolved_ownership = existing_ownership.get(target_surface)
        if resolved_ownership is None:
            resolved_ownership = existing_ownership.get(canonical_surface)
        if resolved_ownership is None:
            resolved_ownership = resolved_answers.get(f"ownership.{target_surface}")
        if resolved_ownership is None:
            resolved_ownership = resolved_answers.get(f"ownership.{canonical_surface}")
        if resolved_ownership is None:
            resolved_ownership = default_ownership

        if resolved_ownership not in entry["ownership"]:
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Resolved ownership is not supported for {target_surface}.",
                4,
                {
                    "surface": target_surface,
                    "resolvedOwnership": resolved_ownership,
                    "supportedOwnership": entry["ownership"],
                },
            )

        ownership_by_surface[target_surface] = resolved_ownership

    return ownership_by_surface


def build_setup_plan_actions(
    workspace: Path,
    package_root: Path,
    manifest: dict | None,
    ownership_by_surface: dict,
    resolved_answers: dict,
    token_values: dict[str, str],
    force_reinstall: bool = False,
) -> tuple[dict, list[dict], list[dict], list[str]]:
    from scripts.lifecycle.generate_manifest import sha256_file

    writes = {"add": 0, "replace": 0, "merge": 0, "archiveRetired": 0}
    actions: list[dict] = []
    skipped_actions: list[dict] = []
    retired_targets: list[str] = []

    if manifest is None:
        return writes, actions, skipped_actions, retired_targets

    merge_strategies = {"merge-json-object", "preserve-marked-markdown-blocks"}

    for entry in manifest.get("managedFiles", []):
        ownership_mode = ownership_by_surface.get(entry["surface"], entry["ownership"][0])
        if ownership_mode != "local":
            skipped_actions.append({
                "id": entry["id"], "surface": entry["surface"], "target": entry["target"],
                "reason": "plugin-backed-ownership", "ownershipMode": ownership_mode,
            })
            continue

        if not entry_required_for_plan(entry, resolved_answers):
            skipped_actions.append({
                "id": entry["id"], "surface": entry["surface"], "target": entry["target"],
                "reason": "condition-not-selected",
                "requiredWhen": entry.get("requiredWhen", []),
                "ownershipMode": ownership_mode,
            })
            continue

        target = entry["target"]
        target_path = workspace / target
        if not target_path.exists():
            action = "add"
        elif entry["strategy"] == "copy-if-missing":
            skipped_actions.append({
                "id": entry["id"], "surface": entry["surface"], "target": entry["target"],
                "reason": "copy-if-missing-present", "ownershipMode": ownership_mode,
            })
            continue
        else:
            if force_reinstall:
                action = "merge" if entry["strategy"] in merge_strategies else "replace"
            else:
                installed_hash = sha256_file(target_path)
                expected_hash = expected_entry_hash(package_root, entry, token_values, target_path)
                if expected_hash is not None and installed_hash == expected_hash:
                    continue
                action = "merge" if entry["strategy"] in merge_strategies else "replace"

        writes[action] += 1
        resolved_token_values = {token: token_values[token] for token in entry.get("tokens", []) if token in token_values}
        missing_token_values = [token for token in entry.get("tokens", []) if token not in token_values]
        action_entry = {
            "id": entry["id"], "surface": entry["surface"], "target": target,
            "action": action, "ownershipMode": ownership_mode,
            "strategy": entry["strategy"], "tokens": entry.get("tokens", []),
            "tokenValues": resolved_token_values,
        }
        if missing_token_values:
            action_entry["missingTokenValues"] = missing_token_values
        actions.append(action_entry)

    for retired_entry in manifest.get("retiredFiles", []):
        retired_target = retired_entry.get("target")
        if retired_target and (workspace / retired_target).exists():
            writes["archiveRetired"] += 1
            retired_targets.append(retired_target)
            actions.append({
                "id": retired_entry["id"], "target": retired_target,
                "action": "archive-retired", "ownershipMode": None,
                "strategy": retired_entry.get("action", "archive-retired"),
            })

    return writes, actions, skipped_actions, retired_targets


def classify_plan_conflicts(
    workspace: Path,
    context: dict,
    actions: list[dict],
    retired_targets: list[str],
) -> tuple[list[dict], list[dict]]:
    conflicts: list[dict] = []
    warnings: list[dict] = list(context["warnings"])

    stale_actions = [action for action in actions if action["action"] in {"replace", "merge"}]
    if stale_actions:
        conflict = {"class": "managed-drift", "targets": [action["target"] for action in stale_actions]}
        conflicts.append(conflict)
        warnings.append({
            "code": "managed_drift",
            "message": "Managed targets differ from package state and require updates.",
            "details": conflict,
        })

    unmanaged_files = collect_unmanaged_files(
        workspace, context["manifest"],
        {entry["target"] for entry in context["manifest"].get("managedFiles", [])} if context["manifest"] else set(),
    )
    if unmanaged_files:
        conflict = {"class": "unmanaged-lookalike", "targets": unmanaged_files}
        conflicts.append(conflict)
        warnings.append({
            "code": "unmanaged_lookalike",
            "message": "Unmanaged files exist in managed target directories.",
            "details": conflict,
        })

    if context["legacyVersionState"]["malformed"] or context["lockfileState"]["malformed"]:
        details = {
            "legacyVersionMalformed": context["legacyVersionState"]["malformed"],
            "lockfileMalformed": context["lockfileState"]["malformed"],
        }
        conflicts.append({"class": "malformed-managed-state", "details": details})
        warnings.append({
            "code": "malformed_managed_state",
            "message": "Existing managed state is malformed and may require repair.",
            "details": details,
        })

    if retired_targets:
        conflict = {"class": "retired-file-present", "targets": retired_targets}
        conflicts.append(conflict)
        warnings.append({
            "code": "retired_file_present",
            "message": "Retired managed files are still present in the workspace.",
            "details": conflict,
        })

    return conflicts, warnings


def build_conflict_summary(conflicts: list[dict]) -> dict:
    summary: dict[str, int] = {}
    for conflict in conflicts:
        conflict_class = conflict["class"]
        summary[conflict_class] = summary.get(conflict_class, 0) + 1
    return summary


def write_plan_output(path_value: str | None, payload: dict) -> str | None:
    if path_value is None:
        return None
    output_path = Path(path_value).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(output_path)


def verify_manifest_integrity(package_root: Path, lockfile_state: dict) -> tuple[bool, str | None]:
    """Return (ok, reason) comparing the current package manifest hash with the lockfile."""
    if not lockfile_state.get("present") or lockfile_state.get("malformed"):
        return True, None
    lockfile_data = lockfile_state.get("data")
    if not isinstance(lockfile_data, dict):
        return True, None
    recorded_hash = lockfile_data.get("manifest", {}).get("hash")
    if not recorded_hash:
        return True, None
    policy = load_optional_json(package_root / DEFAULT_POLICY_PATH)
    if policy is None:
        return True, None
    manifest = load_manifest(package_root, policy)
    if manifest is None:
        return False, "Manifest not found at resolved package root."
    current_hash = sha256_json(manifest)
    if current_hash != recorded_hash:
        return False, f"Manifest hash mismatch: installed={recorded_hash!r}, current={current_hash!r}"
    return True, None


