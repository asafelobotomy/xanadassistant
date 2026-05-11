from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from scripts.lifecycle._xanad._loader import load_json, load_optional_json


CURRENT_PACKAGE_NAME = "xanadAssistant"
PREDECESSOR_PACKAGE_NAMES = frozenset({"copilot-instructions-template"})
_LOCKFILE_FILENAME = "xanadAssistant-lock.json"
_LEGACY_LOCKFILE_FILENAME = "xanad-assistant-lock.json"


def _resolve_lockfile_path(workspace: Path) -> Path:
    """Return the canonical lockfile path, falling back to the legacy name for migration."""
    new_path = workspace / ".github" / _LOCKFILE_FILENAME
    if not new_path.exists():
        legacy_path = workspace / ".github" / _LEGACY_LOCKFILE_FILENAME
        if legacy_path.exists():
            return legacy_path
    return new_path
_LOCKFILE_REQUIRED_FIELDS = frozenset({"schemaVersion", "package", "manifest", "timestamps", "selectedPacks", "files"})


def detect_git_state(workspace: Path) -> dict:
    git_dir = workspace / ".git"
    if not git_dir.exists():
        return {"present": False, "dirty": None}

    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return {"present": True, "dirty": None}

    if result.returncode != 0:
        return {"present": True, "dirty": None}

    return {"present": True, "dirty": bool(result.stdout.strip())}


def determine_install_state(workspace: Path) -> tuple[str, dict]:
    lockfile = _resolve_lockfile_path(workspace)
    legacy_version = workspace / ".github" / "copilot-version.md"

    if lockfile.exists():
        return "installed", {"lockfile": str(lockfile), "legacyVersionFile": legacy_version.exists()}
    if legacy_version.exists():
        return "legacy-version-only", {"lockfile": None, "legacyVersionFile": True}
    return "not-installed", {"lockfile": None, "legacyVersionFile": False}


def parse_legacy_version_file(workspace: Path) -> dict:
    legacy_path = workspace / ".github" / "copilot-version.md"
    if not legacy_path.exists():
        return {"present": False, "malformed": False, "path": str(legacy_path), "data": None}

    text = legacy_path.read_text(encoding="utf-8")
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return {
                "present": True, "malformed": False,
                "path": str(legacy_path),
                "data": json.loads(json_match.group(1)),
            }
        except json.JSONDecodeError:
            return {"present": True, "malformed": True, "path": str(legacy_path), "data": None}

    version_match = re.search(r"(?im)^version\s*:\s*(?P<version>.+?)\s*$", text)
    if version_match:
        return {
            "present": True, "malformed": False,
            "path": str(legacy_path),
            "data": {"version": version_match.group("version")},
        }

    return {"present": True, "malformed": True, "path": str(legacy_path), "data": None}


def _lockfile_needs_migration(data: dict) -> bool:
    """Return True when a valid-JSON lockfile is missing required 0.1.0 schema fields."""
    if not isinstance(data, dict):
        return False
    missing = _LOCKFILE_REQUIRED_FIELDS - data.keys()
    if missing:
        return True
    manifest_block = data.get("manifest")
    if not isinstance(manifest_block, dict):
        return True
    if "schemaVersion" not in manifest_block or "hash" not in manifest_block:
        return True
    package_block = data.get("package")
    if not isinstance(package_block, dict) or "name" not in package_block:
        return True
    if package_block.get("name") != CURRENT_PACKAGE_NAME:
        return True
    return False


def get_lockfile_package_name(lockfile_state: dict) -> str | None:
    data = lockfile_state.get("data")
    if not isinstance(data, dict):
        return None
    package_block = data.get("package")
    if not isinstance(package_block, dict):
        return None
    package_name = package_block.get("name")
    return package_name if isinstance(package_name, str) else None


def get_predecessor_package_name(lockfile_state: dict) -> str | None:
    package_name = lockfile_state.get("originalPackageName")
    if not isinstance(package_name, str):
        package_name = get_lockfile_package_name(lockfile_state)
    if package_name in PREDECESSOR_PACKAGE_NAMES:
        return package_name
    return None


