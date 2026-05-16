#!/usr/bin/env python3
"""Drift preflight for xanadassistant maintainer changes.

Usage:
    python3 scripts/drift_preflight.py
    python3 scripts/drift_preflight.py --check tests
    python3 scripts/drift_preflight.py --list

Runs the repository's maintained drift gates in a stable order so local
verification and CI share one command authority. Exit code 0 means all selected
checks passed; any non-zero exit code is returned from the first failing check.
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    description: str
    command: tuple[str, ...]


CHECKS: tuple[Check, ...] = (
    Check(
        name="attention-budget",
        description="Maintainer-facing Markdown attention budgets.",
        command=("python3", "scripts/check_attention_budget.py"),
    ),
    Check(
        name="loc",
        description="LOC gate for tracked source files.",
        command=("python3", "scripts/check_loc.py"),
    ),
    Check(
        name="tests",
        description="Full unittest suite.",
        command=("python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"),
    ),
    Check(
        name="freshness",
        description="Generated manifest/catalog freshness against policy and templates.",
        command=(
            "python3",
            "-m",
            "scripts.lifecycle.check_manifest_freshness",
            "--package-root",
            ".",
            "--policy",
            "template/setup/install-policy.json",
            "--manifest",
            "template/setup/install-manifest.json",
            "--catalog",
            "template/setup/catalog.json",
        ),
    ),
)
CHECKS_BY_NAME = {check.name: check for check in CHECKS}


def _command_text(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _selected_checks(selected_names: list[str] | None) -> list[Check]:
    if not selected_names:
        return list(CHECKS)
    return [CHECKS_BY_NAME[name] for name in selected_names]


def run(repo_root: Path, selected_names: list[str] | None = None) -> int:
    selected_checks = _selected_checks(selected_names)
    for check in selected_checks:
        print(f"==> {check.name}: {_command_text(check.command)}", file=sys.stderr)
        result = subprocess.run(check.command, cwd=repo_root)
        if result.returncode != 0:
            print(f"\nDrift preflight FAILED at '{check.name}'.", file=sys.stderr)
            return result.returncode
    print("\nDrift preflight PASSED.", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root to validate.")
    parser.add_argument(
        "--check",
        action="append",
        choices=[check.name for check in CHECKS],
        default=[],
        help="Run only the named check. Repeatable.",
    )
    parser.add_argument("--list", action="store_true", help="List available checks and exit.")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        print(f"Repository root does not exist: {repo_root}", file=sys.stderr)
        return 2

    if args.list:
        for check in CHECKS:
            print(f"{check.name}\t{check.description}\t{_command_text(check.command)}")
        return 0

    return run(repo_root, args.check or None)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())