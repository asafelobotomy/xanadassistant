#!/usr/bin/env python3
"""LOC gate — enforces the 250-warning / 400-hard-limit per-file policy.

Usage:
    python3 scripts/check_loc.py [--hard-only] [file ...]

Without file arguments, scans the whole repo (respecting .gitignore via git ls-files).
Exit codes:
    0  All files within limits.
    1  One or more files exceed the hard limit (400 lines).

Files between 250 and 400 lines emit warnings but do not fail.

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hard-only", action="store_true", help="Only report hard-limit violations.")
    parser.add_argument("files", nargs="*", help="Files to check (default: all tracked files).")
    args = parser.parse_args(argv)

    files = collect_files(args.files)
    warnings: list[tuple[Path, int]] = []
    violations: list[tuple[Path, int]] = []

    for path in sorted(files):
        n = count_lines(path)
        if n > HARD_LIMIT:
            violations.append((path, n))
        elif n > WARN_LIMIT and not args.hard_only:
            warnings.append((path, n))

    for path, n in warnings:
        print(f"WARN  {n:>5} lines  {path}", file=sys.stderr)

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
            f"\nLOC gate: {len(warnings)} file(s) exceed the {WARN_LIMIT}-line warning threshold.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
