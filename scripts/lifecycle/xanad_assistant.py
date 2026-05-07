from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import stat


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.lifecycle.generate_manifest import load_json, sha256_file


DEFAULT_POLICY_PATH = Path("template/setup/install-policy.json")
DEFAULT_POLICY_SCHEMA_PATH = Path("template/setup/install-policy.schema.json")
DEFAULT_MANIFEST_SCHEMA_PATH = Path("template/setup/install-manifest.schema.json")
DEFAULT_LOCK_SCHEMA_PATH = Path("template/setup/xanad-assistant-lock.schema.json")
DEFAULT_PACK_REGISTRY_PATH = Path("template/setup/pack-registry.json")
DEFAULT_PROFILE_REGISTRY_PATH = Path("template/setup/profile-registry.json")
DEFAULT_CATALOG_PATH = Path("template/setup/catalog.json")


class LifecycleCommandError(Exception):
    def __init__(self, code: str, message: str, exit_code: int, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details or {}


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", required=True, help="Consumer repository to inspect or modify.")
    parser.add_argument("--package-root", required=True, help="Local xanad-assistant package checkout.")
    parser.add_argument("--source", help="Package source identifier.")
    parser.add_argument("--version", help="Requested release version.")
    parser.add_argument("--ref", help="Requested source ref.")
    parser.add_argument("--json", action="store_true", help="Emit a single JSON result.")
    parser.add_argument("--json-lines", action="store_true", help="Emit JSON Lines protocol events.")
    parser.add_argument("--non-interactive", action="store_true", help="Disable interactive prompting.")
    parser.add_argument("--dry-run", action="store_true", help="Avoid managed writes.")
    parser.add_argument("--answers", help="Path to answer file.")
    parser.add_argument("--plan-out", help="Path to write a serialized plan.")
    parser.add_argument("--report-out", help="Path to write a structured report.")
    parser.add_argument("--log-file", help="Path to write a plain-text operational log.")
    parser.add_argument("--ui", choices=["quiet", "agent", "tui"], default="quiet", help="Presentation mode.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Xanad Assistant lifecycle tool.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect workspace state.")
    add_common_arguments(inspect_parser)

    check_parser = subparsers.add_parser("check", help="Check managed workspace state.")
    add_common_arguments(check_parser)

    interview_parser = subparsers.add_parser("interview", help="Emit structured lifecycle questions.")
    add_common_arguments(interview_parser)
    interview_parser.add_argument(
        "--mode",
        choices=["setup", "update", "repair", "factory-restore"],
        default="setup",
        help="Lifecycle mode requiring questions.",
    )

    plan_parser = subparsers.add_parser("plan", help="Generate a lifecycle plan.")
    plan_subparsers = plan_parser.add_subparsers(dest="mode", required=True)
    for mode in ("setup", "update", "repair", "factory-restore"):
        mode_parser = plan_subparsers.add_parser(mode, help=f"Generate a {mode} plan.")
        add_common_arguments(mode_parser)

    for command in ("apply", "update", "repair", "factory-restore"):
        command_parser = subparsers.add_parser(command, help=f"{command} workspace state.")
        add_common_arguments(command_parser)

    return parser


def resolve_workspace(path_value: str) -> Path:
    workspace = Path(path_value).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def resolve_package_root(path_value: str) -> Path:
    package_root = Path(path_value).resolve()
    if not package_root.exists():
        raise FileNotFoundError(f"Package root does not exist: {package_root}")
    return package_root


def build_source_summary(package_root: Path) -> dict:
    return {
        "kind": "package-root",
        "packageRoot": str(package_root),
    }


def load_optional_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return load_json(path)


def load_contract_artifacts(package_root: Path) -> tuple[dict, dict]:
    policy_path = package_root / DEFAULT_POLICY_PATH
    policy_schema_path = package_root / DEFAULT_POLICY_SCHEMA_PATH
    manifest_schema_path = package_root / DEFAULT_MANIFEST_SCHEMA_PATH
    lock_schema_path = package_root / DEFAULT_LOCK_SCHEMA_PATH

    policy = load_json(policy_path)
    manifest_path = package_root / policy.get("generationSettings", {}).get("manifestOutput", "template/setup/install-manifest.json")

    artifacts = {
        "policy": {
            "path": str(policy_path),
            "loaded": policy_path.exists(),
        },
        "policySchema": {
            "path": str(policy_schema_path),
            "loaded": policy_schema_path.exists(),
        },
        "manifestSchema": {
            "path": str(manifest_schema_path),
            "loaded": manifest_schema_path.exists(),
        },
        "lockSchema": {
            "path": str(lock_schema_path),
            "loaded": lock_schema_path.exists(),
        },
        "manifest": {
            "path": str(manifest_path),
            "loaded": manifest_path.exists(),
        },
    }
    return policy, artifacts


def load_discovery_metadata(package_root: Path) -> tuple[dict, dict]:
    pack_registry_path = package_root / DEFAULT_PACK_REGISTRY_PATH
    profile_registry_path = package_root / DEFAULT_PROFILE_REGISTRY_PATH
    catalog_path = package_root / DEFAULT_CATALOG_PATH

    metadata = {
        "packRegistry": load_optional_json(pack_registry_path),
        "profileRegistry": load_optional_json(profile_registry_path),
        "catalog": load_optional_json(catalog_path),
    }
    artifacts = {
        "packRegistry": {
            "path": str(pack_registry_path),
            "loaded": pack_registry_path.exists(),
        },
        "profileRegistry": {
            "path": str(profile_registry_path),
            "loaded": profile_registry_path.exists(),
        },
        "catalog": {
            "path": str(catalog_path),
            "loaded": catalog_path.exists(),
        },
    }
    return metadata, artifacts


def load_manifest(package_root: Path, policy: dict) -> dict | None:
    manifest_path = package_root / policy.get("generationSettings", {}).get("manifestOutput", "template/setup/install-manifest.json")
    if not manifest_path.exists():
        return None
    return load_json(manifest_path)


def detect_git_state(workspace: Path) -> dict:
    git_dir = workspace / ".git"
    if not git_dir.exists():
        return {
            "present": False,
            "dirty": None,
        }

    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return {
            "present": True,
            "dirty": None,
        }

    if result.returncode != 0:
        return {
            "present": True,
            "dirty": None,
        }

    return {
        "present": True,
        "dirty": bool(result.stdout.strip()),
    }


def determine_install_state(workspace: Path) -> tuple[str, dict]:
    lockfile = workspace / ".github" / "xanad-assistant-lock.json"
    legacy_version = workspace / ".github" / "copilot-version.md"

    if lockfile.exists():
        return "installed", {"lockfile": str(lockfile), "legacyVersionFile": legacy_version.exists()}
    if legacy_version.exists():
        return "legacy-version-only", {"lockfile": None, "legacyVersionFile": True}
    return "not-installed", {"lockfile": None, "legacyVersionFile": False}


def parse_legacy_version_file(workspace: Path) -> dict:
    legacy_path = workspace / ".github" / "copilot-version.md"
    if not legacy_path.exists():
        return {
            "present": False,
            "malformed": False,
            "path": str(legacy_path),
            "data": None,
        }

    text = legacy_path.read_text(encoding="utf-8")
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return {
                "present": True,
                "malformed": False,
                "path": str(legacy_path),
                "data": json.loads(json_match.group(1)),
            }
        except json.JSONDecodeError:
            return {
                "present": True,
                "malformed": True,
                "path": str(legacy_path),
                "data": None,
            }

    version_match = re.search(r"(?im)^version\s*:\s*(?P<version>.+?)\s*$", text)
    if version_match:
        return {
            "present": True,
            "malformed": False,
            "path": str(legacy_path),
            "data": {"version": version_match.group("version")},
        }

    return {
        "present": True,
        "malformed": True,
        "path": str(legacy_path),
        "data": None,
    }


def parse_lockfile_state(workspace: Path) -> dict:
    lockfile_path = workspace / ".github" / "xanad-assistant-lock.json"
    if not lockfile_path.exists():
        return {
            "present": False,
            "malformed": False,
            "path": str(lockfile_path),
            "data": None,
            "selectedPacks": [],
            "profile": None,
            "ownershipBySurface": {},
            "skippedManagedFiles": [],
            "unknownValues": {},
            "files": [],
        }

    try:
        data = load_json(lockfile_path)
    except json.JSONDecodeError:
        return {
            "present": True,
            "malformed": True,
            "path": str(lockfile_path),
            "data": None,
            "selectedPacks": [],
            "profile": None,
            "ownershipBySurface": {},
            "skippedManagedFiles": [],
            "unknownValues": {},
            "files": [],
        }

    return {
        "present": True,
        "malformed": False,
        "path": str(lockfile_path),
        "data": data,
        "selectedPacks": data.get("selectedPacks", []),
        "profile": data.get("profile"),
        "ownershipBySurface": data.get("ownershipBySurface", {}),
        "skippedManagedFiles": data.get("skippedManagedFiles", []),
        "unknownValues": data.get("unknownValues", {}),
        "files": data.get("files", []),
    }


def read_lockfile_status(workspace: Path) -> dict:
    lockfile_state = parse_lockfile_state(workspace)
    return {
        "present": lockfile_state["present"],
        "malformed": lockfile_state["malformed"],
    }


def count_files(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return sum(1 for file_path in path.rglob("*") if file_path.is_file())


def detect_existing_surfaces(workspace: Path) -> dict:
    return {
        "instructions": {
            "present": (workspace / ".github" / "copilot-instructions.md").exists(),
        },
        "prompts": {
            "count": count_files(workspace / ".github" / "prompts"),
        },
        "agents": {
            "count": count_files(workspace / ".github" / "agents"),
        },
        "skills": {
            "count": count_files(workspace / ".github" / "skills"),
        },
        "hooks": {
            "count": count_files(workspace / ".github" / "hooks"),
        },
        "mcp": {
            "present": (workspace / ".vscode" / "mcp.json").exists(),
        },
        "workspace": {
            "count": count_files(workspace / ".copilot" / "workspace"),
        },
    }


def summarize_manifest_targets(workspace: Path, manifest: dict | None) -> dict:
    if manifest is None:
        return {
            "declared": 0,
            "present": 0,
            "missing": 0,
            "skipped": 0,
            "retired": 0,
        }

    declared = len(manifest.get("managedFiles", []))
    present = 0
    missing = 0
    skipped = 0
    for entry in manifest.get("managedFiles", []):
        if entry.get("status") == "skipped":
            skipped += 1
            continue
        if (workspace / entry["target"]).exists():
            present += 1
        else:
            missing += 1

    return {
        "declared": declared,
        "present": present,
        "missing": missing,
        "skipped": skipped,
        "retired": len(manifest.get("retiredFiles", [])),
    }


def parse_condition_literal(value: str) -> object:
    normalized = value.strip()
    lower = normalized.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    return normalized


def condition_matches(condition: str, resolved_answers: dict) -> bool:
    if "=" in condition:
        condition_id, expected_value = condition.split("=", 1)
        return resolved_answers.get(condition_id) == parse_condition_literal(expected_value)
    return bool(resolved_answers.get(condition))


def entry_required_for_plan(entry: dict, resolved_answers: dict) -> bool:
    required_when = entry.get("requiredWhen", [])
    if isinstance(required_when, str):
        required_when = [required_when]
    return all(condition_matches(condition, resolved_answers) for condition in required_when)


def normalize_plan_answers(policy: dict, resolved_answers: dict) -> dict:
    normalized_answers = dict(resolved_answers)
    if "hook-scripts" in policy.get("canonicalSurfaces", []) and normalized_answers.get("mcp.enabled"):
        normalized_answers["hooks.enabled"] = True
    return normalized_answers


def resolve_token_values(policy: dict, workspace: Path, resolved_answers: dict) -> dict[str, str]:
    token_values: dict[str, str] = {}

    for token_rule in policy.get("tokenRules", []):
        token = token_rule["token"]
        if token == "{{WORKSPACE_NAME}}":
            token_values[token] = workspace.name
        elif token == "{{XANAD_PROFILE}}":
            profile = resolved_answers.get("profile.selected")
            if isinstance(profile, str) and profile:
                token_values[token] = profile

    return token_values


def render_tokenized_text(template_text: str, token_values: dict[str, str]) -> str:
    rendered_text = template_text
    for token, value in token_values.items():
        rendered_text = rendered_text.replace(token, value)
    return rendered_text


def sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def merge_json_objects(existing_data: dict, source_data: dict) -> dict:
    merged = dict(existing_data)
    for key, source_value in source_data.items():
        existing_value = merged.get(key)
        if isinstance(existing_value, dict) and isinstance(source_value, dict):
            merged[key] = merge_json_objects(existing_value, source_value)
        else:
            merged[key] = source_value
    return merged


def serialize_json_object(data: dict) -> bytes:
    return (json.dumps(data, indent=2) + "\n").encode("utf-8")


def extract_markdown_heading_block(markdown_text: str, heading: str) -> str | None:
    lines = markdown_text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != heading:
            continue
        end_index = len(lines)
        for candidate in range(index + 1, len(lines)):
            if lines[candidate].startswith("## "):
                end_index = candidate
                break
        block = "\n".join(lines[index:end_index]).strip()
        return block if block else None
    return None


def extract_marked_markdown_blocks(markdown_text: str, marker_name: str) -> list[str]:
    pattern = re.compile(
        rf"<!--\s*{re.escape(marker_name)}\s*-->(.*?)<!--\s*/{re.escape(marker_name)}\s*-->",
        re.DOTALL,
    )
    return [match.group(0).strip() for match in pattern.finditer(markdown_text)]


def merge_markdown_with_preserved_blocks(existing_text: str, source_text: str) -> str:
    merged_text = source_text.rstrip("\n")
    preserved_blocks: list[str] = []

    overrides_block = extract_markdown_heading_block(existing_text, "## §10 - Project-Specific Overrides")
    if overrides_block is not None:
        preserved_blocks.append(overrides_block)

    for marker_name in ("user-added", "migrated"):
        for block in extract_marked_markdown_blocks(existing_text, marker_name):
            if block not in preserved_blocks:
                preserved_blocks.append(block)

    if not preserved_blocks:
        return source_text

    for block in preserved_blocks:
        if block and block not in merged_text:
            merged_text = f"{merged_text}\n\n{block}"

    return merged_text + "\n"


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
        elif action["action"] == "archive-retired" and archive_root is not None:
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


def derive_effective_plan_defaults(policy: dict, metadata: dict, manifest: dict | None, lockfile_state: dict) -> tuple[dict, dict]:
    questions = build_interview_questions(policy, metadata, "setup")
    seeded_answers = seed_answers_from_install_state("update", questions, lockfile_state, {})
    resolved_answers, _ = resolve_question_answers(questions, seeded_answers)
    resolved_answers = normalize_plan_answers(policy, resolved_answers)
    ownership_by_surface = resolve_ownership_by_surface(policy, manifest, lockfile_state, resolved_answers)
    return resolved_answers, ownership_by_surface


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
        workspace,
        package_root,
        manifest,
        ownership_by_surface,
        default_answers,
        token_values,
    )
    manifest_summary = summarize_manifest_targets(workspace, manifest_with_status)

    if not artifacts["manifest"]["loaded"]:
        warnings.append(
            {
                "code": "manifest_missing",
                "message": "Generated manifest not found at package root.",
                "details": {"path": artifacts["manifest"]["path"]},
            }
        )

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
        "clean": 0,
        "missing": 0,
        "stale": 0,
        "malformed": 0,
        "skipped": 0,
        "retired": 0,
        "unmanaged": 0,
        "unknown": 0,
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
            target_path = workspace / target
            if not target_path.exists():
                status = "missing"
            else:
                installed_hash = sha256_file(target_path)
                status = "clean" if installed_hash == entry["hash"] else "stale"

        counts[status] += 1
        entries.append(
            {
                "id": entry["id"],
                "target": target,
                "status": status,
            }
        )

    for retired in manifest.get("retiredFiles", []):
        retired_target = retired.get("target")
        if retired_target and (workspace / retired_target).exists():
            counts["retired"] += 1
            entries.append(
                {
                    "id": retired["id"],
                    "target": retired_target,
                    "status": "retired",
                }
            )

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


def build_check_result(workspace: Path, package_root: Path) -> dict:
    context = collect_context(workspace, package_root)
    counts, entries, managed_targets = classify_manifest_entries(workspace, context["manifestWithStatus"])
    unmanaged_files = collect_unmanaged_files(workspace, context["manifestWithStatus"], managed_targets)
    counts["unmanaged"] = len(unmanaged_files)

    lockfile_status = read_lockfile_status(workspace)
    if lockfile_status["malformed"]:
        counts["malformed"] += 1
    if context["legacyVersionState"]["malformed"]:
        counts["malformed"] += 1

    skipped_files = context["lockfileState"].get("skippedManagedFiles", [])
    counts["skipped"] += len(skipped_files)
    recorded_targets = {entry["target"] for entry in entries}
    for skipped_target in skipped_files:
        if skipped_target in recorded_targets:
            continue
        entries.append(
            {
                "id": skipped_target,
                "target": skipped_target,
                "status": "skipped",
            }
        )

    unknown_values = context["lockfileState"].get("unknownValues", {})
    unknown_count = len(unknown_values)
    for file_record in context["lockfileState"].get("files", []):
        if file_record.get("status") == "unknown" or file_record.get("installedHash") == "unknown":
            unknown_count += 1
            entries.append(
                {
                    "id": file_record.get("id", file_record.get("target", "unknown")),
                    "target": file_record.get("target", "unknown"),
                    "status": "unknown",
                }
            )
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


def build_interview_questions(policy: dict, metadata: dict, mode: str) -> list[dict]:
    questions = []
    ownership_defaults = policy.get("ownershipDefaults", {})

    profile_registry = metadata.get("profileRegistry") or {}
    pack_registry = metadata.get("packRegistry") or {}

    profile_options = [profile["id"] for profile in profile_registry.get("profiles", [])]
    if profile_options:
        questions.append(
            {
                "id": "profile.selected",
                "kind": "choice",
                "prompt": f"Which behavior profile should {mode} use?",
                "required": True,
                "options": profile_options,
                "recommended": "balanced" if "balanced" in profile_options else profile_options[0],
                "default": "balanced" if "balanced" in profile_options else profile_options[0],
                "requiredFor": ["profile"],
            }
        )

    optional_packs = [pack["id"] for pack in pack_registry.get("packs", []) if pack.get("optional", False)]
    if optional_packs:
        questions.append(
            {
                "id": "packs.selected",
                "kind": "multi-choice",
                "prompt": f"Which optional packs should {mode} consider?",
                "required": False,
                "options": optional_packs,
                "recommended": [],
                "default": [],
                "requiredFor": ["packs"],
            }
        )

    for surface in ("agents", "skills"):
        if surface not in ownership_defaults:
            continue
        questions.append(
            {
                "id": f"ownership.{surface}",
                "kind": "choice",
                "prompt": f"How should {surface} be owned for this workspace?",
                "required": True,
                "options": ["local", "plugin-backed-copilot-format"],
                "recommended": ownership_defaults[surface],
                "default": ownership_defaults[surface],
                "requiredFor": [surface],
            }
        )

    if "hook-scripts" in policy.get("canonicalSurfaces", []):
        questions.append(
            {
                "id": "hooks.enabled",
                "kind": "confirm",
                "prompt": "Enable workspace-local hook scripts for this workspace?",
                "required": True,
                "default": False,
                "recommended": False,
                "reason": "Hooks stay opt-in so the default install stays lean until a workspace needs local executable paths.",
                "requiredFor": ["hook-scripts"],
            }
        )

    if "mcp-config" in policy.get("canonicalSurfaces", []):
        questions.append(
            {
                "id": "mcp.enabled",
                "kind": "confirm",
                "prompt": "Enable MCP configuration for this workspace?",
                "required": True,
                "default": False,
                "recommended": False,
                "reason": "MCP stays opt-in until the workspace chooses a local server configuration.",
                "requiredFor": ["mcp-config"],
            }
        )

    return questions


def build_interview_result(workspace: Path, package_root: Path, mode: str) -> dict:
    context = collect_context(workspace, package_root)
    questions = build_interview_questions(context["policy"], context["metadata"], mode)

    return {
        "command": "interview",
        "mode": mode,
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "ok",
        "warnings": context["warnings"],
        "errors": [],
        "result": {
            "installState": context["installState"],
            "discoveryMetadata": context["metadataArtifacts"],
            "questionCount": len(questions),
            "questions": questions,
        },
    }


def build_error_payload(
    command: str,
    workspace: Path,
    package_root: Path,
    code: str,
    message: str,
    exit_code: int,
    mode: str | None = None,
    details: dict | None = None,
) -> tuple[dict, int]:
    return (
        {
            "command": command,
            "mode": mode,
            "workspace": str(workspace),
            "source": build_source_summary(package_root),
            "status": "error",
            "warnings": [],
            "errors": [
                {
                    "code": code,
                    "message": message,
                    "details": details or {},
                }
            ],
            "result": {},
        },
        exit_code,
    )


def load_answers(path_value: str | None) -> dict:
    if path_value is None:
        return {}

    answers_path = Path(path_value).resolve()
    if not answers_path.exists():
        raise LifecycleCommandError(
            "contract_input_failure",
            "Answer file was not found.",
            4,
            {"path": str(answers_path)},
        )

    try:
        data = load_json(answers_path)
    except json.JSONDecodeError as error:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Answer file is not valid JSON.",
            4,
            {"path": str(answers_path), "line": error.lineno, "column": error.colno},
        ) from error

    if not isinstance(data, dict):
        raise LifecycleCommandError(
            "contract_input_failure",
            "Answer file must contain a JSON object.",
            4,
            {"path": str(answers_path)},
        )
    return data