def migrate_lockfile_shape(data: dict) -> dict:
    """Return a copy of *data* with missing required fields filled with safe defaults."""
    migrated = dict(data)
    migrated.setdefault("schemaVersion", "0.1.0")
    existing_package_name = None
    if isinstance(migrated.get("package"), dict):
        existing_package_name = migrated.get("package", {}).get("name")
    if not isinstance(migrated.get("package"), dict) or migrated.get("package", {}).get("name") != CURRENT_PACKAGE_NAME:
        migrated["package"] = {"name": CURRENT_PACKAGE_NAME}
    manifest_block = migrated.get("manifest")
    if not isinstance(manifest_block, dict):
        migrated["manifest"] = {"schemaVersion": "0.1.0", "hash": "sha256:unknown"}
    else:
        manifest_block = dict(manifest_block)
        manifest_block.setdefault("schemaVersion", "0.1.0")
        manifest_block.setdefault("hash", "sha256:unknown")
        migrated["manifest"] = manifest_block
    if not isinstance(migrated.get("timestamps"), dict):
        migrated["timestamps"] = {
            "appliedAt": "1970-01-01T00:00:00Z",
            "updatedAt": "1970-01-01T00:00:00Z",
        }
    if not isinstance(migrated.get("selectedPacks"), list):
        migrated["selectedPacks"] = []
    if not isinstance(migrated.get("files"), list):
        migrated["files"] = []
    migrated.setdefault("unknownValues", {})
    if isinstance(existing_package_name, str) and existing_package_name != CURRENT_PACKAGE_NAME:
        migrated["unknownValues"].setdefault("migratedFromPackageName", existing_package_name)
    migrated.setdefault("skippedManagedFiles", [])
    return migrated


def parse_lockfile_state(workspace: Path) -> dict:
    lockfile_path = _resolve_lockfile_path(workspace)
    if not lockfile_path.exists():
        return {
            "present": False, "malformed": False, "needsMigration": False,
            "path": str(lockfile_path), "data": None,
            "selectedPacks": [], "profile": None, "ownershipBySurface": {},
            "skippedManagedFiles": [], "unknownValues": {}, "files": [],
            "setupAnswers": {}, "mcpEnabled": None,
        }

    try:
        data = load_json(lockfile_path)
    except json.JSONDecodeError:
        return {
            "present": True, "malformed": True, "needsMigration": False,
            "path": str(lockfile_path), "data": None,
            "selectedPacks": [], "profile": None, "ownershipBySurface": {},
            "skippedManagedFiles": [], "unknownValues": {}, "files": [],
            "setupAnswers": {}, "mcpEnabled": None,
        }

    original_package_name = None
    if isinstance(data.get("package"), dict):
        package_name = data.get("package", {}).get("name")
        if isinstance(package_name, str):
            original_package_name = package_name

    needs_migration = _lockfile_needs_migration(data)
    if needs_migration:
        data = migrate_lockfile_shape(data)

    return {
        "present": True, "malformed": False, "needsMigration": needs_migration,
        "path": str(lockfile_path), "data": data,
        "originalPackageName": original_package_name,
        "selectedPacks": data.get("selectedPacks", []),
        "profile": data.get("profile"),
        "ownershipBySurface": data.get("ownershipBySurface", {}),
        "skippedManagedFiles": data.get("skippedManagedFiles", []),
        "unknownValues": data.get("unknownValues", {}),
        "files": data.get("files", []),
        "setupAnswers": data.get("setupAnswers", {}),
        "mcpEnabled": data.get("installMetadata", {}).get("mcpEnabled"),
    }


def read_lockfile_status(workspace: Path) -> dict:
    lockfile_state = parse_lockfile_state(workspace)
    return {
        "present": lockfile_state["present"],
        "malformed": lockfile_state["malformed"],
        "needsMigration": lockfile_state.get("needsMigration", False),
    }


def count_files(path: Path) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    return sum(1 for file_path in path.rglob("*") if file_path.is_file())


def detect_existing_surfaces(workspace: Path) -> dict:
    return {
        "instructions": {"present": (workspace / ".github" / "copilot-instructions.md").exists()},
        "prompts": {"count": count_files(workspace / ".github" / "prompts")},
        "agents": {"count": count_files(workspace / ".github" / "agents")},
        "skills": {"count": count_files(workspace / ".github" / "skills")},
        "hooks": {"count": count_files(workspace / ".github" / "hooks")},
        "mcp": {"present": (workspace / ".vscode" / "mcp.json").exists()},
        "workspace": {"count": count_files(workspace / ".copilot" / "workspace")},
    }


def summarize_manifest_targets(workspace: Path, manifest: dict | None) -> dict:
    if manifest is None:
        return {"declared": 0, "present": 0, "missing": 0, "skipped": 0, "retired": 0}

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
        "declared": declared, "present": present, "missing": missing,
        "skipped": skipped, "retired": len(manifest.get("retiredFiles", [])),
    }
