#!/usr/bin/env python3
"""Attention-budget gate for maintainer-facing Markdown surfaces.

Usage:
    python3 scripts/check_attention_budget.py
    python3 scripts/check_attention_budget.py --repo-root <path> --budget path/to/file.md=120

Without explicit budgets, the script checks the repository's maintained attention-budget
targets. Exit code 0 means all files are within budget; exit code 1 means at least one
file exceeded its budget or was missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_BUDGETS: tuple[tuple[str, int], ...] = (
    ("template/copilot-instructions.md", 150),
    (".github/copilot-instructions.md", 140),
    ("AGENTS.md", 110),
    ("docs/template-review-adopt.md", 360),
)


def parse_budget(value: str) -> tuple[str, int]:
    try:
        path_text, limit_text = value.rsplit("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("budget entries must look like path/to/file.md=123") from exc
    path_text = path_text.strip()
    if not path_text:
        raise argparse.ArgumentTypeError("budget path cannot be empty")
    try:
        limit = int(limit_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("budget limit must be an integer") from exc
    if limit < 1:
        raise argparse.ArgumentTypeError("budget limit must be positive")
    return path_text, limit


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def run(repo_root: Path, budgets: list[tuple[str, int]]) -> int:
    failures = 0
    for relative_path, limit in budgets:
        path = repo_root / relative_path
        if not path.exists():
            print(f"ERROR missing file  {relative_path}", file=sys.stderr)
            failures += 1
            continue
        line_count = count_lines(path)
        if line_count > limit:
            print(
                f"ERROR attention budget exceeded  {relative_path}  {line_count}>{limit}",
                file=sys.stderr,
            )
            failures += 1
            continue
        print(f"OK    {relative_path}  {line_count}/{limit}", file=sys.stderr)
    if failures:
        print(
            f"\nAttention-budget check FAILED: {failures} file(s) exceeded budget or were missing.",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root to check.")
    parser.add_argument(
        "--budget",
        action="append",
        type=parse_budget,
        default=[],
        help="Override budgets with path/to/file.md=123. Repeatable.",
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    budgets = args.budget or list(DEFAULT_BUDGETS)
    return run(repo_root, budgets)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())