def validate_answer_value(question: dict, value: object) -> None:
    kind = question.get("kind")
    options = question.get("options", [])

    if kind == "choice":
        if not isinstance(value, str) or value not in options:
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Invalid answer for {question['id']}.",
                4,
                {"questionId": question["id"], "expected": options, "received": value},
            )
        return

    if kind == "multi-choice":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Invalid answer for {question['id']}.",
                4,
                {"questionId": question["id"], "expected": options, "received": value},
            )
        if any(item not in options for item in value):
            raise LifecycleCommandError(
                "contract_input_failure",
                f"Invalid answer for {question['id']}.",
                4,
                {"questionId": question["id"], "expected": options, "received": value},
            )
        return

    if kind == "confirm" and not isinstance(value, bool):
        raise LifecycleCommandError(
            "contract_input_failure",
            f"Invalid answer for {question['id']}.",
            4,
            {"questionId": question["id"], "expected": "boolean", "received": value},
        )


def resolve_question_answers(questions: list[dict], answers: dict) -> tuple[dict, list[str]]:
    resolved_answers: dict = {}
    unresolved: list[str] = []
    question_map = {question["id"]: question for question in questions}

    unknown_ids = sorted(answer_id for answer_id in answers if answer_id not in question_map)
    if unknown_ids:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Answer file contains unknown question ids.",
            4,
            {"questionIds": unknown_ids},
        )

    for question in questions:
        question_id = question["id"]
        if question_id in answers:
            validate_answer_value(question, answers[question_id])
            resolved_answers[question_id] = answers[question_id]
            continue
        if "default" in question:
            resolved_answers[question_id] = question["default"]
            continue
        if question.get("recommended") is not None:
            resolved_answers[question_id] = question["recommended"]
            continue
        if question.get("required"):
            unresolved.append(question_id)

    return resolved_answers, unresolved


