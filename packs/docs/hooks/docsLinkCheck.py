#!/usr/bin/env python3
"""Docs link-check MCP server — validate internal links in Markdown files.

Tools
-----
extract_links      : Return all links found in a Markdown file.
check_local_links  : Validate that file-system links resolve from a base dir.
find_markdown_files: List all .md files under a directory tree.

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

mcp = FastMCP("docsLinkCheck")

# Matches [text](url) and bare <url> — does not match reference-style links
_LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)|<(https?://[^>]+)>')


def _classify(url: str) -> str:
    """Return 'external' for http/https URLs, 'anchor' for #..., else 'local'."""
    if url.startswith(("http://", "https://")):
        return "external"
    if url.startswith("#"):
        return "anchor"
    return "local"


@mcp.tool()
def extract_links(file_path: str) -> dict:
    """Return all Markdown links found in a file.

    Args:
        file_path: Absolute or relative path to a Markdown file.

    Returns:
        {"file": str, "links": [{"text": str, "url": str, "type": str}]}
        type is one of: "local", "external", "anchor".
    """
    path = Path(file_path)
    if not path.exists():
        return {"file": str(path), "error": f"File not found: {file_path}", "links": []}

    text = path.read_text(encoding="utf-8", errors="replace")
    links = []
    for m in _LINK_RE.finditer(text):
        if m.group(3):  # bare <url>
            url = m.group(3)
            link_text = url
        else:
            link_text = m.group(1)
            url = m.group(2).split(" ")[0]  # strip optional title attribute
        links.append({"text": link_text, "url": url, "type": _classify(url)})

    return {"file": str(path), "links": links}


@mcp.tool()
def check_local_links(file_path: str, base_dir: str = "") -> dict:
    """Validate that all local (file-system) links in a Markdown file resolve.

    Anchor links (#section) and external links are reported but not validated.

    Args:
        file_path: Path to the Markdown file to check.
        base_dir: Directory to resolve relative links from.
                  Defaults to the directory containing file_path.

    Returns:
        {"file": str, "results": [{"url": str, "type": str, "exists": bool|null}]}
        exists is True/False for local links, null for external/anchor.
    """
    path = Path(file_path)
    if not path.exists():
        return {"file": str(path), "error": f"File not found: {file_path}", "results": []}

    base = Path(base_dir) if base_dir else path.parent
    raw = extract_links(file_path)
    results = []
    for link in raw["links"]:
        url = link["url"]
        kind = link["type"]
        if kind == "local":
            # Strip anchor fragment if present (e.g., ../other.md#section)
            target_url = url.split("#")[0]
            resolved = (base / target_url).resolve()
            exists: bool | None = resolved.exists()
        else:
            exists = None  # not checked
        results.append({"url": url, "type": kind, "exists": exists})

    return {"file": str(path), "results": results}


@mcp.tool()
def find_markdown_files(directory: str, max_results: int = 200) -> dict:
    """List all Markdown files under a directory tree.

    Args:
        directory: Root directory to search.
        max_results: Maximum number of files to return. Defaults to 200.

    Returns:
        {"directory": str, "files": [str], "truncated": bool}
    """
    root = Path(directory)
    if not root.exists():
        return {"directory": str(root), "error": f"Directory not found: {directory}", "files": [], "truncated": False}

    files = []
    for p in sorted(root.rglob("*.md")):
        if p.is_file():
            files.append(str(p))
            if len(files) >= max_results:
                return {"directory": str(root), "files": files, "truncated": True}

    return {"directory": str(root), "files": files, "truncated": False}


if __name__ == "__main__":
    mcp.run()
