#!/usr/bin/env python3
"""Lean Context Budget MCP server — context compression and token estimation utilities.

Tools
-----
estimate_tokens  : Approximate token count for a text string.
compress_lines   : Truncate text to a maximum line count with an omission marker.
summarize_diff   : Compact summary of a unified diff (files, additions, deletions).

All operations are local and require no network access.

Transport: stdio  |  Run: uvx --from "mcp[cli]" mcp run <this-file>
"""
from __future__ import annotations

import re
import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as _exc:  # pragma: no cover
    sys.stderr.write(
        "ERROR: the 'mcp' package is required but not installed.\n"
        "Install it with: pip install 'mcp[cli]'\n"
        f"Details: {_exc}\n"
    )
    sys.exit(1)

mcp = FastMCP("leanContextBudget")

# Rough empirical ratio: ~4 characters per token for English/code.
_CHARS_PER_TOKEN = 4


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def estimate_tokens(text: str) -> dict:
    """Approximate the token count for a text string using a character-ratio heuristic.

    Returns a dict with:
      - chars:         character count
      - tokens_approx: estimated token count (chars / 4)
      - pressure:      'low' (<2000), 'medium' (2000–8000), 'high' (>8000)
      - note:          reminder that this is an approximation

    Args:
        text: The text to measure.
    """
    chars = len(text)
    tokens = max(1, chars // _CHARS_PER_TOKEN)
    if tokens < 2000:
        pressure = "low"
    elif tokens < 8000:
        pressure = "medium"
    else:
        pressure = "high"
    return {
        "chars": chars,
        "tokens_approx": tokens,
        "pressure": pressure,
        "note": "Approximation only — actual token count depends on the model's tokenizer.",
    }


@mcp.tool()
def compress_lines(text: str, max_lines: int = 50, keep: str = "tail") -> str:
    """Truncate text to a maximum line count, inserting an omission marker.

    Args:
        text:      The text to compress.
        max_lines: Maximum number of lines to retain (default 50).
        keep:      Which portion to keep — 'head' (first N lines), 'tail' (last N lines),
                   or 'middle' (N/2 from start and N/2 from end with gap marker).
    """
    lines = text.splitlines()
    total = len(lines)
    if total <= max_lines:
        return text

    omitted = total - max_lines

    if keep == "head":
        kept = lines[:max_lines]
        return "\n".join(kept) + f"\n[... {omitted} line(s) omitted ...]"

    if keep == "tail":
        kept = lines[-max_lines:]
        return f"[... {omitted} line(s) omitted ...]\n" + "\n".join(kept)

    # middle: split budget evenly
    half = max_lines // 2
    head_lines = lines[:half]
    tail_lines = lines[-(max_lines - half):]
    gap = total - half - (max_lines - half)
    return (
        "\n".join(head_lines)
        + f"\n[... {gap} line(s) omitted ...]\n"
        + "\n".join(tail_lines)
    )


@mcp.tool()
def summarize_diff(diff_text: str) -> str:
    """Produce a compact summary of a unified diff: files changed with addition/deletion counts.

    Args:
        diff_text: Unified diff text (output of git diff, diff -u, etc.).
    """
    if not diff_text.strip():
        return "Empty diff."

    file_stats: dict[str, dict[str, int]] = {}
    current_file: str | None = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git ") or line.startswith("--- ") or line.startswith("+++ "):
            # +++ b/path gives us the new filename; strip the b/ prefix
            if line.startswith("+++ "):
                path = line[4:].strip()
                if path.startswith("b/"):
                    path = path[2:]
                if path != "/dev/null":
                    current_file = path
                    file_stats.setdefault(current_file, {"add": 0, "del": 0})
            continue
        if current_file is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            file_stats[current_file]["add"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            file_stats[current_file]["del"] += 1

    if not file_stats:
        return "No file changes detected in diff."

    total_add = sum(s["add"] for s in file_stats.values())
    total_del = sum(s["del"] for s in file_stats.values())
    lines_out: list[str] = []
    for path, stats in sorted(file_stats.items()):
        lines_out.append(f"  {path}  +{stats['add']} -{stats['del']}")

    lines_out.append(
        f"\n{len(file_stats)} file(s) changed — +{total_add} additions, -{total_del} deletions"
    )
    return "\n".join(lines_out)


if __name__ == "__main__":  # pragma: no cover
    mcp.run(transport="stdio")
