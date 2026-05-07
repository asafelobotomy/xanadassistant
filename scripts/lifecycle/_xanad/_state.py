from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from scripts.lifecycle._xanad._loader import load_json, load_optional_json


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
    return False


def migrate_lockfile_shape(data: dict) -> dict:
    """Return a copy of *data* with missing required fields filled with safe defaults."""
    migrated = dict(data)
    migrated.setdefault("schemaVersion", "0.1.0")
    if not isinstance(migrated.get("package"), dict) or "name" not in migrated.get("package", {}):
        migrated["package"] = {"name": "xanad-assistant"}
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
    migrated.setdefault("skippedManagedFiles", [])
    return migrated


def parse_lockfile_state(workspace: Path) -> dict:
    lockfile_path = workspace / ".github" / "xanad-assistant-lock.json"
    if not lockfile_path.exists():
        return {
            "present": False, "malformed": False, "needsMigration": False,
            "path": str(lockfile_path), "data": None,
            "selectedPacks": [], "profile": None, "ownershipBySurface": {},
            "skippedManagedFiles": [], "unknownValues": {}, "files": [],
        }

    try:
        data = load_json(lockfile_path)
    except json.JSONDecodeError:
        return {
            "present": True, "malformed": True, "needsMigration": False,
            "path": str(lockfile_path), "data": None,
            "selectedPacks": [], "profile": None, "ownershipBySurface": {},
            "skippedManagedFiles": [], "unknownValues": {}, "files": [],
        }

    needs_migration = _lockfile_needs_migration(data)
    if needs_migration:
        data = migrate_lockfile_shape(data)

    return {
        "present": True, "malformed": False, "needsMigration": needs_migration,
        "path": str(lockfile_path), "data": data,
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
