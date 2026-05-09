"""Pure utility helpers for manifest generation.

These functions have no side effects and no dependencies on policy structure.
They are separated to keep generate_manifest.py under the project LOC limit.
"""

from __future__ import annotations

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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_registry(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as file_handle:
        return json.load(file_handle)


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
    for file_path in sorted(path for path in base_path.rglob("*") if path.is_file() and "__pycache__" not in path.parts):
        yield file_path, file_path.relative_to(base_path)


def target_for_entry(target_root: str, path_pattern: str | None, relative_path: Path, source_kind: str) -> str:
    if source_kind == "file" and path_pattern:
        return normalize_relpath(Path(target_root) / path_pattern)
    return normalize_relpath(Path(target_root) / relative_path)


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


def write_manifest(path: Path, manifest: dict) -> None:
    import json as _json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
