from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.lifecycle.generate_manifest import generate_manifest, load_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether the generated manifest is fresh.")
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
    return parser.parse_args()


def compare_manifest_to_generated(package_root: Path, policy_rel: str, manifest_rel: str) -> tuple[bool, dict, dict]:
    policy = load_json(package_root / policy_rel)
    current_manifest = load_json(package_root / manifest_rel)
    generated_manifest = generate_manifest(package_root, policy)
    return current_manifest == generated_manifest, current_manifest, generated_manifest


def main() -> int:
    args = parse_args()
    package_root = Path(args.package_root).resolve()
    is_fresh, current_manifest, generated_manifest = compare_manifest_to_generated(
        package_root,
        args.policy,
        args.manifest,
    )
    if is_fresh:
        return 0

    print("install-manifest.json is stale relative to install-policy.json", file=sys.stderr)
    print(json.dumps({"current": current_manifest, "generated": generated_manifest}, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())