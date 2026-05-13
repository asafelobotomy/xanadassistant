#!/usr/bin/env python3
"""OSS License Check MCP server — scan source files for license headers and validate SPDX expressions.

Tools
-----
scan_license_headers : Report source files that have a license or copyright header.
find_missing_headers : Report source files that are missing a license header.
validate_spdx        : Check whether a string is a recognised SPDX license expression.

All operations are local and require no network access.

Transport: stdio  |  Run: uvx --from "mcp[cli]" mcp run <this-file>
"""
from __future__ import annotations

import re
import sys
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

mcp = FastMCP("ossLicenseCheck")

# Patterns checked in the first few lines of a file to detect a license header
_LICENSE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"SPDX-License-Identifier", re.IGNORECASE),
    re.compile(r"Copyright\s+[\d(C©]", re.IGNORECASE),
    re.compile(r"Licensed under the", re.IGNORECASE),
    re.compile(r"Permission is hereby granted", re.IGNORECASE),
    re.compile(r"GNU (?:General|Lesser|Affero) Public License", re.IGNORECASE),
    re.compile(r"Mozilla Public License", re.IGNORECASE),
]

# Widely-used SPDX license identifiers (covers the vast majority of OSS use cases)
_SPDX_IDS: frozenset[str] = frozenset({
    "MIT", "Apache-2.0", "GPL-2.0-only", "GPL-2.0-or-later",
    "GPL-3.0-only", "GPL-3.0-or-later", "LGPL-2.0-only", "LGPL-2.0-or-later",
    "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later",
    "AGPL-3.0-only", "AGPL-3.0-or-later", "BSD-2-Clause", "BSD-3-Clause",
    "ISC", "MPL-2.0", "CDDL-1.0", "EPL-1.0", "EPL-2.0", "EUPL-1.2",
    "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "Unlicense", "WTFPL",
    "PSF-2.0", "Python-2.0", "Artistic-2.0", "Zlib", "BSL-1.0",
})

_DEFAULT_EXTENSIONS = [".py", ".js", ".ts", ".go", ".rb", ".java", ".c", ".cpp", ".h", ".rs"]
_IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", "vendor"}
_HEADER_LINES = 8  # how many lines from the top to check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_header(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            head = "".join(next(fh, "") for _ in range(_HEADER_LINES))
    except OSError:
        return False
    return any(pat.search(head) for pat in _LICENSE_PATTERNS)


def _source_files(root: Path, extensions: list[str]) -> list[Path]:
    ext_set = {e if e.startswith(".") else f".{e}" for e in extensions}
    result = []
    for p in root.rglob("*"):
        if any(part in _IGNORE_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix in ext_set:
            result.append(p)
    return sorted(result)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def scan_license_headers(root: str, extensions: list[str] | None = None) -> dict:
    """Report source files that have a license or copyright header.

    Args:
        root:       Directory to scan.
        extensions: File extensions to include (default: .py .js .ts .go .rb .java .c .cpp .h .rs).

    Returns:
        {"root": str, "scanned": int, "with_header": int, "files": list[str]}
    """
    r = Path(root)
    if not r.is_dir():
        return {"error": f"Not a directory: {root}"}
    files = _source_files(r, extensions or _DEFAULT_EXTENSIONS)
    found = [str(f.relative_to(r)) for f in files if _has_header(f)]
    return {"root": root, "scanned": len(files), "with_header": len(found), "files": found}


@mcp.tool()
def find_missing_headers(root: str, extensions: list[str] | None = None) -> dict:
    """Report source files that are missing a license or copyright header.

    Args:
        root:       Directory to scan.
        extensions: File extensions to include (default: .py .js .ts .go .rb .java .c .cpp .h .rs).

    Returns:
        {"root": str, "scanned": int, "missing": int, "files": list[str]}
    """
    r = Path(root)
    if not r.is_dir():
        return {"error": f"Not a directory: {root}"}
    files = _source_files(r, extensions or _DEFAULT_EXTENSIONS)
    missing = [str(f.relative_to(r)) for f in files if not _has_header(f)]
    return {"root": root, "scanned": len(files), "missing": len(missing), "files": missing}


@mcp.tool()
def validate_spdx(expression: str) -> dict:
    """Check whether a string is a recognised SPDX license expression.

    Handles simple identifiers and basic compound expressions using AND / OR.
    Does not validate complex SPDX WITH exception clauses.

    Args:
        expression: SPDX expression, e.g. "MIT", "Apache-2.0 OR MIT".

    Returns:
        {"expression": str, "valid": bool, "unrecognised": list[str]}
    """
    parts = re.split(r"\b(?:AND|OR|WITH)\b", expression, flags=re.IGNORECASE)
    unknown = [p.strip() for p in parts if p.strip() and p.strip() not in _SPDX_IDS]
    return {"expression": expression, "valid": not unknown, "unrecognised": unknown}


if __name__ == "__main__":
    mcp.run()
