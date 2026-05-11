from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.lifecycle.generate_manifest import generate_catalog, generate_manifest, load_json, load_optional_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether the generated manifest and catalog are fresh.")
    parser.add_argument("--package-root", required=True, help="Path to the xanad-assistant package root.")
    parser.add_argument(
        "--policy",
        default="template/setup/install-policy.json",
        help="Path to the install policy relative to the package root.",
    )
    parser.add_argument(
        "--manifest",
        default="template/setup/install-manifest.json",
        help="Path to the committed manifest relative to the package root.",
    )
    parser.add_argument(
        "--catalog",
        default=None,
        help="Path to the committed catalog relative to the package root. When provided, catalog freshness is also checked.",
    )
    return parser.parse_args()


def compare_manifest_to_generated(package_root: Path, policy_rel: str, manifest_rel: str) -> tuple[bool, dict, dict]:
    policy = load_json(package_root / policy_rel)
    current_manifest = load_json(package_root / manifest_rel)
    generated_manifest = generate_manifest(package_root, policy)
    return current_manifest == generated_manifest, current_manifest, generated_manifest


def compare_catalog_to_generated(package_root: Path, policy_rel: str, catalog_rel: str) -> tuple[bool, dict, dict]:
    policy = load_json(package_root / policy_rel)
    current_catalog = load_json(package_root / catalog_rel)
    pack_registry = load_optional_registry(package_root / "template/setup/pack-registry.json")
    profile_registry = load_optional_registry(package_root / "template/setup/profile-registry.json")
    generated_catalog = generate_catalog(policy, pack_registry, profile_registry)
    return current_catalog == generated_catalog, current_catalog, generated_catalog


def main() -> int:
    args = parse_args()
    package_root = Path(args.package_root).resolve()
    exit_code = 0

    is_fresh, current_manifest, generated_manifest = compare_manifest_to_generated(
        package_root,
        args.policy,
        args.manifest,
    )
    if not is_fresh:
        print("install-manifest.json is stale relative to install-policy.json", file=sys.stderr)
        print(json.dumps({"current": current_manifest, "generated": generated_manifest}, indent=2), file=sys.stderr)
        exit_code = 1

    if args.catalog is not None:
        is_catalog_fresh, current_catalog, generated_catalog = compare_catalog_to_generated(
            package_root,
            args.policy,
            args.catalog,
        )
        if not is_catalog_fresh:
            print("catalog.json is stale relative to install-policy.json and registries", file=sys.stderr)
            print(json.dumps({"current": current_catalog, "generated": generated_catalog}, indent=2), file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())