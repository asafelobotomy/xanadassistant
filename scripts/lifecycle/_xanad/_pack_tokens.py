from __future__ import annotations

import json
from pathlib import Path


def load_pack_tokens(
    package_root: Path,
    selected_packs: list[str],
    resolved_token_conflicts: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Return resolved pack token values keyed by ``{{token-name}}`` marker strings.

    Loads core defaults from ``packs/core/tokens.json``, then applies overrides
    from each selected pack's ``tokens.json`` in order.  A core or pack token
    file that is absent or malformed is silently skipped — partial coverage is
    valid and results in no tokens from that source.

    When *resolved_token_conflicts* is provided (mapping raw token name to the
    winning pack ID), those explicit winners override whatever sequential loading
    order produced, ensuring deterministic output after conflict resolution.
    """
    sources = [package_root / "packs" / "core" / "tokens.json"] + [
        package_root / "packs" / pack_name / "tokens.json"
        for pack_name in (selected_packs or [])
    ]

    tokens: dict[str, str] = {}
    for source in sources:
        if not source.is_file():
            continue
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                tokens["{{" + key + "}}"] = value

    if resolved_token_conflicts:
        for raw_key, winning_pack in resolved_token_conflicts.items():
            marker = "{{" + raw_key + "}}"
            pack_file = package_root / "packs" / winning_pack / "tokens.json"
            if not pack_file.is_file():
                continue
            try:
                data = json.loads(pack_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(data, dict) and raw_key in data and isinstance(data[raw_key], str):
                tokens[marker] = data[raw_key]

    return tokens