def resolve_ownership_by_surface(policy: dict, manifest: dict | None, lockfile_state: dict, resolved_answers: dict) -> dict:
    canonical_surfaces = policy.get("canonicalSurfaces", [])
    target_path_rules = policy.get("targetPathRules", {})
    ownership_defaults = policy.get("ownershipDefaults", {})
    existing_ownership = lockfile_state.get("ownershipBySurface", {})

    ownership_by_surface: dict[str, str] = {}
    if manifest is None:
        return ownership_by_surface

    for entry in manifest.get("managedFiles", []):
        canonical_surface = entry["id"].split(".", 1)[0]
        target_surface = entry["surface"]
        default_ownership = ownership_defaults.get(canonical_surface)
        if canonical_surface in canonical_surfaces:
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
    writes = {
        "add": 0,
        "replace": 0,
        "merge": 0,
        "archiveRetired": 0,
    }
    actions: list[dict] = []
    skipped_actions: list[dict] = []
    retired_targets: list[str] = []

    if manifest is None:
        return writes, actions, skipped_actions, retired_targets

    merge_strategies = {"merge-json-object", "preserve-marked-markdown-blocks"}

    for entry in manifest.get("managedFiles", []):
        ownership_mode = ownership_by_surface.get(entry["surface"], entry["ownership"][0])
        if ownership_mode != "local":
            skipped_actions.append(
                {
                    "id": entry["id"],
                    "surface": entry["surface"],
                    "target": entry["target"],
                    "reason": "plugin-backed-ownership",
                    "ownershipMode": ownership_mode,
                }
            )
            continue

        if not entry_required_for_plan(entry, resolved_answers):
            skipped_actions.append(
                {
                    "id": entry["id"],
                    "surface": entry["surface"],
                    "target": entry["target"],
                    "reason": "condition-not-selected",
                    "requiredWhen": entry.get("requiredWhen", []),
                    "ownershipMode": ownership_mode,
                }
            )
            continue

        target = entry["target"]
        target_path = workspace / target
        if not target_path.exists():
            action = "add"
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
        actions.append(
            {
                "id": entry["id"],
                "surface": entry["surface"],
                "target": target,
                "action": action,
                "ownershipMode": ownership_mode,
                "strategy": entry["strategy"],
                "tokens": entry.get("tokens", []),
                "tokenValues": {token: token_values[token] for token in entry.get("tokens", []) if token in token_values},
            }
        )

    for retired_entry in manifest.get("retiredFiles", []):
        retired_target = retired_entry.get("target")
        if retired_target and (workspace / retired_target).exists():
            writes["archiveRetired"] += 1
            retired_targets.append(retired_target)
            actions.append(
                {
                    "id": retired_entry["id"],
                    "target": retired_target,
                    "action": "archive-retired",
                    "ownershipMode": None,
                    "strategy": retired_entry.get("action", "archive-retired"),
                }
            )

    return writes, actions, skipped_actions, retired_targets


