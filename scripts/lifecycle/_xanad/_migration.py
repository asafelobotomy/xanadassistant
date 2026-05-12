from __future__ import annotations

"""Lockfile migration helpers.

Factored out of _state.py to keep that module under the 250-line warning threshold.
"""


CURRENT_PACKAGE_NAME = "xanadAssistant"
PREDECESSOR_PACKAGE_NAMES = frozenset({"copilot-instructions-template"})

_LOCKFILE_REQUIRED_FIELDS = frozenset({
    "schemaVersion", "package", "manifest", "timestamps", "selectedPacks", "files",
})


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
    migrated.setdefault("resolvedTokenConflicts", {})
    return migrated
