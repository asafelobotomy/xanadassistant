from __future__ import annotations

import argparse
import hashlib
import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable


OWNERSHIP_MODES = {
    "local",
    "plugin-backed-copilot-format",
}

WRITE_STRATEGIES = {
    "replace-verbatim",
    "copy-if-missing",
    "merge-json-object",
    "preserve-marked-markdown-blocks",
    "token-replace",
    "archive-retired",
    "report-retired",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate xanad-assistant install manifest.")
    parser.add_argument("--package-root", required=True, help="Path to the xanad-assistant package root.")
    parser.add_argument(
        "--policy",
        default="template/setup/install-policy.json",
        help="Path to the install policy relative to the package root.",
    )
    parser.add_argument(
        "--manifest-out",
        default=None,
        help="Path to write the generated manifest, relative to the package root.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_relpath(path: Path) -> str:
    return path.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def detect_tokens_in_source(path: Path, token_rules: list[dict]) -> list[str]:
    if not token_rules:
        return []

    text = path.read_text(encoding="utf-8")
    matched_tokens = [rule["token"] for rule in token_rules if rule["token"] in text]
    return sorted(set(matched_tokens))


def build_file_id(surface_name: str, relative_path: Path) -> str:
    raw = normalize_relpath(relative_path)
    if raw == ".":
        return surface_name
    return f"{surface_name}.{raw.replace('/', '.')}"


def iter_source_files(base_path: Path, source_kind: str) -> Iterable[tuple[Path, Path]]:
    if source_kind == "file":
        if base_path.is_file():
            yield base_path, Path(base_path.name)
        return

    if not base_path.is_dir():
        return

    for file_path in sorted(path for path in base_path.rglob("*") if path.is_file()):
        yield file_path, file_path.relative_to(base_path)


def target_for_entry(target_root: str, path_pattern: str | None, relative_path: Path, source_kind: str) -> str:
    if source_kind == "file" and path_pattern:
        return normalize_relpath(Path(target_root) / path_pattern)
    return normalize_relpath(Path(target_root) / relative_path)


def validate_policy(policy: dict) -> None:
    missing = []
    for surface_name in policy.get("canonicalSurfaces", []):
        if surface_name not in policy.get("surfaceSources", {}):
            missing.append(f"surfaceSources.{surface_name}")
        if surface_name not in policy.get("targetPathRules", {}):
            missing.append(f"targetPathRules.{surface_name}")
        if surface_name not in policy.get("ownershipDefaults", {}):
            missing.append(f"ownershipDefaults.{surface_name}")
        if surface_name not in policy.get("strategyDefaults", {}):
            missing.append(f"strategyDefaults.{surface_name}")

    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(f"Policy is missing required surface mappings: {joined}")


def resolve_surface_base_path(package_root: Path, source_roots: dict, source_spec: dict) -> Path:
    if source_spec["sourceRoot"] not in source_roots:
        raise ValueError(f"Unknown source root for surface: {source_spec['sourceRoot']}")
    return package_root / source_roots[source_spec["sourceRoot"]] / source_spec["path"]


def iter_all_files(base_path: Path) -> Iterable[Path]:
    for file_path in sorted(path for path in base_path.rglob("*") if path.is_file()):
        yield file_path


def is_excluded_path(relative_path: str, patterns: list[str]) -> bool:
    return any(fnmatch(relative_path, pattern) for pattern in patterns)


def normalize_condition_expression(expression: str | list[str] | None) -> list[str]:
    if expression is None:
        return []
    if isinstance(expression, str):
        return [expression]
    return list(expression)


def resolve_supported_ownership(surface_name: str, default_ownership: str, delivery_rules: dict) -> list[str]:
    delivery_rule = delivery_rules.get(surface_name, {})
    supported_ownership = delivery_rule.get("supportedOwnership")
    if supported_ownership is None:
        return [default_ownership]
    if default_ownership not in supported_ownership:
        raise ValueError(f"Default ownership for {surface_name} must be present in supportedOwnership.")
    unsupported = [mode for mode in supported_ownership if mode not in OWNERSHIP_MODES]
    if unsupported:
        raise ValueError(f"Unsupported ownership mode for {surface_name}: {', '.join(unsupported)}")
    return list(supported_ownership)


def validate_surface_sources(package_root: Path, policy: dict) -> None:
    source_roots = policy["sourceRoots"]
    surface_sources = policy["surfaceSources"]

    for surface_name in policy.get("canonicalSurfaces", []):
        source_spec = surface_sources[surface_name]
        base_path = resolve_surface_base_path(package_root, source_roots, source_spec)
        if source_spec["kind"] == "file" and not base_path.is_file():
            raise ValueError(f"Managed source file is missing for {surface_name}: {normalize_relpath(base_path.relative_to(package_root))}")
        if source_spec["kind"] == "directory" and not base_path.is_dir():
            raise ValueError(f"Managed source directory is missing for {surface_name}: {normalize_relpath(base_path.relative_to(package_root))}")


def validate_unmanaged_sources(package_root: Path, policy: dict) -> None:
    source_roots = policy["sourceRoots"]
    surface_sources = policy["surfaceSources"]
    excludes = policy.get("generationSettings", {}).get("unmanagedSourceExcludes", [])

    root_to_surfaces: dict[str, list[dict]] = {}
    for surface_name in policy.get("canonicalSurfaces", []):
        source_spec = surface_sources[surface_name]
        root_to_surfaces.setdefault(source_spec["sourceRoot"], []).append(source_spec)

    unmanaged_files: list[str] = []
    for root_name, root_relative in source_roots.items():
        if root_name not in root_to_surfaces:
            continue

        root_path = package_root / root_relative
        if not root_path.exists() or not root_path.is_dir():
            continue

        covered_files: set[str] = set()
        for source_spec in root_to_surfaces[root_name]:
            base_path = resolve_surface_base_path(package_root, source_roots, source_spec)
            if source_spec["kind"] == "file":
                covered_files.add(normalize_relpath(base_path.relative_to(package_root)))
                continue
            for file_path in iter_all_files(base_path):
                covered_files.add(normalize_relpath(file_path.relative_to(package_root)))

        for file_path in iter_all_files(root_path):
            relative = normalize_relpath(file_path.relative_to(package_root))
            if relative in covered_files:
                continue
            if is_excluded_path(relative, excludes):
                continue
            unmanaged_files.append(relative)

    if unmanaged_files:
        joined = ", ".join(unmanaged_files)
        raise ValueError(f"Managed source files lack policy coverage: {joined}")


def generate_manifest(package_root: Path, policy: dict) -> dict:
    validate_policy(policy)
    validate_surface_sources(package_root, policy)
    validate_unmanaged_sources(package_root, policy)

    managed_files = []
    retired_files = []
    source_roots = policy["sourceRoots"]
    surface_sources = policy["surfaceSources"]
    target_rules = policy["targetPathRules"]
    ownership_defaults = policy["ownershipDefaults"]
    strategy_defaults = policy["strategyDefaults"]
    required_conditions = policy.get("requiredConditions", {})
    chmod_rules = policy.get("chmodRules", {})
    delivery_rules = policy.get("packageFormatDeliveryRules", {})
    token_rules = policy.get("tokenRules", [])

    for surface_name in policy.get("canonicalSurfaces", []):
        source_spec = surface_sources[surface_name]
        base_path = resolve_surface_base_path(package_root, source_roots, source_spec)
        target_rule = target_rules[surface_name]
        ownership_mode = ownership_defaults[surface_name]
        supported_ownership = resolve_supported_ownership(surface_name, ownership_mode, delivery_rules)
        strategy = strategy_defaults[surface_name]

        if ownership_mode not in OWNERSHIP_MODES:
            raise ValueError(f"Unsupported ownership mode for {surface_name}: {ownership_mode}")
        if strategy not in WRITE_STRATEGIES:
            raise ValueError(f"Unsupported write strategy for {surface_name}: {strategy}")

        for file_path, relative_path in iter_source_files(base_path, source_spec["kind"]):
            managed_files.append(
                {
                    "id": build_file_id(surface_name, relative_path),
                    "surface": target_rule.get("surface", surface_name),
                    "layer": source_spec["layer"],
                    "source": normalize_relpath(file_path.relative_to(package_root)),
                    "target": target_for_entry(
                        target_rule["targetRoot"],
                        target_rule.get("pathPattern"),
                        relative_path,
                        source_spec["kind"],
                    ),
                    "ownership": supported_ownership,
                    "strategy": strategy,
                    "requiredWhen": normalize_condition_expression(required_conditions.get(surface_name, [])),
                    "tokens": detect_tokens_in_source(file_path, token_rules),
                    "chmod": chmod_rules.get(surface_name, "none"),
                    "hash": sha256_file(file_path),
                }
            )

    managed_files.sort(key=lambda entry: (entry["target"], entry["id"]))
    retired_policy = policy.get("retiredFilePolicy", {})
    if policy.get("generationSettings", {}).get("includeRetiredFiles", False):
        retired_files = retired_policy.get("entries", [])

    return {
        "schemaVersion": policy.get("generationSettings", {}).get("manifestSchemaVersion", policy["schemaVersion"]),
        "packageVersion": policy["schemaVersion"],
        "policySchemaVersion": policy["schemaVersion"],
        "sourceRoots": source_roots,
        "generationSettings": policy.get("generationSettings", {}),
        "managedFiles": managed_files,
        "retiredFiles": retired_files,
    }


def write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    package_root = Path(args.package_root).resolve()
    policy_path = package_root / args.policy
    manifest_out = args.manifest_out

    policy = load_json(policy_path)
    manifest = generate_manifest(package_root, policy)
    output_path = package_root / (manifest_out or policy.get("generationSettings", {}).get("manifestOutput", "template/setup/install-manifest.json"))
    write_manifest(output_path, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())