def classify_plan_conflicts(context: dict, actions: list[dict], retired_targets: list[str]) -> tuple[list[dict], list[dict]]:
    conflicts: list[dict] = []
    warnings: list[dict] = list(context["warnings"])

    stale_actions = [action for action in actions if action["action"] in {"replace", "merge"}]
    if stale_actions:
        conflict = {
            "class": "managed-drift",
            "targets": [action["target"] for action in stale_actions],
        }
        conflicts.append(conflict)
        warnings.append(
            {
                "code": "managed_drift",
                "message": "Managed targets differ from package state and require updates.",
                "details": conflict,
            }
        )

    unmanaged_files = collect_unmanaged_files(context["workspacePath"], context["manifest"], {entry["target"] for entry in context["manifest"].get("managedFiles", [])} if context["manifest"] else set())
    if unmanaged_files:
        conflict = {
            "class": "unmanaged-lookalike",
            "targets": unmanaged_files,
        }
        conflicts.append(conflict)
        warnings.append(
            {
                "code": "unmanaged_lookalike",
                "message": "Unmanaged files exist in managed target directories.",
                "details": conflict,
            }
        )

    if context["legacyVersionState"]["malformed"] or context["lockfileState"]["malformed"]:
        details = {
            "legacyVersionMalformed": context["legacyVersionState"]["malformed"],
            "lockfileMalformed": context["lockfileState"]["malformed"],
        }
        conflicts.append({"class": "malformed-managed-state", "details": details})
        warnings.append(
            {
                "code": "malformed_managed_state",
                "message": "Existing managed state is malformed and may require repair.",
                "details": details,
            }
        )

    if retired_targets:
        conflict = {
            "class": "retired-file-present",
            "targets": retired_targets,
        }
        conflicts.append(conflict)
        warnings.append(
            {
                "code": "retired_file_present",
                "message": "Retired managed files are still present in the workspace.",
                "details": conflict,
            }
        )

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


