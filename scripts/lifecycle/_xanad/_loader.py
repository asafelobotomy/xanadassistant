from __future__ import annotations

import json
from pathlib import Path

from scripts.lifecycle._manifest_utils import load_json, sha256_file  # noqa: F401 – re-exported
from scripts.lifecycle._xanad._errors import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_LOCK_SCHEMA_PATH,
    DEFAULT_MANIFEST_SCHEMA_PATH,
    DEFAULT_PACK_REGISTRY_PATH,
    DEFAULT_POLICY_PATH,
    DEFAULT_POLICY_SCHEMA_PATH,
    DEFAULT_PROFILE_REGISTRY_PATH,
    LifecycleCommandError,
)


def load_optional_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return load_json(path)


def load_contract_artifacts(package_root: Path) -> tuple[dict, dict]:
    policy_path = package_root / DEFAULT_POLICY_PATH
    policy_schema_path = package_root / DEFAULT_POLICY_SCHEMA_PATH
    manifest_schema_path = package_root / DEFAULT_MANIFEST_SCHEMA_PATH
    lock_schema_path = package_root / DEFAULT_LOCK_SCHEMA_PATH

    try:
        policy = load_json(policy_path)
    except FileNotFoundError:
        raise LifecycleCommandError(
            "contract_input_failure",
            f"Required policy file not found: {policy_path}",
            4,
            {"path": str(policy_path)},
        )
    except (json.JSONDecodeError, OSError) as exc:
        raise LifecycleCommandError(
            "contract_input_failure",
            f"Policy file is malformed or unreadable: {exc}",
            4,
            {"path": str(policy_path)},
        )
    manifest_path = package_root / policy.get("generationSettings", {}).get(
        "manifestOutput", "template/setup/install-manifest.json"
    )

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
    manifest_path = package_root / policy.get("generationSettings", {}).get(
        "manifestOutput", "template/setup/install-manifest.json"
    )
    if not manifest_path.exists():
        return None
    return load_json(manifest_path)
