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
    "agents/xanadLifecycle.agent.md": 320,

    # ── Consumer hook scripts (single-file delivery) ──────────────────────────────
    # Consumer workspaces receive these hooks as single files, so they need a little
    # more room than the default warning budget while still honoring the hard limit.
    "hooks/scripts/xanadWorkspaceMcp.py": 380,
    "hooks/scripts/mcpSequentialThinkingServer.py": 260,
    "hooks/scripts/gitMcp.py": 380,
    "hooks/scripts/githubMcp.py": 450,  # matches hard limit override

    # ── Pack hooks (consumer-facing single-file scripts) ──────────────────────────
    "packs/secure/hooks/secureOsv.py": 300,
    "packs/shapeup/hooks/shapeupScopeCheck.py": 300,

    # ── Lifecycle engine submodules ───────────────────────────────────────────────
    # Each submodule is intentionally scoped; these grew slightly beyond 250 while
    # remaining well under the hard limit.
    "scripts/lifecycle/_xanad/_interview.py": 300,
    "scripts/lifecycle/_xanad/_plan_b.py": 300,

    # ── Developer sandbox ────────────────────────────────────────────────────────
    # Grows with each new workspace template; not a consumer surface.
    "scripts/sandbox.py": 380,
    # Pack workspace templates; _apply_in_ws + 17 template functions.
    "scripts/_sandbox_pack_workspaces.py": 300,    # Manifest generator grows as new surfaces and rules are added.
    "scripts/lifecycle/generate_manifest.py": 300,

    # ── Hook test modules ────────────────────────────────────────────────────────
    "tests/hooks/test_github_mcp_unit.py": 380,
    "tests/hooks/test_xanad_workspace_mcp_coverage2_unit.py": 300,
    "tests/hooks/test_xanad_workspace_mcp_unit.py": 380,

    # ── Lifecycle test modules ───────────────────────────────────────────────────
    "tests/lifecycle/test_apply_unit.py": 300,
    "tests/lifecycle/test_coverage_gaps.py": 380,
    "tests/lifecycle/test_execute_apply_b_unit.py": 300,
    "tests/lifecycle/test_execute_apply_unit.py": 320,
    "tests/lifecycle/test_inspect_check.py": 380,
    "tests/lifecycle/test_lifecycle_emit_progress_unit.py": 400,
    "tests/lifecycle/test_lifecycle_unit.py": 320,
    "tests/lifecycle/test_pack_e2e_a.py": 380,
    "tests/lifecycle/test_plan_actions_unit.py": 320,
    "tests/lifecycle/test_plan_lifecycle_a.py": 380,
    "tests/lifecycle/test_plan_result_unit.py": 380,
    "tests/lifecycle/test_plan_seed_unit.py": 300,
    "tests/lifecycle/test_plan_setup.py": 380,
    "tests/lifecycle/test_plan_unit.py": 380,
    "tests/lifecycle/test_workspace_scan_unit.py": 300,

    # ── Manifest test modules ────────────────────────────────────────────────────
    "tests/manifest/test_generate_manifest_unit.py": 300,
}
HARD_LIMIT_OVERRIDES: dict[str, int] = {
    # githubMcp.py covers a full GitHub REST API surface (auth, repos, issues, PRs,
    # releases, Actions) as a single file delivered verbatim to consumer workspaces.
    # Splitting the MCP server would require import machinery unavailable in those
    # workspaces, so a higher hard ceiling is appropriate here.
    "hooks/scripts/githubMcp.py": 450,
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
