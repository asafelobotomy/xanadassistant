from __future__ import annotations

import argparse
from pathlib import Path

from scripts.lifecycle._manifest_utils import (
    OWNERSHIP_MODES,
    WRITE_STRATEGIES,
    build_file_id,
    detect_tokens_in_source,
    is_excluded_path,
    iter_all_files,
    iter_source_files,
    load_json,
    load_optional_registry,
    normalize_condition_expression,
    normalize_relpath,
    sha256_file,
    target_for_entry,
    write_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate xanadAssistant install manifest.")
    parser.add_argument("--package-root", required=True, help="Path to the xanadAssistant package root.")
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


def _derive_pack_dir_surfaces(package_root: Path, pack_id: str) -> set[str]:
    pack_root = package_root / "packs" / pack_id
    surfaces: set[str] = set()
    for directory_name, surface_kind in (("skills", "skills"), ("prompts", "prompts"), ("mcp", "hooks")):
        if (pack_root / directory_name).is_dir():
            surfaces.add(f"{pack_id}-{surface_kind}")
    return surfaces


def _derive_policy_pack_surfaces(policy: dict, pack_id: str) -> set[str]:
    expected_source_root = f"{pack_id}-pack"
    surfaces: set[str] = set()
    for surface_name, source_spec in policy.get("surfaceSources", {}).items():
        if source_spec.get("sourceRoot") == expected_source_root and source_spec.get("layer") == "pack":
            surfaces.add(surface_name)
    return surfaces


def validate_pack_registry(package_root: Path, policy: dict, pack_registry: dict) -> None:
    mismatches: list[str] = []

    for pack in pack_registry.get("packs", []):
        if pack.get("status") != "active":
            continue
        pack_id = pack["id"]
        registry_surfaces = set(pack.get("surfaces", []))
        dir_surfaces = _derive_pack_dir_surfaces(package_root, pack_id)
        policy_surfaces = _derive_policy_pack_surfaces(policy, pack_id)

        if registry_surfaces != dir_surfaces or registry_surfaces != policy_surfaces:
            mismatches.append(
                f"{pack_id}: registry={sorted(registry_surfaces)} dir={sorted(dir_surfaces)} policy={sorted(policy_surfaces)}"
            )

    if mismatches:
        raise ValueError("Pack registry surfaces are inconsistent: " + "; ".join(mismatches))


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

    version_file = package_root / "VERSION"
    package_version = (
        version_file.read_text(encoding="utf-8").strip()
        if version_file.is_file()
        else policy["schemaVersion"]
    )

    return {
        "schemaVersion": policy.get("generationSettings", {}).get("manifestSchemaVersion", policy["schemaVersion"]),
        "packageVersion": package_version,
        "policySchemaVersion": policy["schemaVersion"],
        "sourceRoots": source_roots,
        "generationSettings": policy.get("generationSettings", {}),
        "managedFiles": managed_files,
        "retiredFiles": retired_files,
    }


def generate_catalog(policy: dict, pack_registry: dict, profile_registry: dict) -> dict:
    """Generate catalog.json from policy, pack registry, and profile registry."""
    command_categories = {
        "inspect": "read-only",
        "interview": "read-only",
        "check": "read-only",
        "plan": "planning",
        "apply": "write",
        "update": "write",
        "repair": "write",
        "factory-restore": "write",
    }
    surface_sources = policy.get("surfaceSources", {})
    surface_layers = {name: spec.get("layer", "core") for name, spec in surface_sources.items()}
    packs = [pack["id"] for pack in pack_registry.get("packs", [])]
    profiles = [profile["id"] for profile in profile_registry.get("profiles", [])]

    return {
        "schemaVersion": "0.1.0",
        "generatedFrom": "policy+registries",
        "commands": [{"id": cmd_id, "category": category} for cmd_id, category in command_categories.items()],
        "ownershipModes": sorted(OWNERSHIP_MODES),
        "compatibilityTargets": [
            "copilot-format",
            "local-package-root",
            "json-lines-protocol",
        ],
        "surfaceLayers": surface_layers,
        "packs": packs,
        "profiles": profiles,
    }


def main() -> int:
    args = parse_args()
    package_root = Path(args.package_root).resolve()
    policy_path = package_root / args.policy
    manifest_out = args.manifest_out

    policy = load_json(policy_path)
    pack_registry = None
    if policy.get("generationSettings", {}).get("derivedArtifactStrategy", {}).get("catalog") == "generated-from-policy-and-registries":
        pack_registry = load_optional_registry(package_root / "template/setup/pack-registry.json")
        validate_pack_registry(package_root, policy, pack_registry)
    manifest = generate_manifest(package_root, policy)
    output_path = package_root / (manifest_out or policy.get("generationSettings", {}).get("manifestOutput", "template/setup/install-manifest.json"))
    write_manifest(output_path, manifest)

    catalog_strategy = policy.get("generationSettings", {}).get("derivedArtifactStrategy", {}).get("catalog")
    if catalog_strategy == "generated-from-policy-and-registries":
        assert pack_registry is not None
        profile_registry = load_optional_registry(package_root / "template/setup/profile-registry.json")
        catalog = generate_catalog(policy, pack_registry, profile_registry)
        catalog_path = package_root / "template/setup/catalog.json"
        write_manifest(catalog_path, catalog)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())