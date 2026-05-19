#!/usr/bin/env python3
"""Decide whether the current HEAD version should publish a GitHub release.

Usage:
    python3 scripts/release_decision.py [--repo-root PATH] [--repository OWNER/REPO] [--github-output PATH]

The decision is based on the current HEAD VERSION file, not on whether the
latest successful push diff happened to include VERSION. This makes the release
workflow recoverable after a failed version-bump push followed by a later repair
push on main.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TextIO


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_version(repo_root: Path) -> str:
    version_path = repo_root / "VERSION"
    try:
        version = version_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Failed to read VERSION: {exc}") from exc
    if not version:
        raise RuntimeError("VERSION is empty")
    return version


def release_exists(tag: str, repository: str | None = None) -> bool:
    command = ["gh", "release", "view", tag, "--json", "tagName"]
    if repository:
        command.extend(["--repo", repository])

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise RuntimeError(f"Failed to run gh release view: {exc}") from exc

    if result.returncode == 0:
        return True

    stderr = (result.stderr or "").lower()
    if "release not found" in stderr or "http 404" in stderr or "not found" in stderr:
        return False

    raise RuntimeError(
        "gh release view failed with exit code "
        f"{result.returncode}: {(result.stderr or result.stdout).strip()}"
    )


def build_decision(repo_root: Path, repository: str | None = None) -> dict[str, str | bool]:
    version = read_version(repo_root)
    tag = f"v{version}"
    exists = release_exists(tag, repository)
    return {
        "version": version,
        "tag": tag,
        "should_publish": not exists,
        "reason": "release_exists" if exists else "unreleased_head_version",
    }


def write_github_output(output_path: Path, decision: dict[str, str | bool]) -> None:
    lines = []
    for key, value in decision.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = value
        lines.append(f"{key}={rendered}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=None, help="Repository root containing VERSION.")
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="Optional OWNER/REPO value for gh release lookup (defaults to GITHUB_REPOSITORY).",
    )
    parser.add_argument(
        "--github-output",
        default=None,
        help="Optional file path to write GitHub Actions step outputs.",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else _default_repo_root()

    try:
        decision = build_decision(repo_root, args.repository)
    except RuntimeError as exc:
        print(f"Release decision failed: {exc}", file=stderr)
        return 2

    if args.github_output:
        write_github_output(Path(args.github_output), decision)

    print(json.dumps(decision, indent=2), file=stdout)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())