def write_report_output(path_value: str | None, payload: dict) -> str | None:
    if path_value is None:
        return None

    output_path = Path(path_value).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(output_path)


def sha256_json(data: object) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def seed_answers_from_install_state(mode: str, questions: list[dict], lockfile_state: dict, answers: dict) -> dict:
    if mode not in {"update", "repair", "factory-restore"}:
        return dict(answers)

    seeded_answers = dict(answers)
    question_map = {question["id"]: question for question in questions}

    profile_question = question_map.get("profile.selected")
    installed_profile = lockfile_state.get("profile")
    if profile_question and "profile.selected" not in seeded_answers and installed_profile in profile_question.get("options", []):
        seeded_answers["profile.selected"] = installed_profile

    packs_question = question_map.get("packs.selected")
    installed_packs = lockfile_state.get("selectedPacks", [])
    if packs_question and "packs.selected" not in seeded_answers and isinstance(installed_packs, list):
        valid_packs = [pack_id for pack_id in installed_packs if pack_id in packs_question.get("options", [])]
        seeded_answers["packs.selected"] = valid_packs

    return seeded_answers


def determine_repair_reasons(context: dict) -> list[str]:
    reasons: list[str] = []
    if context["installState"] == "legacy-version-only":
        reasons.append("legacy-version-only")
    if context["legacyVersionState"]["malformed"]:
        reasons.append("malformed-legacy-version")
    if context["lockfileState"]["malformed"]:
        reasons.append("malformed-lockfile")
    return reasons


