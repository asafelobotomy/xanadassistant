#!/usr/bin/env python3
"""LOC gate — enforces the default 250-warning / 400-hard-limit per-file policy.

Usage:
    python3 scripts/check_loc.py [--hard-only] [file ...]

Without file arguments, scans the whole repo (respecting .gitignore via git ls-files).
Exit codes:
    0  All files within limits.
    1  One or more files exceed their hard limit.

Files above their warning threshold but at or below their hard limit emit warnings but do
not fail.  Per-file hard-limit overrides are documented in HARD_LIMIT_OVERRIDES.

Scoped to: *.py, *.md, *.sh files that are tracked by git (or provided explicitly).
JSON / schema / lock files are excluded — they are data, not source.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

WARN_LIMIT = 250
HARD_LIMIT = 400
REPO_ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {".py", ".md", ".sh"}
WARN_LIMIT_OVERRIDES = {
    # ── Agent surface files ───────────────────────────────────────────────────────
    # Agent definitions are long-form instruction documents; they grow with features.
    "agents/xanadLifecycle.agent.md": 370,

    # ── Top-level project docs ─────────────────────────────────────────────────────
    "README.md": 330,
    "docs/archive/memory-mcp.md": 300,

    # ── Consumer MCP scripts (single-file delivery) ───────────────────────────────
    # Consumer workspaces receive these MCP servers as single files, so they need a little
    # more room than the default warning budget while still honoring the hard limit.
    "mcp/scripts/sequentialThinkingMcp.py": 260,
    "mcp/scripts/memoryMcp.py": 600,
    "mcp/scripts/webMcp.py": 450,
    "mcp/scripts/xanadWorkspaceMcp.py": 380,
    "mcp/scripts/gitMcp.py": 450,
    "mcp/scripts/githubMcp.py": 450,
    "mcp/scripts/_memory_mcp_shared.py": 310,
    # ── Managed copies (.github/) — mirrors of the above; same ceilings apply ─────
    ".github/mcp/scripts/sequentialThinkingMcp.py": 260,
    ".github/mcp/scripts/memoryMcp.py": 600,
    ".github/mcp/scripts/webMcp.py": 450,
    ".github/mcp/scripts/xanadWorkspaceMcp.py": 380,
    ".github/mcp/scripts/gitMcp.py": 450,
    ".github/mcp/scripts/githubMcp.py": 450,
    ".github/mcp/scripts/_memory_mcp_shared.py": 310,

    # ── Pack MCP scripts (consumer-facing single-file scripts) ────────────────────
    "packs/secure/mcp/secureOsv.py": 300,
    "packs/shapeup/mcp/shapeupScopeCheck.py": 300,

    # ── Lifecycle engine submodules ───────────────────────────────────────────────
    # Each submodule is intentionally scoped; these grew slightly beyond 250 while
    # remaining well under the hard limit.
    "scripts/lifecycle/_xanad/_apply_executor.py": 350,
    "scripts/lifecycle/_xanad/_execute_apply_compat.py": 320,
    "scripts/lifecycle/_xanad/_interview.py": 300,
    "scripts/lifecycle/_xanad/_main.py": 310,
    "scripts/lifecycle/_xanad/_plan_b.py": 310,

    "scripts/lifecycle/generate_manifest.py": 310,

    # ── Lifecycle tests ────────────────────────────────────────────────────────────
    "tests/lifecycle/test_apply_contracts.py": 400,
    "tests/lifecycle/test_apply_executor.py": 330,
    "tests/lifecycle/test_health_check.py": 260,
    "tests/lifecycle/test_main_dispatch.py": 300,
    "tests/lifecycle/test_plan_action_helpers.py": 380,
    "tests/lifecycle/test_plan_agent_tokens.py": 320,
    "tests/lifecycle/test_plan_interview.py": 320,
    "tests/lifecycle/test_progress_and_defaults.py": 290,
    "tests/lifecycle/test_source_and_state.py": 330,

    # ── MCP test modules ───────────────────────────────────────────────────────────
    "tests/mcp_servers/test_web_mcp.py": 420,
    "tests/mcp_servers/test_xanad_workspace_mcp_lifecycle.py": 280,
}
HARD_LIMIT_OVERRIDES: dict[str, int] = {
    # Web MCP server: grew with robots.txt support, retry logic, and WAF classification.
    "mcp/scripts/webMcp.py": 510,
    ".github/mcp/scripts/webMcp.py": 510,
    # Web MCP test suite: expanded to cover new fetch, retry, and search paths.
    "tests/mcp_servers/test_web_mcp.py": 470,
    # Workspace MCP (pre-existing): grew with command hardening.
    "mcp/scripts/xanadWorkspaceMcp.py": 425,
    ".github/mcp/scripts/xanadWorkspaceMcp.py": 425,
    # Git MCP server: grew with structured mutation envelopes, _run_flags_completed,
    # _mutation_result helper, git_diff_staged_stat / git_diff_unstaged_stat tools,
    # extended stash/rebase/push tool surface for the Commit-agent migration,
    # and git_merge (start/continue/abort) to replace runCommands for merge workflows.
    "mcp/scripts/gitMcp.py": 600,
    ".github/mcp/scripts/gitMcp.py": 600,
}


def collect_files(roots: list[str]) -> list[Path]:
    if roots:
        return [Path(p) for p in roots if Path(p).is_file()]
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [
            Path(p)
            for p in result.stdout.splitlines()
            if p and Path(p).suffix in EXTENSIONS
        ]
    except subprocess.CalledProcessError:
        # Fallback: walk the repo root
        repo_root = Path(__file__).resolve().parents[1]
        return [
            path
            for path in repo_root.rglob("*")
            if path.is_file() and path.suffix in EXTENSIONS
            and ".git" not in path.parts
        ]


def count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def _path_key(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def warning_limit_for(path: Path) -> int:
    return WARN_LIMIT_OVERRIDES.get(_path_key(path), WARN_LIMIT)


def hard_limit_for(path: Path) -> int:
    return HARD_LIMIT_OVERRIDES.get(_path_key(path), HARD_LIMIT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hard-only", action="store_true", help="Only report hard-limit violations.")
    parser.add_argument("files", nargs="*", help="Files to check (default: all tracked files).")
    args = parser.parse_args(argv)

    files = collect_files(args.files)
    warnings: list[tuple[Path, int, int]] = []
    violations: list[tuple[Path, int, int]] = []

    for path in sorted(files):
        n = count_lines(path)
        warn_limit = warning_limit_for(path)
        hard_limit = hard_limit_for(path)
        if n > hard_limit:
            violations.append((path, n, hard_limit))
        elif n > warn_limit and not args.hard_only:
            warnings.append((path, n, warn_limit))

    for path, n, warn_limit in warnings:
        suffix = "" if warn_limit == WARN_LIMIT else f"  (warn limit: {warn_limit})"
        print(f"WARN  {n:>5} lines  {path}{suffix}", file=sys.stderr)

    for path, n, hard_limit in violations:
        print(f"ERROR {n:>5} lines  {path}  (hard limit: {hard_limit})", file=sys.stderr)

    if violations:
        print(
            f"\nLOC gate FAILED: {len(violations)} file(s) exceed the hard limit.",
            file=sys.stderr,
        )
        return 1

    if warnings:
        print(
            f"\nLOC gate: {len(warnings)} file(s) exceed their warning threshold.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
