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
    pack_data_cache: dict[str, dict] = {}
    for source in sources:
        if not source.is_file():
            continue
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        pack_data_cache[source.parent.name] = data
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                tokens["{{" + key + "}}"] = value

    if resolved_token_conflicts:
        for raw_key, winning_pack in resolved_token_conflicts.items():
            marker = "{{" + raw_key + "}}"
            cached = pack_data_cache.get(winning_pack, {})
            if raw_key in cached and isinstance(cached[raw_key], str):
                tokens[marker] = cached[raw_key]

    return tokens