def build_planned_lockfile(
    context: dict,
    ownership_by_surface: dict,
    resolved_answers: dict,
    token_values: dict[str, str],
    actions: list[dict],
    skipped_actions: list[dict],
    retired_targets: list[str],
    backup_plan: dict,
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

        file_records.append(
            {
                "id": action["id"],
                "target": action["target"],
                "sourceHash": manifest_entry["hash"],
                "installedHash": expected_entry_hash(
                    context["packageRoot"],
                    manifest_entry,
                    token_values,
                    context["workspacePath"] / action["target"],
                ) or "unknown",
                "ownershipMode": action["ownershipMode"],
                "status": "applied",
            }
        )

    archive_targets = {entry["target"]: entry["archivePath"] for entry in backup_plan.get("archiveTargets", [])}
    retired_records = []
    for retired_entry in manifest.get("retiredFiles", []):
        target = retired_entry.get("target")
        if target not in retired_targets:
            continue
        retired_record = {
            "id": retired_entry["id"],
            "action": "archived" if target in archive_targets else "reported",
        }
        if target is not None:
            retired_record["target"] = target
        if target in archive_targets:
            retired_record["archivePath"] = archive_targets[target]
        retired_records.append(retired_record)

    lockfile_contents = {
        "schemaVersion": "0.1.0",
        "package": {
            "name": "xanad-assistant",
        },
        "manifest": {
            "schemaVersion": manifest.get("schemaVersion", "0.1.0"),
            "hash": sha256_json(manifest),
        },
        "timestamps": {
            "appliedAt": "<apply-timestamp>",
            "updatedAt": "<apply-timestamp>",
        },
        "selectedPacks": resolved_answers.get("packs.selected", []),
        "profile": resolved_answers.get("profile.selected"),
        "ownershipBySurface": ownership_by_surface,
        "setupAnswers": resolved_answers,
        "installMetadata": {
            "mcpAvailable": True,
            "mcpEnabled": bool(resolved_answers.get("mcp.enabled", False)),
        },
        "files": sorted(file_records, key=lambda record: record["target"]),
        "skippedManagedFiles": sorted(entry["target"] for entry in skipped_actions),
        "retiredManagedFiles": retired_records,
        "unknownValues": {},
    }
    if backup_plan.get("required") and backup_plan.get("root"):
        lockfile_contents["lastBackup"] = {"path": backup_plan["root"]}

    return {
        "path": ".github/xanad-assistant-lock.json",
        "contents": lockfile_contents,
    }


def build_plan_result(workspace: Path, package_root: Path, mode: str, answers_path: str | None, non_interactive: bool) -> dict:
    if mode not in {"setup", "update", "repair", "factory-restore"}:
        return build_not_implemented_payload("plan", workspace, package_root, mode)

    context = collect_context(workspace, package_root)
    if mode == "update" and context["installState"] == "not-installed":
        raise LifecycleCommandError(
            "inspection_failure",
            "Update planning requires an existing install state.",
            5,
            {"installState": context["installState"]},
        )
    if mode == "repair":
        repair_reasons = determine_repair_reasons(context)
        if context["installState"] == "not-installed":
            raise LifecycleCommandError(
                "inspection_failure",
                "Repair planning requires an existing install state.",
                5,
                {"installState": context["installState"]},
            )
        if not repair_reasons:
            raise LifecycleCommandError(
                "inspection_failure",
                "Repair planning requires legacy or malformed managed state.",
                5,
                {"installState": context["installState"]},
            )
    else:
        repair_reasons = []
    if mode == "factory-restore" and context["installState"] == "not-installed":
        raise LifecycleCommandError(
            "inspection_failure",
            "Factory-restore planning requires an existing install state.",
            5,
            {"installState": context["installState"]},
        )

    questions = build_interview_questions(context["policy"], context["metadata"], mode)
    answers = seed_answers_from_install_state(mode, questions, context["lockfileState"], load_answers(answers_path))
    resolved_answers, unresolved = resolve_question_answers(questions, answers)
    resolved_answers = normalize_plan_answers(context["policy"], resolved_answers)
    if non_interactive and unresolved:
        raise LifecycleCommandError(
            "approval_or_answers_required",
            "Required answers are missing for non-interactive planning.",
            6,
            {"questionIds": unresolved},
        )

    ownership_by_surface = resolve_ownership_by_surface(
        context["policy"],
        context["manifest"],
        context["lockfileState"],
        resolved_answers,
    )
    token_values = resolve_token_values(context["policy"], workspace, resolved_answers)
    context["workspacePath"] = workspace
    writes, actions, skipped_actions, retired_targets = build_setup_plan_actions(
        workspace,
        package_root,
        context["manifest"],
        ownership_by_surface,
        resolved_answers,
        token_values,
        force_reinstall=mode == "factory-restore",
    )
    conflicts, warnings = classify_plan_conflicts(context, actions, retired_targets)
    token_plan = build_token_plan_summary(context["policy"], actions, token_values)

    backup_required = any(count > 0 for count in writes.values())
    backup_plan = build_backup_plan(context["policy"], actions, backup_required)
    planned_lockfile = build_planned_lockfile(
        context,
        ownership_by_surface,
        resolved_answers,
        token_values,
        actions,
        skipped_actions,
        retired_targets,
        backup_plan,
    )
    approval_required = backup_required

    return {
        "command": "plan",
        "mode": mode,
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "approval-required" if approval_required else "ok",
        "warnings": warnings,
        "errors": [],
        "result": {
            "installState": context["installState"],
            "installPaths": context["installPaths"],
            "contracts": context["artifacts"],
            "discoveryMetadata": context["metadataArtifacts"],
            "approvalRequired": approval_required,
            "backupRequired": backup_required,
            "backupPlan": backup_plan,
            "plannedLockfile": planned_lockfile,
            "writes": writes,
            "conflicts": conflicts,
            "conflictSummary": build_conflict_summary(conflicts),
            "actions": actions,
            "skippedActions": skipped_actions,
            "tokenSubstitutions": token_plan,
            "ownershipBySurface": ownership_by_surface,
            "packs": resolved_answers.get("packs.selected", []),
            "profile": resolved_answers.get("profile.selected"),
            "factoryRestore": mode == "factory-restore",
            "repairReasons": repair_reasons,
            "retired": retired_targets,
            "questionsResolved": not unresolved,
            "resolvedAnswers": resolved_answers,
            "questions": questions,
        },
    }


def generate_apply_timestamps() -> tuple[str, str]:
    current = datetime.now(timezone.utc).replace(microsecond=0)
    return current.isoformat().replace("+00:00", "Z"), current.strftime("%Y-%m-%dT%H-%M-%SZ")


def materialize_apply_timestamp(value: str | None, path_timestamp: str) -> str | None:
    if value is None:
        return None
    return value.replace("<apply-timestamp>", path_timestamp)


def render_entry_bytes(package_root: Path, manifest_entry: dict, token_values: dict[str, str]) -> bytes:
    expected_bytes = expected_entry_bytes(package_root, manifest_entry, token_values)
    if expected_bytes is None:
        raise LifecycleCommandError(
            "apply_failure",
            "Unable to render managed file bytes for apply.",
            9,
            {"id": manifest_entry["id"], "strategy": manifest_entry.get("strategy")},
        )
    return expected_bytes


def merge_json_object_file(target_path: Path, package_root: Path, manifest_entry: dict) -> None:
    source_path = package_root / manifest_entry["source"]
    if target_path.exists():
        try:
            existing_data = load_json(target_path)
            source_data = load_json(source_path)
        except json.JSONDecodeError as error:
            raise LifecycleCommandError(
                "apply_failure",
                "Existing JSON target could not be merged.",
                9,
                {"target": str(target_path), "error": str(error)},
            ) from error
        if not isinstance(existing_data, dict) or not isinstance(source_data, dict):
            raise LifecycleCommandError(
                "apply_failure",
                "JSON merge targets must both be objects.",
                9,
                {"target": str(target_path), "source": str(source_path)},
            )
        merged_data = merge_json_objects(existing_data, source_data)
    else:
        source_data = load_json(source_path)
        if not isinstance(source_data, dict):
            raise LifecycleCommandError(
                "apply_failure",
                "JSON merge source must be an object.",
                9,
                {"source": str(source_path)},
            )
        merged_data = source_data

    target_path.write_bytes(serialize_json_object(merged_data))


def merge_markdown_file(target_path: Path, package_root: Path, manifest_entry: dict) -> None:
    source_path = package_root / manifest_entry["source"]
    source_text = source_path.read_text(encoding="utf-8")
    if target_path.exists():
        existing_text = target_path.read_text(encoding="utf-8")
        merged_text = merge_markdown_with_preserved_blocks(existing_text, source_text)
    else:
        merged_text = source_text
    target_path.write_text(merged_text, encoding="utf-8")


def build_copilot_version_summary(lockfile_contents: dict, manifest: dict | None) -> str:
    package_version = None
    if manifest is not None:
        package_version = manifest.get("packageVersion")
    if not package_version:
        package_version = "unknown"

    summary_digest = {
        "version": package_version,
        "profile": lockfile_contents.get("profile"),
        "selectedPacks": lockfile_contents.get("selectedPacks", []),
        "manifestHash": lockfile_contents.get("manifest", {}).get("hash"),
        "appliedAt": lockfile_contents.get("timestamps", {}).get("appliedAt"),
    }

    selected_packs = lockfile_contents.get("selectedPacks", [])
    packs_summary = ", ".join(selected_packs) if selected_packs else "none"

    return (
        "# Xanad Assistant Installed Summary\n\n"
        f"Version: {package_version}\n"
        f"Profile: {lockfile_contents.get('profile') or 'unknown'}\n"
        f"Selected packs: {packs_summary}\n"
        f"Applied at: {lockfile_contents.get('timestamps', {}).get('appliedAt') or 'unknown'}\n"
        f"Lockfile: .github/xanad-assistant-lock.json\n\n"
        "```json\n"
        f"{json.dumps(summary_digest, indent=2)}\n"
        "```\n"
    )


def apply_chmod_rule(target_path: Path, chmod_rule: str) -> None:
    if chmod_rule != "executable":
        return
    current_mode = stat.S_IMODE(target_path.stat().st_mode)
    target_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def execute_apply_plan(workspace: Path, package_root: Path, plan_payload: dict) -> dict:
    manifest = load_manifest(package_root, load_json(package_root / DEFAULT_POLICY_PATH)) or {"managedFiles": []}
    manifest_entries = {entry["id"]: entry for entry in manifest.get("managedFiles", [])}
    actions = plan_payload["result"].get("actions", [])
    backup_plan = plan_payload["result"].get("backupPlan", {})
    planned_lockfile = json.loads(json.dumps(plan_payload["result"]["plannedLockfile"]))
    factory_restore = bool(plan_payload["result"].get("factoryRestore", False))
    apply_timestamp, path_timestamp = generate_apply_timestamps()

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

    writes = {
        "added": 0,
        "replaced": 0,
        "merged": 0,
        "skipped": len(plan_payload["result"].get("skippedActions", [])),
    }

    for action in actions:
        if action["action"] == "archive-retired":
            raise LifecycleCommandError(
                "apply_failure",
                "Retired file handling is not implemented in the current apply slice.",
                9,
                {"target": action["target"], "action": action["action"]},
            )
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
                merge_markdown_file(target_path, package_root, manifest_entry)
            writes["merged"] += 1
            continue

        target_path.write_bytes(render_entry_bytes(package_root, manifest_entry, action.get("tokenValues", {})))
        apply_chmod_rule(target_path, manifest_entry.get("chmod", "none"))

        if action["action"] == "add":
            writes["added"] += 1
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

    lockfile_path = workspace / planned_lockfile["path"]
    lockfile_path.parent.mkdir(parents=True, exist_ok=True)
    lockfile_path.write_text(json.dumps(planned_lockfile["contents"], indent=2) + "\n", encoding="utf-8")

    summary_path = workspace / ".github" / "copilot-version.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        build_copilot_version_summary(planned_lockfile["contents"], manifest),
        encoding="utf-8",
    )

    validation = build_check_result(workspace, package_root)
    if validation["status"] != "clean":
        raise LifecycleCommandError(
            "apply_failure",
            "Applied workspace did not validate cleanly.",
            9,
            {
                "backupPath": backup_root,
                "summary": validation["result"]["summary"],
            },
        )

    return {
        "backup": {
            "created": backup_root is not None,
            "path": backup_root,
        },
        "writes": writes,
        "retired": [],
        "lockfile": {
            "written": True,
            "path": planned_lockfile["path"],
        },
        "summary": {
            "written": True,
            "path": ".github/copilot-version.md",
        },
        "validation": {
            "status": "passed",
        },
    }


