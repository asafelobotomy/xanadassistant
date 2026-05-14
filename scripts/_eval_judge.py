"""Triage output parser and scorer.

Parses the canonical triage output format:
    Tier: <tier>
    Scope: <one-line description>
    Approach: <recommended path>
    Blockers: <none | specific missing info>

Score dimensions (each 0 or 1):
    format_valid   — response contains the required four-field structure
    tier_correct   — Tier value is in the task's acceptable set
    blocker_correct — Blockers field is non-empty iff the task expects a blocker
"""
from __future__ import annotations

import re

# Matches the four required fields; tolerates code-block wrapping and trailing text.
_PATTERN = re.compile(
    r"Tier:\s*(\w+)[^\n]*\n"
    r"Scope:\s*([^\n]+)\n"
    r"Approach:\s*([^\n]+)\n"
    r"Blockers:\s*([^\n]+)",
    re.IGNORECASE,
)

_BLOCKERS_NONE = frozenset({"none", "n/a", "none.", "n/a."})


def parse(text: str) -> dict | None:
    """Parse triage output text. Returns field dict or None if format invalid."""
    m = _PATTERN.search(text)
    if not m:
        return None
    return {
        "tier": m.group(1).strip().capitalize(),
        "scope": m.group(2).strip(),
        "approach": m.group(3).strip(),
        "blockers": m.group(4).strip().rstrip("`").strip(),
    }


def score(parsed: dict | None, task: dict) -> dict:
    """Score a parsed response against a task's ground truth.

    Returns a dict with boolean dimensions and an integer score 0-3.
    """
    if parsed is None:
        return {
            "format_valid": False,
            "tier_correct": False,
            "blocker_correct": False,
            "score": 0,
        }

    tier = parsed["tier"]
    tier_correct = tier in task["tier_acceptable"]

    has_blocker = parsed["blockers"].lower().strip(".") not in _BLOCKERS_NONE
    blocker_correct = has_blocker if task["expect_blockers"] else not has_blocker

    return {
        "format_valid": True,
        "tier_correct": tier_correct,
        "blocker_correct": blocker_correct,
        "score": int(tier_correct) + int(blocker_correct) + 1,  # +1 for format
        "tier": tier,
        "expected_tiers": sorted(task["tier_acceptable"]),
    }
