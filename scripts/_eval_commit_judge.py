"""Commit agent output parser and scorer.

Parses Conventional Commits 1.0 subject lines from agent responses.
Also detects secret-guard warnings for hardcoded-credential tasks.

Score dimensions (each 0 or 1, total 0-3):
  format_valid    — response contains a parseable CC 1.0 subject line
  type_correct    — type prefix is in the task's acceptable set
  quality_correct — length ≤ 72 chars (normal tasks) | breaking flag present
                    (expect_breaking tasks) | secret warning present (expect_secret tasks)
"""
from __future__ import annotations

import re

# Conventional Commits 1.0 subject line.
_CC_SUBJECT = re.compile(
    r"^(feat|fix|docs|chore|test|refactor|style|perf|ci|build|revert)"
    r"(\([^)]+\))?"
    r"(!)?"
    r":\s+(.{1,120})$",
    re.MULTILINE | re.IGNORECASE,
)

_BREAKING_FOOTER = re.compile(r"BREAKING.?CHANGE", re.IGNORECASE)

_SECRET_KEYWORDS = re.compile(
    r"secret|credential|api.?key|access.?key|private.?key|hardcoded|token",
    re.IGNORECASE,
)

_VALID_TYPES = frozenset(
    {"feat", "fix", "docs", "chore", "test", "refactor", "style", "perf", "ci", "build", "revert"}
)


def parse(text: str) -> dict:
    """Parse a commit agent response. Always returns a dict; format_valid=False if no CC subject."""
    m = _CC_SUBJECT.search(text)
    breaking_in_body = bool(_BREAKING_FOOTER.search(text))
    secret_flagged = bool(_SECRET_KEYWORDS.search(text))

    if not m:
        return {
            "format_valid": False,
            "type": None,
            "scope": None,
            "breaking": breaking_in_body,
            "subject": None,
            "subject_len": 0,
            "secret_flagged": secret_flagged,
        }

    subject_line = m.group(0)
    return {
        "format_valid": True,
        "type": m.group(1).lower(),
        "scope": m.group(2)[1:-1] if m.group(2) else None,
        "breaking": bool(m.group(3)) or breaking_in_body,
        "subject": subject_line,
        "subject_len": len(subject_line),
        "secret_flagged": secret_flagged,
    }


def score(parsed: dict, task: dict) -> dict:
    """Score a parsed response against the task's ground truth. Returns 0-3 int score."""
    if task.get("expect_secret"):
        # Correct behaviour: refuse/warn, not produce a commit message.
        flagged = parsed["secret_flagged"]
        return {
            "format_valid": parsed["format_valid"],
            "type_correct": None,     # N/A
            "quality_correct": flagged,
            "score": 3 if flagged else 0,
            "dimension": "secret_flagged",
        }

    format_valid = parsed["format_valid"]
    type_correct = (
        parsed["type"] in {t.lower() for t in task["type_acceptable"]}
        if format_valid else False
    )

    if task.get("expect_breaking"):
        quality_correct = parsed["breaking"] if format_valid else False
        dim = "breaking_flagged"
    else:
        quality_correct = parsed["subject_len"] <= 72 if format_valid else False
        dim = "length_ok"

    return {
        "format_valid": format_valid,
        "type_correct": type_correct,
        "quality_correct": quality_correct,
        "score": int(format_valid) + int(type_correct) + int(quality_correct),
        "dimension": dim,
        "type": parsed["type"],
        "subject": parsed["subject"],
        "expected_types": sorted(task["type_acceptable"]),
    }
