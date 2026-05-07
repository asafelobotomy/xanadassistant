from __future__ import annotations

import hashlib
import json
import re


def sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def sha256_json(data: object) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def merge_json_objects(existing_data: dict, source_data: dict) -> dict:
    merged = dict(existing_data)
    for key, source_value in source_data.items():
        existing_value = merged.get(key)
        if isinstance(existing_value, dict) and isinstance(source_value, dict):
            merged[key] = merge_json_objects(existing_value, source_value)
        else:
            merged[key] = source_value
    return merged


def serialize_json_object(data: dict) -> bytes:
    return (json.dumps(data, indent=2) + "\n").encode("utf-8")


def extract_markdown_heading_block(markdown_text: str, heading: str) -> str | None:
    lines = markdown_text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != heading:
            continue
        end_index = len(lines)
        for candidate in range(index + 1, len(lines)):
            if lines[candidate].startswith("## "):
                end_index = candidate
                break
        block = "\n".join(lines[index:end_index]).strip()
        return block if block else None
    return None


def extract_marked_markdown_blocks(markdown_text: str, marker_name: str) -> list[str]:
    pattern = re.compile(
        rf"<!--\s*{re.escape(marker_name)}\s*-->(.*?)<!--\s*/{re.escape(marker_name)}\s*-->",
        re.DOTALL,
    )
    return [match.group(0).strip() for match in pattern.finditer(markdown_text)]


def merge_markdown_with_preserved_blocks(existing_text: str, source_text: str) -> str:
    merged_text = source_text.rstrip("\n")
    preserved_blocks: list[str] = []

    overrides_block = extract_markdown_heading_block(existing_text, "## §10 - Project-Specific Overrides")
    if overrides_block is not None:
        preserved_blocks.append(overrides_block)

    for marker_name in ("user-added", "migrated"):
        for block in extract_marked_markdown_blocks(existing_text, marker_name):
            if block not in preserved_blocks:
                preserved_blocks.append(block)

    if not preserved_blocks:
        return source_text

    for block in preserved_blocks:
        if block and block not in merged_text:
            merged_text = f"{merged_text}\n\n{block}"

    return merged_text + "\n"
