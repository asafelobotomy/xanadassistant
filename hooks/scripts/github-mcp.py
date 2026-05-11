#!/usr/bin/env python3
"""GitHub MCP — GitHub REST API via GITHUB_TOKEN.

Provides tools for repositories, issues, pull requests, releases, Actions
workflow runs, code search, and file contents.  All operations use the
GitHub REST API — no GraphQL required for this tool set.

Authentication
--------------
Set the GITHUB_TOKEN environment variable to a Personal Access Token (classic
or fine-grained) with the scopes required for the operations you need:
  - Contents (read)    → get_repo, get_file_contents, search_code
  - Issues (read)      → list_issues, get_issue
  - Issues (write)     → create_issue_comment
  - Pull requests (read/write) → list_pull_requests, get_pull_request,
                                  create_pull_request
  - Actions (read)     → list_workflow_runs
  - Metadata (read)    → list_releases

In GitHub Codespaces, GITHUB_TOKEN is pre-populated automatically.

Transport: stdio  |  Run: uvx --from "mcp[cli]" mcp run <this-file>
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as _exc:  # pragma: no cover
    sys.stderr.write(
        "ERROR: the 'mcp' package is required but not installed.\n"
        "Install it with: pip install 'mcp[cli]'\n"
        f"Details: {_exc}\n"
    )
    sys.exit(1)

mcp = FastMCP("xanadGitHub")

_API = "https://api.github.com"


# ---------------------------------------------------------------------------
# Auth + HTTP helpers
# ---------------------------------------------------------------------------

def _token() -> str:
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if not tok:
        raise RuntimeError(
            "GITHUB_TOKEN environment variable is not set. "
            "Create a GitHub Personal Access Token and export it before starting VS Code, "
            "or set it in your shell profile."
        )
    return tok


def _req(method: str, path: str, body: dict | None = None,
         params: dict | None = None) -> Any:  # pragma: no cover
    url = f"{_API}{path}"
    if params:
        filtered = {k: v for k, v in params.items() if v is not None}
        if filtered:
            url += "?" + urllib.parse.urlencode(filtered)
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code}: {body_text}") from exc


def _get(path: str, params: dict | None = None) -> Any:  # pragma: no cover
    return _req("GET", path, params=params)


def _post(path: str, body: dict) -> Any:  # pragma: no cover
    return _req("POST", path, body=body)


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

@mcp.tool()
def get_repo(owner: str, repo: str) -> str:  # pragma: no cover
    """Return key metadata for a GitHub repository."""
    d = _get(f"/repos/{owner}/{repo}")
    return json.dumps({k: d.get(k) for k in (
        "full_name", "description", "default_branch", "stargazers_count",
        "forks_count", "open_issues_count", "license", "visibility",
        "html_url", "pushed_at",
    )}, indent=2)


@mcp.tool()
def get_file_contents(owner: str, repo: str, path: str, ref: str = "") -> str:  # pragma: no cover
    """Return the decoded text content of a file from a GitHub repository.

    Args:
        owner: Repository owner (user or org).
        repo: Repository name.
        path: File path within the repository (e.g. 'src/main.py').
        ref: Branch, tag, or commit SHA (defaults to the default branch).
    """
    params = {"ref": ref} if ref else None
    d = _get(f"/repos/{owner}/{repo}/contents/{path}", params=params)
    if d.get("encoding") == "base64":
        return base64.b64decode(d["content"]).decode("utf-8", errors="replace")
    return d.get("content", "(binary or unsupported encoding)")


@mcp.tool()
def search_code(query: str, per_page: int = 10) -> str:  # pragma: no cover
    """Search code on GitHub.

    Args:
        query: GitHub code search query (e.g. 'repo:owner/repo someFunction').
        per_page: Number of results, 1–30 (default 10).
    """
    d = _get("/search/code", {"q": query, "per_page": min(30, per_page)})
    items = d.get("items", [])
    if not items:
        return f"No code results for: {query!r}"
    lines = [f"Found {d.get('total_count', '?')} result(s):"]
    for item in items:
        lines.append(f"  {item['repository']['full_name']}: {item['path']} ({item['html_url']})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------

@mcp.tool()
def list_issues(owner: str, repo: str, state: str = "open",
                per_page: int = 20) -> str:  # pragma: no cover
    """List issues for a repository (excludes pull requests).

    Args:
        owner: Repository owner.
        repo: Repository name.
        state: 'open' (default), 'closed', or 'all'.
        per_page: Results per page, 1–50 (default 20).
    """
    items = _get(f"/repos/{owner}/{repo}/issues",
                 {"state": state, "per_page": min(50, per_page)})
    issues = [i for i in items if "pull_request" not in i]
    if not issues:
        return f"No {state} issues in {owner}/{repo}."
    return "\n".join(
        f"#{i['number']} [{i['state']}] {i['title']} ({i['html_url']})"
        for i in issues
    )


@mcp.tool()
def get_issue(owner: str, repo: str, issue_number: int) -> str:  # pragma: no cover
    """Get full details of a specific issue.

    Args:
        owner: Repository owner.
        repo: Repository name.
        issue_number: Issue number.
    """
    i = _get(f"/repos/{owner}/{repo}/issues/{issue_number}")
    return json.dumps({k: i.get(k) for k in (
        "number", "title", "state", "body", "html_url",
        "user", "labels", "assignees", "created_at", "updated_at",
    )}, indent=2)


@mcp.tool()
def create_issue_comment(owner: str, repo: str,
                         issue_number: int, body: str) -> str:  # pragma: no cover
    """Post a comment on an issue or pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        issue_number: Issue or PR number.
        body: Comment text (Markdown supported).
    """
    r = _post(f"/repos/{owner}/{repo}/issues/{issue_number}/comments", {"body": body})
    return f"Comment created: {r.get('html_url')}"


# ---------------------------------------------------------------------------
# Pull requests
# ---------------------------------------------------------------------------

@mcp.tool()
def list_pull_requests(owner: str, repo: str, state: str = "open",
                       per_page: int = 20) -> str:  # pragma: no cover
    """List pull requests for a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        state: 'open' (default), 'closed', or 'all'.
        per_page: Results per page, 1–50 (default 20).
    """
    items = _get(f"/repos/{owner}/{repo}/pulls",
                 {"state": state, "per_page": min(50, per_page)})
    if not items:
        return f"No {state} pull requests in {owner}/{repo}."
    return "\n".join(
        f"#{i['number']} [{i['state']}] {i['title']} "
        f"({i['head']['ref']}→{i['base']['ref']}) {i['html_url']}"
        for i in items
    )


@mcp.tool()
def get_pull_request(owner: str, repo: str, pull_number: int) -> str:  # pragma: no cover
    """Get full details of a specific pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pull_number: Pull request number.
    """
    p = _get(f"/repos/{owner}/{repo}/pulls/{pull_number}")
    return json.dumps({k: p.get(k) for k in (
        "number", "title", "state", "body", "html_url", "draft",
        "head", "base", "user", "mergeable", "created_at", "updated_at",
    )}, indent=2)


@mcp.tool()
def create_pull_request(owner: str, repo: str, title: str, head: str,
                        base: str, body: str = "",
                        draft: bool = False) -> str:  # pragma: no cover
    """Create a pull request.

    Args:
        owner: Repository owner.
        repo: Repository name.
        title: PR title.
        head: Branch containing the changes (e.g. 'my-feature').
        base: Branch to merge into (e.g. 'main').
        body: PR description body (Markdown).
        draft: When True, creates as a draft PR.
    """
    r = _post(f"/repos/{owner}/{repo}/pulls",
              {"title": title, "head": head, "base": base,
               "body": body, "draft": draft})
    return f"Pull request created: #{r['number']} {r['html_url']}"


# ---------------------------------------------------------------------------
# Releases
# ---------------------------------------------------------------------------

@mcp.tool()
def list_releases(owner: str, repo: str, per_page: int = 10) -> str:  # pragma: no cover
    """List releases for a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        per_page: Results per page, 1–30 (default 10).
    """
    items = _get(f"/repos/{owner}/{repo}/releases", {"per_page": min(30, per_page)})
    if not items:
        return f"No releases found for {owner}/{repo}."
    return "\n".join(
        f"{r['tag_name']} — {r['name']} "
        f"({'draft' if r['draft'] else 'pre-release' if r['prerelease'] else 'stable'}) "
        f"{r.get('published_at', r.get('created_at', '?'))}"
        for r in items
    )


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@mcp.tool()
def list_workflow_runs(owner: str, repo: str, workflow_id: str = "",
                       status: str = "", per_page: int = 10) -> str:  # pragma: no cover
    """List recent workflow runs for a repository.

    Args:
        owner: Repository owner.
        repo: Repository name.
        workflow_id: Workflow filename (e.g. 'ci.yml') or numeric ID.
                     Omit to list runs across all workflows.
        status: Filter — 'completed', 'in_progress', 'queued', 'waiting',
                'requested', or 'pending'. Omit for all statuses.
        per_page: Results per page, 1–50 (default 10).
    """
    path = f"/repos/{owner}/{repo}/actions"
    path += f"/workflows/{workflow_id}/runs" if workflow_id else "/runs"
    params: dict = {"per_page": min(50, per_page)}
    if status:
        params["status"] = status
    d = _get(path, params)
    runs = d.get("workflow_runs", [])
    if not runs:
        return "No workflow runs found."
    return "\n".join(
        f"#{r['id']} {r['name']} [{r['status']}/{r.get('conclusion', '—')}] "
        f"{r['head_branch']} {r['created_at']} {r['html_url']}"
        for r in runs
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    mcp.run()
