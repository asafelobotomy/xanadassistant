#!/usr/bin/env python3
"""Lean Test Reporter MCP server — filter test output to failures only.

Tools
-----
filter_failures : Extract failures from raw test runner output with file:line context.
count_summary   : Return just the pass/fail/skip count line from test output.

Supports unittest, pytest, Jest, Mocha, and Cargo test output formats.

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

mcp = FastMCP("leanTestReporter")

# ---------------------------------------------------------------------------
# Runner detection
# ---------------------------------------------------------------------------

_RUNNER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pytest",    re.compile(r"={5,}\s*FAILURES?\s*={5,}|FAILED .+::", re.M)),
    ("unittest",  re.compile(r"^(FAIL|ERROR):\s+\w+", re.M)),
    ("jest",      re.compile(r"✕|✗|× |FAIL\s+\w", re.M)),
    ("mocha",     re.compile(r"passing|failing|\d+ (passing|failing)", re.M)),
    ("cargo",     re.compile(r"^test .+ \.\.\. FAILED$", re.M)),
]


def _detect_runner(output: str) -> str:
    for name, pat in _RUNNER_PATTERNS:
        if pat.search(output):
            return name
    return "unknown"


# ---------------------------------------------------------------------------
# Per-runner extractors
# ---------------------------------------------------------------------------

def _extract_pytest(output: str) -> tuple[list[str], str]:
    blocks: list[str] = []
    # Grab FAILURES section
    fail_section = re.search(r"={5,}\s*FAILURES?\s*={5,}(.+?)(?:={5,}|\Z)", output, re.S)
    if fail_section:
        raw = fail_section.group(1)
        for block in re.split(r"_{5,}", raw):
            block = block.strip()
            if block:
                header = block.splitlines()[0].strip("_ ") if block.splitlines() else ""
                # Find first file:line reference
                loc_match = re.search(r"(\S+\.py):(\d+)", block)
                err_match = re.search(r"^(AssertionError|E\s+.+)$", block, re.M)
                loc = f"{loc_match.group(1)}:{loc_match.group(2)}" if loc_match else "?"
                err = err_match.group(0).lstrip("E").strip() if err_match else "see output"
                blocks.append(f"FAIL  {header}\n  {loc}  {err}")
    # Summary line
    summary_match = re.search(r"\d+ (failed|passed|error).+", output)
    summary = summary_match.group(0) if summary_match else ""
    # Count totals
    counts = {k: 0 for k in ("failed", "passed", "error", "warning", "skipped")}
    for key in counts:
        m = re.search(rf"(\d+) {key}", output)
        if m:
            counts[key] = int(m.group(1))
    total = sum(counts.values())
    summary = (
        f"Ran: {total} — failed: {counts['failed']}, "
        f"passed: {counts['passed']}, skipped: {counts['skipped']}"
    )
    return blocks, summary


def _extract_unittest(output: str) -> tuple[list[str], str]:
    blocks: list[str] = []
    # Each FAIL/ERROR block
    for m in re.finditer(
        r"^(FAIL|ERROR):\s+(.+?)\n-{5,}\n(.+?)(?=\n(?:FAIL|ERROR|OK|FAILED|Ran)|\Z)",
        output, re.M | re.S
    ):
        kind, name, body = m.group(1), m.group(2), m.group(3)
        loc_match = re.search(r'File "(.+?)", line (\d+)', body)
        err_match = re.search(r'^(\w+Error|\w+Exception|AssertionError.+)$', body, re.M)
        loc = f"{loc_match.group(1)}:{loc_match.group(2)}" if loc_match else "?"
        err = err_match.group(0).strip() if err_match else "see output"
        blocks.append(f"{kind}  {name}\n  {loc}  {err}")
    # Summary
    ran_m = re.search(r"Ran (\d+) test", output)
    fail_m = re.search(r"failures=(\d+)", output)
    err_m  = re.search(r"errors=(\d+)", output)
    skip_m = re.search(r"skipped=(\d+)", output)
    total   = int(ran_m.group(1)) if ran_m else 0
    failed  = int(fail_m.group(1)) if fail_m else 0
    errors  = int(err_m.group(1))  if err_m  else 0
    skipped = int(skip_m.group(1)) if skip_m else 0
    summary = (
        f"Ran: {total} — failed: {failed + errors}, "
        f"passed: {total - failed - errors - skipped}, skipped: {skipped}"
    )
    return blocks, summary


def _extract_generic(output: str) -> tuple[list[str], str]:
    """Best-effort extraction for unknown runners."""
    blocks = []
    for line in output.splitlines():
        if re.search(r"\b(FAIL|FAILED|ERROR|ERRORS)\b", line, re.I):
            blocks.append(line.strip())
    return blocks, ""


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def filter_failures(output: str, runner: str = "auto") -> str:
    """Extract test failures from raw runner output as a compact failures-only summary.

    Args:
        output: Raw text output from a test run.
        runner: Test runner hint — 'auto' (default), 'pytest', 'unittest', 'jest',
                'mocha', or 'cargo'. Use 'auto' to detect automatically.
    """
    effective = runner if runner != "auto" else _detect_runner(output)

    if effective == "pytest":
        blocks, summary = _extract_pytest(output)
    elif effective == "unittest":
        blocks, summary = _extract_unittest(output)
    else:
        blocks, summary = _extract_generic(output)

    if not blocks:
        return count_summary(output, runner)

    body = "\n\n".join(blocks)
    return f"{body}\n\n{summary}" if summary else body


@mcp.tool()
def count_summary(output: str, runner: str = "auto") -> str:
    """Return just the pass/fail/skip count line from test output.

    Args:
        output: Raw text output from a test run.
        runner: Test runner hint — 'auto' (default), 'pytest', 'unittest', 'jest',
                'mocha', or 'cargo'.
    """
    effective = runner if runner != "auto" else _detect_runner(output)

    if effective == "pytest":
        _, summary = _extract_pytest(output)
        return summary or "No summary found in output."

    if effective == "unittest":
        _, summary = _extract_unittest(output)
        return summary or "No summary found in output."

    # Generic: find the last line matching a count pattern
    for line in reversed(output.splitlines()):
        line = line.strip()
        if re.search(r"\d+.+(pass|fail|test|spec|ok)", line, re.I):
            return line
    return "No summary found in output."


if __name__ == "__main__":  # pragma: no cover
    mcp.run(transport="stdio")
