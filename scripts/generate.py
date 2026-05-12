#!/usr/bin/env python3
"""Regenerate all derived artifacts from canonical sources.

Run from the repository root:

    python3 scripts/generate.py

This produces:
  template/setup/install-manifest.json  — from install-policy.json + filesystem scan
  template/setup/catalog.json           — from install-policy.json + registries
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lifecycle.generate_manifest import (
    generate_catalog,
    generate_manifest,
    load_json,
    load_optional_registry,
    write_manifest,
)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    policy_path = repo_root / "template/setup/install-policy.json"
    try:
        policy = load_json(policy_path)
    except FileNotFoundError:
        print(f"ERROR: Policy file not found: {policy_path}", file=sys.stderr)
        return 1
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: Cannot load policy at {policy_path}: {exc}", file=sys.stderr)
        return 1

    manifest = generate_manifest(repo_root, policy)
    manifest_path = repo_root / policy.get("generationSettings", {}).get(
        "manifestOutput", "template/setup/install-manifest.json"
    )
    write_manifest(manifest_path, manifest)
    print(f"manifest → {manifest_path.relative_to(repo_root)}")

    artifact_strategy = policy.get("generationSettings", {}).get("derivedArtifactStrategy", {})
    if artifact_strategy.get("catalog") == "generated-from-policy-and-registries":
        pack_registry = load_optional_registry(repo_root / "template/setup/pack-registry.json")
        profile_registry = load_optional_registry(repo_root / "template/setup/profile-registry.json")
        catalog = generate_catalog(policy, pack_registry, profile_registry)
        catalog_path = repo_root / "template/setup/catalog.json"
        write_manifest(catalog_path, catalog)
        print(f"catalog  → {catalog_path.relative_to(repo_root)}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
