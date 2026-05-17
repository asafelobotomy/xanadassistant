#!/usr/bin/env python3
"""OSS git log MCP server — structured git history for changelog generation.

Tools
-----
get_commits        : Return structured commits for a revision range.
get_tags           : List annotated and lightweight tags with dates.
get_last_tag       : Return the most recent tag name.
format_range       : Return the canonical range string from last tag to HEAD.

Transport: stdio  |  Run: uvx --from "mcp[cli]" mcp run <this-file>
"""
from __future__ import annotations

import json
import subprocess
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

mcp = FastMCP("ossGitLog")


def _run_git(*args: str, cwd: str | None = None) -> str:
    """Run a git command and return stripped stdout. Raises on non-zero exit."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


@mcp.tool()
def get_last_tag(repo_path: str = ".") -> dict:
    """Return the most recent git tag in the repository.

    Args:
        repo_path: Path to the git repository root (default: current directory).

    Returns:
        {"tag": "<tag-name>"} or {"tag": null} if no tags exist.
    """
    try:
        tag = _run_git("describe", "--tags", "--abbrev=0", cwd=repo_path)
        return {"tag": tag}
    except RuntimeError:
        return {"tag": None}


@mcp.tool()
def format_range(repo_path: str = ".") -> dict:
    """Return the canonical revision range from the last tag to HEAD.

    Args:
        repo_path: Path to the git repository root.

    Returns:
        {"range": "<last-tag>..HEAD"} or {"range": "HEAD"} if no tags exist.
    """
    result = get_last_tag(repo_path=repo_path)
    tag = result.get("tag")
    return {"range": f"{tag}..HEAD" if tag else "HEAD"}


@mcp.tool()
def get_commits(
    revision_range: str = "",
    repo_path: str = ".",
    no_merges: bool = True,
    max_count: int = 200,
) -> dict:
    """Return structured commits for a revision range.

    Each commit includes: hash (short), subject, body, author, date (ISO 8601).

    Args:
        revision_range: Git revision range, e.g. "v1.2.0..HEAD". Leave blank
            to use the range from the last tag to HEAD.
        repo_path: Path to the git repository root.
        no_merges: Exclude merge commits (default: true).
        max_count: Maximum number of commits to return (default: 200).

    Returns:
        {"commits": [{"hash": ..., "subject": ..., "body": ...,
                      "author": ..., "date": ...}, ...]}
    """
    if not revision_range:
        revision_range = format_range(repo_path=repo_path)["range"]

    sep = "\x1f"  # unit separator — safe delimiter
    rec_sep = "\x1e"  # record separator

    fmt = sep.join(["%h", "%s", "%b", "%an", "%aI"]) + rec_sep

    args = ["log", f"--pretty=format:{fmt}", f"--max-count={max_count}"]
    if no_merges:
        args.append("--no-merges")
    if revision_range:
        args.append(revision_range)

    try:
        raw = _run_git(*args, cwd=repo_path)
    except RuntimeError as exc:
        return {"error": str(exc), "commits": []}

    commits: list[dict] = []
    for record in raw.split(rec_sep):
        record = record.strip()
        if not record:
            continue
        parts = record.split(sep, 4)
        if len(parts) < 5:
            continue
        commits.append(
            {
                "hash": parts[0],
                "subject": parts[1],
                "body": parts[2].strip(),
                "author": parts[3],
                "date": parts[4],
            }
        )

    return {"commits": commits}


@mcp.tool()
def get_tags(repo_path: str = ".", max_count: int = 20) -> dict:
    """List recent git tags with their dates.

    Args:
        repo_path: Path to the git repository root.
        max_count: Maximum number of tags to return, most recent first.

    Returns:
        {"tags": [{"name": ..., "date": ..., "hash": ...}, ...]}
    """
    try:
        raw = _run_git(
            "tag",
            "--sort=-creatordate",
            f"--format=%(refname:short){chr(0x1f)}%(creatordate:iso-strict){chr(0x1f)}%(objectname:short)",
            cwd=repo_path,
        )
    except RuntimeError as exc:
        return {"error": str(exc), "tags": []}

    tags: list[dict] = []
    for line in raw.splitlines():
        parts = line.split("\x1f", 2)
        if len(parts) < 3:
            continue
        tags.append({"name": parts[0], "date": parts[1], "hash": parts[2]})
        if len(tags) >= max_count:
            break

    return {"tags": tags}


if __name__ == "__main__":  # pragma: no cover
    mcp.run(transport="stdio")
