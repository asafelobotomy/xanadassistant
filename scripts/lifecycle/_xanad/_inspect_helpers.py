from __future__ import annotations

from pathlib import Path

from scripts.lifecycle.generate_manifest import sha256_file
from scripts.lifecycle._xanad._conditions import entry_required_for_plan
from scripts.lifecycle._xanad._plan_utils import expected_entry_hash
from scripts.lifecycle._xanad._state import get_predecessor_package_name


_SUCCESSOR_MIGRATION_ROOTS = (
    ".github/agents",
    ".github/skills",
    ".github/prompts",
    ".github/instructions",
    ".github/mcp",
    ".github/hooks",
    ".copilot/workspace",
)
_SUCCESSOR_MIGRATION_FILES = (".mcp.json",)


def annotate_manifest_entries(
    workspace: Path,
    package_root: Path,
    manifest: dict | None,
    ownership_by_surface: dict,
    resolved_answers: dict,
    token_values: dict[str, str],
    consumer_resolutions: dict | None = None,
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
        elif consumer_resolutions and entry["target"] in consumer_resolutions:
            annotated_entry["status"] = "skipped"
            annotated_entry["skipReason"] = "consumer-keep"
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
        "clean": 0, "missing": 0, "stale": 0, "malformed": 0,
        "skipped": 0, "retired": 0, "unmanaged": 0, "unknown": 0,
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
            raise ValueError(f"Managed manifest entry must be annotated with status before classification: {entry['id']}")
        counts[status] += 1
        entries.append({"id": entry["id"], "target": target, "status": status})

    for retired in manifest.get("retiredFiles", []):
        retired_target = retired.get("target")
        retired_action = retired.get("action", "archive-retired")
        if retired_target and (workspace / retired_target).exists() and retired_action != "report-retired":
            counts["retired"] += 1
            entries.append({"id": retired["id"], "target": retired_target, "status": "retired"})

    return counts, entries, managed_targets


def collect_unmanaged_files(workspace: Path, manifest: dict | None, managed_targets: set[str]) -> list[str]:
    if manifest is None:
        return []

    retired_targets = {entry.get("target") for entry in manifest.get("retiredFiles", [])}
    candidate_dirs = {str(Path(target).parent) for target in managed_targets}
    managed_targets_by_dir: dict[str, list[Path]] = {}
    for target in managed_targets:
        target_path = Path(target)
        managed_targets_by_dir.setdefault(str(target_path.parent), []).append(target_path)
    unmanaged: set[str] = set()

    for candidate in sorted(candidate_dirs):
        if candidate in {"", "."}:
            continue
        candidate_path = Path(candidate)
        managed_in_dir = managed_targets_by_dir.get(candidate, [])
        # Root container directories like .github and .vscode often hold unrelated
        # repository metadata. Only scan dedicated managed subtrees for lookalikes.
        if (
            len(candidate_path.parts) == 1
            and candidate_path.name.startswith(".")
            and managed_in_dir
            and all(len(path.parts) == len(candidate_path.parts) + 1 for path in managed_in_dir)
        ):
            continue
        base_dir = workspace / candidate
        if not base_dir.exists() or not base_dir.is_dir():
            continue
        if base_dir.is_symlink():
            continue
        for file_path in sorted(path for path in base_dir.rglob("*") if path.is_file() and "__pycache__" not in path.parts):
            relative = file_path.relative_to(workspace).as_posix()
            if relative in managed_targets or relative in retired_targets:
                continue
            if relative in {".github/xanadAssistant-lock.json", ".github/xanad-assistant-lock.json", ".github/copilot-version.md"}:
                continue
            unmanaged.add(relative)

    return sorted(unmanaged)


def collect_successor_migration_files(
    workspace: Path,
    manifest: dict | None,
    lockfile_state: dict,
    legacy_version_state: dict,
) -> list[str]:
    if manifest is None:
        return []

    predecessor_package = get_predecessor_package_name(lockfile_state)
    predecessor_markers = predecessor_package is not None
    if not predecessor_markers and legacy_version_state.get("present") and not lockfile_state.get("present"):
        predecessor_markers = True
    if not predecessor_markers:
        marker_paths = [workspace / ".github" / "hooks" / "copilot-hooks.json", workspace / ".mcp.json", workspace / ".copilot" / "workspace"]
        predecessor_markers = any(path.exists() for path in marker_paths)
    if not predecessor_markers:
        return []

    managed_targets = {entry.get("target") for entry in manifest.get("managedFiles", [])}
    retired_targets = {entry.get("target") for entry in manifest.get("retiredFiles", [])}
    excluded = managed_targets | retired_targets | {
        ".github/xanadAssistant-lock.json",
        ".github/xanad-assistant-lock.json",
        ".github/copilot-version.md",
    }
    cleanup_targets: set[str] = set()

    for root in _SUCCESSOR_MIGRATION_ROOTS:
        root_path = workspace / root
        if not root_path.exists():
            continue
        if root_path.is_symlink():
            continue
        for file_path in sorted(path for path in root_path.rglob("*") if path.is_file()):
            relative = file_path.relative_to(workspace).as_posix()
            if relative not in excluded:
                cleanup_targets.add(relative)

    for relative in _SUCCESSOR_MIGRATION_FILES:
        file_path = workspace / relative
        if file_path.exists() and relative not in excluded:
            cleanup_targets.add(relative)

    return sorted(cleanup_targets)


# ── Sanitize scanner ──────────────────────────────────────────────────────────

_COPILOT_SHAPED_SUFFIXES = frozenset({
    ".agent.md",
    ".prompt.md",
    ".instructions.md",
})
_COPILOT_SHAPED_NAMES = frozenset({"SKILL.md", "copilot-instructions.md", "mcp.json"})
_MCP_JSON_ALLOWED_ROOTS = frozenset({".github", ".vscode"})
_SANITIZE_SCAN_ROOTS = frozenset({".github", ".vscode"})


def is_copilot_shaped_unmanaged_path(relative_path: str) -> bool:
    """Return True if *relative_path* looks like a Copilot-managed file.

    Rules:
    - ``*.agent.md``, ``*.prompt.md``, ``*.instructions.md`` under any path.
    - ``SKILL.md`` and ``copilot-instructions.md`` under any path.
    - ``mcp.json`` only when its first path component is ``.github`` or ``.vscode``.
    """
    p = Path(relative_path)
    name = p.name
    if any(name.endswith(suffix) for suffix in _COPILOT_SHAPED_SUFFIXES):
        return True
    if name in (_COPILOT_SHAPED_NAMES - {"mcp.json"}):
        return True
    if name == "mcp.json":
        parts = p.parts
        return len(parts) >= 2 and parts[0] in _MCP_JSON_ALLOWED_ROOTS
    return False


def collect_managed_scan_roots(policy: dict, manifest: dict | None) -> list[str]:
    """Return the set of directory roots that should be scanned for sanitize candidates.

    Derived from the policy's ``targetPathRules`` (target root names) plus any
    explicit MCP config directories from the manifest.
    """
    roots: set[str] = set(_SANITIZE_SCAN_ROOTS)
    for rule in policy.get("targetPathRules", {}).values():
        root = rule.get("targetRoot", "")
        if root:
            parts = Path(root).parts
            if parts:
                roots.add(parts[0])
    return sorted(roots)


def collect_sanitizable_unmanaged_files(
    workspace: Path,
    policy: dict,
    manifest: dict | None,
) -> list[str]:
    """Return paths of unmanaged Copilot-shaped files found under managed scan roots.

    Only files that:
    - are under a managed scan root (``.github`` or ``.vscode``),
    - pass ``is_copilot_shaped_unmanaged_path()``,
    - are not already tracked as managed or retired by the manifest,
    are returned.
    """
    if manifest is None:
        return []

    managed_targets = {entry.get("target") for entry in manifest.get("managedFiles", [])}
    retired_targets = {entry.get("target") for entry in manifest.get("retiredFiles", [])}
    excluded = managed_targets | retired_targets | {
        ".github/xanadAssistant-lock.json",
        ".github/xanad-assistant-lock.json",
        ".github/copilot-version.md",
    }

    scan_roots = collect_managed_scan_roots(policy, manifest)
    candidates: set[str] = set()

    for root in scan_roots:
        root_path = workspace / root
        if not root_path.exists() or not root_path.is_dir() or root_path.is_symlink():
            continue
        for file_path in sorted(path for path in root_path.rglob("*") if path.is_file() and "__pycache__" not in path.parts):
            relative = file_path.relative_to(workspace).as_posix()
            if relative in excluded:
                continue
            if is_copilot_shaped_unmanaged_path(relative):
                candidates.add(relative)

    return sorted(candidates)