def build_execution_result(
    command: str,
    mode: str,
    workspace: Path,
    package_root: Path,
    answers_path: str | None,
    non_interactive: bool,
) -> dict:
    plan_payload = build_plan_result(workspace, package_root, mode, answers_path, non_interactive)
    apply_result = execute_apply_plan(workspace, package_root, plan_payload)

    return {
        "command": command,
        "mode": mode,
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "ok",
        "warnings": plan_payload["warnings"],
        "errors": [],
        "result": apply_result,
    }


def build_apply_result(workspace: Path, package_root: Path, answers_path: str | None, non_interactive: bool) -> dict:
    return build_execution_result("apply", "setup", workspace, package_root, answers_path, non_interactive)


def emit_json(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def emit_json_lines(payload: dict) -> None:
    command = payload["command"]
    if command == "inspect":
        events = [
            {
                "type": "phase",
                "command": command,
                "sequence": 1,
                "phase": "Preflight",
            },
            {
                "type": "inspect-summary",
                "command": command,
                "sequence": 2,
                "installState": payload["result"]["installState"],
                "manifestSummary": payload["result"]["manifestSummary"],
                "contracts": payload["result"]["contracts"],
            },
            {
                "type": "receipt",
                "command": command,
                "sequence": 3,
                "status": payload["status"],
            },
        ]
    elif command == "check":
        events = [
            {
                "type": "phase",
                "command": command,
                "sequence": 1,
                "phase": "Preflight",
            },
            {
                "type": "check-summary",
                "command": command,
                "sequence": 2,
                "status": payload["status"],
                "summary": payload["result"]["summary"],
                "unmanagedFiles": payload["result"]["unmanagedFiles"],
            },
            {
                "type": "receipt",
                "command": command,
                "sequence": 3,
                "status": payload["status"],
            },
        ]
    elif command == "interview":
        events = [
            {
                "type": "phase",
                "command": command,
                "sequence": 1,
                "phase": "Interview",
            }
        ]
        for question in payload["result"]["questions"]:
            event = {
                "type": "question",
                "command": command,
                "sequence": 0,
            }
            event.update(question)
            events.append(event)
        events.append(
            {
                "type": "receipt",
                "command": command,
                "sequence": 0,
                "status": payload["status"],
            }
        )
    elif command == "plan":
        events = [
            {
                "type": "phase",
                "command": command,
                "sequence": 1,
                "phase": "Preflight",
            },
            {
                "type": "inspect-summary",
                "command": command,
                "sequence": 2,
                "installState": payload["result"]["installState"],
                "legacyVersionFile": payload["result"]["installPaths"]["legacyVersionFile"],
                "lockfile": bool(payload["result"]["installPaths"]["lockfile"]),
            },
        ]
        for question in payload["result"]["questions"]:
            event = {
                "type": "question",
                "command": command,
                "sequence": 0,
            }
            event.update(question)
            events.append(event)
        events.extend(
            [
                {
                    "type": "phase",
                    "command": command,
                    "sequence": 0,
                    "phase": "Plan",
                },
                {
                    "type": "plan-summary",
                    "command": command,
                    "sequence": 0,
                    "mode": payload["mode"],
                    "approvalRequired": payload["result"]["approvalRequired"],
                    "backupRequired": payload["result"]["backupRequired"],
                    "backupPlan": payload["result"]["backupPlan"],
                    "plannedLockfile": payload["result"]["plannedLockfile"],
                    "writes": payload["result"]["writes"],
                    "conflicts": payload["result"]["conflictSummary"],
                },
                {
                    "type": "receipt",
                    "command": command,
                    "sequence": 0,
                    "status": payload["status"],
                },
            ]
        )
    elif command in {"apply", "update", "repair", "factory-restore"}:
        events = [
            {
                "type": "phase",
                "command": command,
                "sequence": 1,
                "phase": "Apply",
            },
            {
                "type": "apply-report",
                "command": command,
                "sequence": 2,
                "backup": payload["result"]["backup"],
                "writes": payload["result"]["writes"],
                "retired": payload["result"]["retired"],
                "lockfile": payload["result"]["lockfile"],
                "summary": payload["result"]["summary"],
                "validation": payload["result"]["validation"],
            },
            {
                "type": "receipt",
                "command": command,
                "sequence": 3,
                "status": payload["status"],
            },
        ]
    else:
        events = [
            {
                "type": "error",
                "command": command,
                "sequence": 1,
                "code": "not_implemented",
                "message": payload["errors"][0]["message"],
                "details": payload["errors"][0].get("details", {}),
            }
        ]

    for warning in payload.get("warnings", []):
        events.insert(
            2,
            {
                "type": "warning",
                "command": payload["command"],
                "sequence": 99,
                "code": warning["code"],
                "message": warning["message"],
                "details": warning.get("details", {}),
                "backupPlan": payload["result"]["backupPlan"],
            },
        )

    for index, event in enumerate(events, start=1):
        event["sequence"] = index
        sys.stdout.write(json.dumps(event) + "\n")


def emit_agent_progress(payload: dict) -> None:
    print("xanad-assistant", file=sys.stderr)
    if payload["command"] == "inspect":
        print("Preflight", file=sys.stderr)
        print("  Package contracts loaded", file=sys.stderr)
        print(f"  Install state: {payload['result']['installState']}", file=sys.stderr)
        print(
            f"  Manifest entries: {payload['result']['manifestSummary']['declared']}",
            file=sys.stderr,
        )
        return

    if payload["command"] == "check":
        print("Preflight", file=sys.stderr)
        print(f"  Check status: {payload['status']}", file=sys.stderr)
        print(f"  Missing targets: {payload['result']['summary']['missing']}", file=sys.stderr)
        return

    if payload["command"] == "interview":
        print("Interview", file=sys.stderr)
        print(f"  Questions emitted: {payload['result']['questionCount']}", file=sys.stderr)
        return

    if payload["command"] == "plan":
        print("Preflight", file=sys.stderr)
        print(f"  Install state: {payload['result']['installState']}", file=sys.stderr)
        print("Plan", file=sys.stderr)
        print(
            f"  Planned writes: {sum(payload['result']['writes'].values())}",
            file=sys.stderr,
        )
        if payload["result"]["conflicts"]:
            print(
                f"  Conflict classes: {len(payload['result']['conflicts'])}",
                file=sys.stderr,
            )
        if payload["result"]["approvalRequired"]:
            print("  Waiting on Copilot", file=sys.stderr)
        return

    if payload["command"] in {"apply", "update", "repair", "factory-restore"}:
        print("Apply", file=sys.stderr)
        print(f"  Files added: {payload['result']['writes']['added']}", file=sys.stderr)
        print(f"  Files replaced: {payload['result']['writes']['replaced']}", file=sys.stderr)
        print(f"  Summary written: {payload['result']['summary']['path']}", file=sys.stderr)
        print("Validate", file=sys.stderr)
        print(f"  Validation: {payload['result']['validation']['status']}", file=sys.stderr)
        return

    print("Preflight", file=sys.stderr)


def emit_payload(payload: dict, ui_mode: str, use_json_lines: bool) -> None:
    if ui_mode == "agent":
        emit_agent_progress(payload)

    if use_json_lines:
        emit_json_lines(payload)
        return
    emit_json(payload)


def build_not_implemented_payload(command: str, workspace: Path, package_root: Path, mode: str | None = None) -> dict:
    return {
        "command": command,
        "mode": mode,
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "not-implemented",
        "warnings": [],
        "errors": [
            {
                "code": "not_implemented",
                "message": f"{command} is not implemented in the current lifecycle slice.",
                "details": {"mode": mode},
            }
        ],
        "result": {},
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    workspace = resolve_workspace(args.workspace)
    package_root = resolve_package_root(args.package_root)
    use_json_lines = args.json_lines

    if args.command == "inspect":
        payload = build_inspect_result(workspace, package_root)
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "check":
        payload = build_check_result(workspace, package_root)
        emit_payload(payload, args.ui, use_json_lines)
        return 0 if payload["status"] == "clean" else 7

    if args.command == "interview":
        payload = build_interview_result(workspace, package_root, args.mode)
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "plan":
        try:
            payload = build_plan_result(workspace, package_root, args.mode, args.answers, args.non_interactive)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "plan",
                workspace,
                package_root,
                error.code,
                error.message,
                error.exit_code,
                mode=args.mode,
                details=error.details,
            )
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code
        plan_out_path = write_plan_output(args.plan_out, payload)
        if plan_out_path is not None:
            payload["result"]["planOut"] = plan_out_path
        emit_payload(payload, args.ui, use_json_lines)
        return 0 if not payload["errors"] else 1

    if args.command == "apply":
        try:
            payload = build_apply_result(workspace, package_root, args.answers, args.non_interactive)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "apply",
                workspace,
                package_root,
                error.code,
                error.message,
                error.exit_code,
                mode="setup",
                details=error.details,
            )
            report_out_path = write_report_output(args.report_out, payload)
            if report_out_path is not None:
                payload.setdefault("result", {})["reportOut"] = report_out_path
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code

        report_out_path = write_report_output(args.report_out, payload)
        if report_out_path is not None:
            payload["result"]["reportOut"] = report_out_path
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "update":
        try:
            payload = build_execution_result("update", "update", workspace, package_root, args.answers, args.non_interactive)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "update",
                workspace,
                package_root,
                error.code,
                error.message,
                error.exit_code,
                mode="update",
                details=error.details,
            )
            report_out_path = write_report_output(args.report_out, payload)
            if report_out_path is not None:
                payload.setdefault("result", {})["reportOut"] = report_out_path
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code

        report_out_path = write_report_output(args.report_out, payload)
        if report_out_path is not None:
            payload["result"]["reportOut"] = report_out_path
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "repair":
        try:
            payload = build_execution_result("repair", "repair", workspace, package_root, args.answers, args.non_interactive)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "repair",
                workspace,
                package_root,
                error.code,
                error.message,
                error.exit_code,
                mode="repair",
                details=error.details,
            )
            report_out_path = write_report_output(args.report_out, payload)
            if report_out_path is not None:
                payload.setdefault("result", {})["reportOut"] = report_out_path
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code

        report_out_path = write_report_output(args.report_out, payload)
        if report_out_path is not None:
            payload["result"]["reportOut"] = report_out_path
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "factory-restore":
        try:
            payload = build_execution_result(
                "factory-restore",
                "factory-restore",
                workspace,
                package_root,
                args.answers,
                args.non_interactive,
            )
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "factory-restore",
                workspace,
                package_root,
                error.code,
                error.message,
                error.exit_code,
                mode="factory-restore",
                details=error.details,
            )
            report_out_path = write_report_output(args.report_out, payload)
            if report_out_path is not None:
                payload.setdefault("result", {})["reportOut"] = report_out_path
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code

        report_out_path = write_report_output(args.report_out, payload)
        if report_out_path is not None:
            payload["result"]["reportOut"] = report_out_path
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    mode = getattr(args, "mode", None)
    payload = build_not_implemented_payload(args.command, workspace, package_root, mode)
    emit_payload(payload, args.ui, use_json_lines)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())