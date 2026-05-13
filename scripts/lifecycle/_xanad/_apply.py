from __future__ import annotations

import json
import re
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

from scripts.lifecycle._xanad._conditions import render_tokenized_text
from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH, LifecycleCommandError
from scripts.lifecycle._xanad._loader import load_json, load_manifest
from scripts.lifecycle._xanad._merge import (
    merge_json_objects,
    merge_markdown_with_preserved_blocks,
    serialize_json_object,
)
from scripts.lifecycle._xanad._plan_utils import expected_entry_bytes


def generate_apply_timestamps() -> tuple[str, str]:
    current = datetime.now(timezone.utc).replace(microsecond=0)
    return current.isoformat().replace("+00:00", "Z"), current.strftime("%Y-%m-%dT%H-%M-%SZ")


def materialize_apply_timestamp(value: str | None, path_timestamp: str) -> str | None:
    if value is None:
        return None
    return value.replace("<apply-timestamp>", path_timestamp)


def render_entry_bytes(package_root: Path, manifest_entry: dict, token_values: dict[str, str]) -> bytes:
    result = expected_entry_bytes(package_root, manifest_entry, token_values)
    if result is None:
        raise LifecycleCommandError(
            "apply_failure",
            "Unable to render managed file bytes for apply.",
            9,
            {"id": manifest_entry["id"], "strategy": manifest_entry.get("strategy")},
        )
    return result


_JSONC_RE = re.compile(
    r'"(?:[^"\\]|\\.)*"'   # double-quoted string — preserve
    r'|//[^\n]*'              # // line comment — remove
    r'|/\*.*?\*/',             # /* block comment */ — remove
    re.DOTALL,
)


def _strip_json_comments(text: str) -> str:
    """Strip // and /* */ comments from JSONC text without altering quoted strings."""
    def _replace(m: re.Match) -> str:
        s = m.group(0)
        return s if s.startswith('"') else ""
    return _JSONC_RE.sub(_replace, text)


def merge_json_object_file(target_path: Path, package_root: Path, manifest_entry: dict) -> None:
    source_path = package_root / manifest_entry["source"]
    if target_path.exists():
        try:
            existing_data = json.loads(_strip_json_comments(target_path.read_text(encoding="utf-8")))
            source_data = load_json(source_path)
        except json.JSONDecodeError as error:
            raise LifecycleCommandError(
                "apply_failure", "Existing JSON target could not be merged.", 9,
                {"target": str(target_path), "error": str(error)},
            ) from error
        if not isinstance(existing_data, dict) or not isinstance(source_data, dict):
            raise LifecycleCommandError(
                "apply_failure", "JSON merge targets must both be objects.", 9,
                {"target": str(target_path), "source": str(source_path)},
            )
        merged_data = merge_json_objects(existing_data, source_data)
    else:
        source_data = load_json(source_path)
        if not isinstance(source_data, dict):
            raise LifecycleCommandError(
                "apply_failure", "JSON merge source must be an object.", 9,
                {"source": str(source_path)},
            )
        merged_data = source_data

    target_path.write_bytes(serialize_json_object(merged_data))


def merge_markdown_file(
    target_path: Path, package_root: Path, manifest_entry: dict, token_values: dict[str, str] | None = None
) -> None:
    source_path = package_root / manifest_entry["source"]
    source_text = source_path.read_text(encoding="utf-8")
    rendered_text = render_tokenized_text(source_text, token_values or {})
    if target_path.exists():
        existing_text = target_path.read_text(encoding="utf-8")
        merged_text = merge_markdown_with_preserved_blocks(existing_text, rendered_text)
    else:
        merged_text = rendered_text
    target_path.write_text(merged_text, encoding="utf-8")


def build_copilot_version_summary(lockfile_contents: dict, manifest: dict | None) -> str:
    package_version = None
    if manifest is not None:
        package_version = manifest.get("packageVersion")
    if not package_version:
        package_version = "unknown"

    summary_digest = {
        "version": package_version,
        "profile": lockfile_contents.get("profile"),
        "selectedPacks": lockfile_contents.get("selectedPacks", []),
        "manifestHash": lockfile_contents.get("manifest", {}).get("hash"),
        "appliedAt": lockfile_contents.get("timestamps", {}).get("appliedAt"),
    }
    selected_packs = lockfile_contents.get("selectedPacks", [])
    packs_summary = ", ".join(selected_packs) if selected_packs else "none"

    return (
        "# xanadAssistant Installed Summary\n\n"
        f"Version: {package_version}\n"
        f"Profile: {lockfile_contents.get('profile') or 'unknown'}\n"
        f"Selected packs: {packs_summary}\n"
        f"Applied at: {lockfile_contents.get('timestamps', {}).get('appliedAt') or 'unknown'}\n"
        f"Lockfile: .github/xanadAssistant-lock.json\n\n"
        "```json\n"
        f"{json.dumps(summary_digest, indent=2)}\n"
        "```\n"
    )


def apply_chmod_rule(target_path: Path, chmod_rule: str) -> None:
    if chmod_rule != "executable":
        return
    current_mode = stat.S_IMODE(target_path.stat().st_mode)
    target_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

