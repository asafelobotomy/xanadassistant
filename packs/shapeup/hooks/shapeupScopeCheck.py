#!/usr/bin/env python3
"""Shape Up scope-check MCP server — find unscoped TODOs, scope creep signals, and open questions.

Tools
-----
find_unscoped_todos  : Find TODO/FIXME/HACK comments without associated issue references.
check_scope_creep    : Detect files modified outside a declared scope list.
list_open_questions  : Extract open-question markers from Markdown and plain-text docs.
check_appetite       : Check whether a cycle is within its Shape Up appetite budget.

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

mcp = FastMCP("shapeupScopeCheck")

# Comment markers that indicate deferred or unscoped work
_TODO_PATTERN = re.compile(
    r"(?:#|//|/\*|<!--)\s*(TODO|FIXME|HACK|XXX)\b(.*)$",
    re.IGNORECASE | re.MULTILINE,
)

# Issue reference patterns — a TODO is "scoped" if it references one of these
_ISSUE_REF_PATTERN = re.compile(
    r"(?:#\d+|https?://[^\s]+/issues/\d+|[A-Z]+-\d+)",
    re.IGNORECASE,
)

# Open-question markers in Markdown
_QUESTION_PATTERN = re.compile(
    r"(?:^|\n)\s*[-*]\s*(?:open\s+question|tbd|to\s+be\s+decided|unclear|TBD|TODO:?\s+decide)[:\s](.+?)(?=\n|$)",
    re.IGNORECASE,
)

# File types to scan for TODO/FIXME
_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rb", ".java", ".kt",
    ".cs", ".cpp", ".c", ".h", ".rs", ".swift", ".sh", ".bash",
}

# File types to scan for open questions
_DOC_EXTENSIONS = {".md", ".txt", ".rst", ".adoc"}

_IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll", ".so", ".dylib",
}


def _walk_files(root: Path, extensions: set[str]) -> list[Path]:
    """Yield files under root matching extensions, skipping ignored directories."""
    result = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _IGNORE_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in extensions:
            result.append(path)
    return result


@mcp.tool()
def find_unscoped_todos(directory: str) -> dict:
    """Find TODO/FIXME/HACK comments that have no associated issue reference.

    A TODO is considered scoped if it contains a GitHub issue number (#123),
    a Jira-style ticket (ABC-123), or a full issue URL.

    Args:
        directory: Directory to scan.

    Returns:
        {"directory": str, "findings": [{"file": str, "line": int, "marker": str,
         "text": str}], "count": int}
    """
    root = Path(directory)
    if not root.exists():
        return {"directory": str(root), "error": f"Not found: {directory}", "findings": [], "count": 0}

    findings: list[dict] = []

    for path in _walk_files(root, _CODE_EXTENSIONS | _DOC_EXTENSIONS):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _TODO_PATTERN.finditer(content):
            marker = match.group(1).upper()
            text = (match.group(2) or "").strip()
            full_text = f"{marker} {text}"
            if _ISSUE_REF_PATTERN.search(full_text):
                continue  # scoped — has an issue ref
            lineno = content[: match.start()].count("\n") + 1
            findings.append({
                "file": str(path),
                "line": lineno,
                "marker": marker,
                "text": text[:120],
            })

    return {"directory": str(root), "findings": findings, "count": len(findings)}


@mcp.tool()
def check_scope_creep(directory: str, scope_paths: list[str]) -> dict:
    """Detect files present in the directory that are outside the declared scope list.

    Scope paths are relative path prefixes (e.g. ["src/feature-x", "tests/test_feature_x.py"]).
    Any file that does not fall under at least one of the declared scope paths is flagged.
    Dotfiles, config files, and common root files (README, LICENSE) are excluded from flagging.

    Args:
        directory: Directory to check.
        scope_paths: List of relative path prefixes that define the expected scope.

    Returns:
        {"directory": str, "scope_paths": list, "outside_scope": [str], "count": int}
    """
    root = Path(directory)
    if not root.exists():
        return {"directory": str(root), "error": f"Not found: {directory}", "outside_scope": [], "count": 0}

    if not scope_paths:
        return {
            "directory": str(root),
            "scope_paths": [],
            "outside_scope": [],
            "count": 0,
            "note": "No scope paths provided — nothing to check.",
        }

    _COMMON_ROOT_FILES = {"README.md", "LICENSE", "LICENSE.md", "CHANGELOG.md", ".gitignore", ".gitattributes"}

    outside: list[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _IGNORE_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in _BINARY_EXTENSIONS:
            continue
        rel = path.relative_to(root)
        rel_str = str(rel)
        # Skip common root-level files
        if rel.parent == Path(".") and rel.name in _COMMON_ROOT_FILES:
            continue
        # Skip dotfiles
        if any(part.startswith(".") for part in rel.parts):
            continue
        in_scope = any(
            rel_str == sp or rel_str.startswith(sp.rstrip("/") + "/")
            for sp in scope_paths
        )
        if not in_scope:
            outside.append(rel_str)

    return {
        "directory": str(root),
        "scope_paths": scope_paths,
        "outside_scope": outside,
        "count": len(outside),
    }


@mcp.tool()
def list_open_questions(directory: str) -> dict:
    """Extract open-question markers from Markdown and plain-text documentation files.

    Looks for list items or paragraphs marked with: "Open question", "TBD",
    "To be decided", "Unclear", or "TODO: decide".

    Args:
        directory: Directory to scan.

    Returns:
        {"directory": str, "questions": [{"file": str, "line": int, "text": str}], "count": int}
    """
    root = Path(directory)
    if not root.exists():
        return {"directory": str(root), "error": f"Not found: {directory}", "questions": [], "count": 0}

    questions: list[dict] = []

    for path in _walk_files(root, _DOC_EXTENSIONS):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = content.splitlines()
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            # Match list items or inline markers
            if re.search(
                r"(?:open\s+question|tbd|to\s+be\s+decided|unclear)[:\s]",
                stripped,
                re.IGNORECASE,
            ):
                questions.append({
                    "file": str(path),
                    "line": lineno,
                    "text": stripped[:140],
                })

    return {"directory": str(root), "questions": questions, "count": len(questions)}


@mcp.tool()
def check_appetite(start_date: str, budget_weeks: int = 6) -> dict:
    """Check whether a Shape Up cycle is within its appetite.

    Args:
        start_date:   ISO 8601 date string (YYYY-MM-DD) when the cycle started.
        budget_weeks: Appetite in weeks (default 6 for a standard Shape Up cycle).

    Returns:
        {"start_date": str, "today": str, "budget_weeks": int, "budget_days": int,
         "elapsed_days": int, "remaining_days": int, "over_budget": bool,
         "percent_complete": float}
    """
    from datetime import date as _date
    try:
        start = _date.fromisoformat(start_date)
    except ValueError:
        return {"error": f"Invalid date: {start_date!r} — expected YYYY-MM-DD."}
    today = _date.today()
    budget_days = budget_weeks * 7
    elapsed = (today - start).days
    remaining = budget_days - elapsed
    return {
        "start_date": start_date,
        "today": today.isoformat(),
        "budget_weeks": budget_weeks,
        "budget_days": budget_days,
        "elapsed_days": elapsed,
        "remaining_days": remaining,
        "over_budget": remaining < 0,
        "percent_complete": round(min(elapsed / budget_days * 100, 100), 1) if budget_days else 0.0,
    }


if __name__ == "__main__":
    mcp.run()
