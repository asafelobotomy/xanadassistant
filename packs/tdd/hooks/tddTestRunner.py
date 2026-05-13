#!/usr/bin/env python3
"""TDD Test Runner MCP server — parse test output and track Red-Green-Refactor cycle state.

Tools
-----
parse_test_output    : Extract pass/fail counts and first failure from pytest/unittest output.
parse_coverage_xml   : Read a Cobertura coverage.xml and return overall coverage percentage.
summarize_cycle_state: Classify output as 'red', 'green', or 'unknown' for cycle tracking.

All operations are local and require no network access.

Transport: stdio  |  Run: uvx --from "mcp[cli]" mcp run <this-file>
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as _exc:  # pragma: no cover
    sys.stderr.write(
        "ERROR: the 'mcp' package is required but not installed.\n"
        "Install it with: pip install 'mcp[cli]'\n"
        f"Details: {_exc}\n"
    )
    sys.exit(1)

mcp = FastMCP("tddTestRunner")

# pytest: "N passed", "M failed", "K errors"
_PYTEST_COUNT = re.compile(
    r"(?P<passed>\d+)\s+passed|(?P<failed>\d+)\s+failed|(?P<error>\d+)\s+error",
    re.IGNORECASE,
)
# pytest first failure line: "FAILED path::name - AssertionError: ..."
_PYTEST_FAIL = re.compile(r"^FAILED\s+(.+?)\s+-\s+(.+)$", re.MULTILINE)
# unittest: "Ran N tests in Xs"
_UNITTEST_RAN = re.compile(r"Ran\s+(\d+)\s+tests", re.IGNORECASE)
# unittest: "OK" or "FAILED (failures=X, errors=Y)"
_UNITTEST_RESULT = re.compile(r"^(OK|FAILED)\s*(?:\((.+)\))?$", re.MULTILINE)
# unittest first failure: "FAIL: test_name (module.Class)"
_UNITTEST_FAIL = re.compile(r"^(?:FAIL|ERROR):\s+(\S+)", re.MULTILINE)


@mcp.tool()
def parse_test_output(text: str) -> dict:
    """Extract pass/fail counts and the first failure from pytest or unittest output.

    Args:
        text: Raw stdout from a test run.

    Returns:
        {"passed": int, "failed": int, "errors": int, "total": int,
         "first_failure": str | None, "format": "pytest" | "unittest" | "unknown"}
    """
    passed = failed = errors = 0
    first_failure: str | None = None
    fmt = "unknown"

    # pytest
    if re.search(r"\d+\s+(?:passed|failed)", text, re.IGNORECASE):
        for m in _PYTEST_COUNT.finditer(text):
            if m.group("passed"):
                passed += int(m.group("passed"))
            if m.group("failed"):
                failed += int(m.group("failed"))
            if m.group("error"):
                errors += int(m.group("error"))
        fm = _PYTEST_FAIL.search(text)
        if fm:
            first_failure = f"{fm.group(1)}: {fm.group(2)}"
        fmt = "pytest"

    # unittest (may override pytest counts if both appear)
    ran_m = _UNITTEST_RAN.search(text)
    if ran_m:
        fmt = "unittest"
        total = int(ran_m.group(1))
        result_m = _UNITTEST_RESULT.search(text)
        if result_m:
            if result_m.group(1) == "OK":
                passed, failed, errors = total, 0, 0
            else:
                failed = errors = 0
                for part in (result_m.group(2) or "").split(","):
                    part = part.strip()
                    if part.startswith("failures="):
                        failed = int(part[9:])
                    elif part.startswith("errors="):
                        errors = int(part[7:])
                passed = total - failed - errors
        fm = _UNITTEST_FAIL.search(text)
        if fm:
            first_failure = fm.group(1)

    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total": passed + failed + errors,
        "first_failure": first_failure,
        "format": fmt,
    }


@mcp.tool()
def parse_coverage_xml(path: str) -> dict:
    """Parse a Cobertura coverage.xml file and return a coverage summary.

    Args:
        path: Path to coverage.xml produced by coverage.py or pytest-cov.

    Returns:
        {"line_rate": float, "percent_covered": float,
         "lines_valid": int, "lines_covered": int, "zero_coverage_files": list[str]}
    """
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}
    try:
        root = ET.parse(str(p)).getroot()
    except ET.ParseError as exc:
        return {"error": f"XML parse error: {exc}"}

    line_rate = float(root.get("line-rate", 0))
    lines_valid = int(root.get("lines-valid", 0))
    lines_covered = int(root.get("lines-covered", 0))
    zero_cov = [
        cls.get("filename", "unknown")
        for cls in root.iter("class")
        if float(cls.get("line-rate", 1)) == 0.0
    ]
    return {
        "line_rate": round(line_rate, 4),
        "percent_covered": round(line_rate * 100, 1),
        "lines_valid": lines_valid,
        "lines_covered": lines_covered,
        "zero_coverage_files": zero_cov[:20],
    }


@mcp.tool()
def summarize_cycle_state(test_output: str) -> dict:
    """Classify test output as 'red', 'green', or 'unknown' for TDD cycle tracking.

    Args:
        test_output: Raw stdout from a test run.

    Returns:
        {"state": "red" | "green" | "unknown", "reason": str}
    """
    parsed = parse_test_output(test_output)
    if parsed["failed"] > 0 or parsed["errors"] > 0:
        reason = f"{parsed['failed']} failing, {parsed['errors']} error(s)."
        if parsed["first_failure"]:
            reason += f" First: {parsed['first_failure']}"
        return {"state": "red", "reason": reason}
    if parsed["passed"] > 0:
        return {"state": "green", "reason": f"{parsed['passed']} test(s) passing, 0 failing."}
    return {"state": "unknown", "reason": "Could not detect test runner output format."}


if __name__ == "__main__":  # pragma: no cover
    mcp.run(transport="stdio")
