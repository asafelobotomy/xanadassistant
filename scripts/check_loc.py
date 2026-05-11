#!/usr/bin/env python3
"""LOC gate — enforces the default 250-warning / 400-hard-limit per-file policy.

Usage:
    python3 scripts/check_loc.py [--hard-only] [file ...]

Without file arguments, scans the whole repo (respecting .gitignore via git ls-files).
Exit codes:
    0  All files within limits.
    1  One or more files exceed the hard limit (400 lines).

Files above their warning threshold but at or below 400 lines emit warnings but do not fail.
Some constrained surfaces may have a higher warning threshold while keeping the same
400-line hard limit.

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
EXTENSIONS = {".py", ".md", ".sh"}
WARN_LIMIT_OVERRIDES = {
    # Consumer workspaces receive these hooks as single files, so they need a little
    # more room than the default warning budget while still honoring the hard limit.
    "hooks/scripts/xanad-workspace-mcp.py": 380,
    "hooks/scripts/mcp-sequential-thinking-server.py": 380,
    "hooks/scripts/git-mcp.py": 380,
    "hooks/scripts/github-mcp.py": 380,
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


def warning_limit_for(path: Path) -> int:
    try:
        key = path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        key = path.as_posix()
    return WARN_LIMIT_OVERRIDES.get(key, WARN_LIMIT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hard-only", action="store_true", help="Only report hard-limit violations.")
    parser.add_argument("files", nargs="*", help="Files to check (default: all tracked files).")
    args = parser.parse_args(argv)

    files = collect_files(args.files)
    warnings: list[tuple[Path, int, int]] = []
    violations: list[tuple[Path, int]] = []

    for path in sorted(files):
        n = count_lines(path)
        warn_limit = warning_limit_for(path)
        if n > HARD_LIMIT:
            violations.append((path, n))
        elif n > warn_limit and not args.hard_only:
            warnings.append((path, n, warn_limit))

    for path, n, warn_limit in warnings:
        suffix = "" if warn_limit == WARN_LIMIT else f"  (warn limit: {warn_limit})"
        print(f"WARN  {n:>5} lines  {path}{suffix}", file=sys.stderr)

    for path, n in violations:
        print(f"ERROR {n:>5} lines  {path}  (hard limit: {HARD_LIMIT})", file=sys.stderr)

    if violations:
        print(
            f"\nLOC gate FAILED: {len(violations)} file(s) exceed the {HARD_LIMIT}-line hard limit.",
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
