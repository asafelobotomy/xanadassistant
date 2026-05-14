"""Debugger agent output parser and scorer.

Scoring dimensions (each 0 or 1, total 0-3):
  cause_identified  — response names the root cause concept (keyword match)
  fix_prescribed    — response proposes the minimal fix (keyword match)
  focused           — response does NOT drift into the red-herring code element
                      (scope_creep_keywords absent from response)

Tasks include a non-buggy function with a visible quality issue (red herring).
A bare LLM tends to mention it; the Debugger agent with scope-discipline should not.
"""
from __future__ import annotations

import re


def parse(text: str) -> dict:
    """Extract text-level features from a debugger response."""
    return {
        "text": text,
        "word_count": len(text.split()),
        "has_code_fence": "```" in text,
        "has_diagnosis_marker": bool(
            re.search(
                r"\b(root cause|cause:|issue:|the (?:bug|problem|error)|fix:|minimal fix|fix is)\b",
                text,
                re.IGNORECASE,
            )
        ),
    }


def score(parsed: dict, task: dict) -> dict:
    """Score a parsed debugger response against the task's ground truth.

    Each dimension scores 0 or 1; total is 0-3.
    """
    text = parsed["text"].lower()

    cause_found = any(kw.lower() in text for kw in task["cause_keywords"])
    fix_found   = any(kw.lower() in text for kw in task["fix_keywords"])
    # focused = True when NONE of the red-herring keywords appear
    focused     = not any(kw.lower() in text for kw in task["scope_creep_keywords"])

    total = int(cause_found) + int(fix_found) + int(focused)
    return {
        "cause_identified": cause_found,
        "fix_prescribed":   fix_found,
        "focused":          focused,
        "score": total,
    }
