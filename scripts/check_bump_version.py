#!/usr/bin/env python3
"""Check package-version mirrors against VERSION and update stale references.

Usage:
    python3 scripts/check_bump_version.py [--check] [--repo-root <path>]

The canonical package version lives in the top-level VERSION file. This script
keeps the explicit repository mirrors aligned with that version:

- template/setup/install-manifest.json (via scripts/generate.py)
- .github/copilot-version.md

Exit codes:
    0  All tracked version mirrors already match VERSION, or were updated.
    1  One or more version mirrors are stale in --check mode.
    2  Input or regeneration error prevented verification/update.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_canonical_version(repo_root: Path) -> str:
    version_file = repo_root / "VERSION"
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Failed to read VERSION: {exc}") from exc
    if not version:
        raise RuntimeError("VERSION is empty")
    return version


def read_manifest_version(repo_root: Path) -> str:
    manifest_path = repo_root / "template" / "setup" / "install-manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Failed to read install manifest: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse install manifest JSON: {exc}") from exc
    version = payload.get("packageVersion")
    if not isinstance(version, str) or not version:
        raise RuntimeError("install-manifest.json is missing packageVersion")
    return version


def run_generate(repo_root: Path) -> None:
    generate_script = repo_root / "scripts" / "generate.py"
    if not generate_script.is_file():
        raise RuntimeError(f"Generate script not found: {generate_script}")
    try:
        subprocess.run(
            [sys.executable, str(generate_script)],
            cwd=repo_root,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"scripts/generate.py failed with exit code {exc.returncode}") from exc


def sync_manifest(repo_root: Path, version: str, *, check_only: bool) -> bool:
    current = read_manifest_version(repo_root)
    if current == version:
        return False
    if check_only:
        return True
    run_generate(repo_root)
    refreshed = read_manifest_version(repo_root)
    if refreshed != version:
        raise RuntimeError(
            f"Generated manifest packageVersion {refreshed!r} does not match VERSION {version!r}"
        )
    return True


def _replace_once(pattern: str, replacement: str, text: str, *, target: str) -> tuple[str, bool]:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count == 0:
        raise RuntimeError(f"Expected pattern not found in {target}: {pattern}")
    return updated, updated != text


def sync_copilot_version_summary(repo_root: Path, version: str, *, check_only: bool) -> bool:
    summary_path = repo_root / ".github" / "copilot-version.md"
    try:
        original = summary_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to read {summary_path}: {exc}") from exc

    updated, changed_header = _replace_once(
        r"^Version: .*$",
        f"Version: {version}",
        original,
        target=str(summary_path),
    )
    updated, changed_json = _replace_once(
        r'"version":\s*"[^"]+"',
        f'"version": "{version}"',
        updated,
        target=str(summary_path),
    )
    changed = changed_header or changed_json
    if changed and not check_only:
        summary_path.write_text(updated, encoding="utf-8")
    return changed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report stale version mirrors without updating them.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root containing VERSION (default: inferred from this script).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _default_repo_root()
    version = None
    try:
        version = read_canonical_version(repo_root)
        stale_paths: list[str] = []

        if sync_manifest(repo_root, version, check_only=args.check):
            stale_paths.append("template/setup/install-manifest.json")
        if sync_copilot_version_summary(repo_root, version, check_only=args.check):
            stale_paths.append(".github/copilot-version.md")
    except RuntimeError as exc:
        print(f"Version bump check failed: {exc}", file=sys.stderr)
        return 2

    if args.check:
        if stale_paths:
            print(
                "Stale version references detected for "
                f"VERSION {version}: {', '.join(stale_paths)}",
                file=sys.stderr,
            )
            return 1
        print(f"Version references already match VERSION {version}.")
        return 0

    if stale_paths:
        print(f"Updated version references for VERSION {version}: {', '.join(stale_paths)}")
    else:
        print(f"No version updates needed for VERSION {version}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())