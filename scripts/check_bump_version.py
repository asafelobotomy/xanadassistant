#!/usr/bin/env python3
"""Check package-version artifacts against VERSION and update stale references.

Usage:
    python3 scripts/check_bump_version.py [--check] [--repo-root <path>]

The canonical package version lives in the top-level VERSION file. This script
keeps the repository's version-sensitive artifacts aligned with that version:

- template/setup/install-manifest.json (via scripts/generate.py)
- .github/xanadAssistant-lock.json
- .github/copilot-version.md

Exit codes:
    0  All tracked version artifacts already match VERSION, or were updated.
    1  One or more version artifacts are stale in --check mode.
    2  Input or regeneration error prevented verification/update.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TextIO


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.lifecycle._xanad._apply import build_copilot_version_summary
from scripts.lifecycle._xanad._merge import sha256_json


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            handle.write(text)
            temp_path = Path(handle.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def _capture_artifact_snapshots(repo_root: Path) -> dict[Path, str | None]:
    paths = [
        repo_root / "template" / "setup" / "install-manifest.json",
        repo_root / ".github" / "xanadAssistant-lock.json",
        repo_root / ".github" / "copilot-version.md",
        repo_root / "template" / "setup" / "catalog.json",
    ]
    snapshots: dict[Path, str | None] = {}
    for path in paths:
        snapshots[path] = path.read_text(encoding="utf-8") if path.exists() else None
    return snapshots


def _restore_artifact_snapshots(snapshots: dict[Path, str | None]) -> None:
    for path, content in snapshots.items():
        if content is None:
            path.unlink(missing_ok=True)
            continue
        _write_text_atomic(path, content)


def read_canonical_version(repo_root: Path) -> str:
    version_file = repo_root / "VERSION"
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Failed to read VERSION: {exc}") from exc
    if not version:
        raise RuntimeError("VERSION is empty")
    return version


def read_manifest(repo_root: Path) -> dict:
    manifest_path = repo_root / "template" / "setup" / "install-manifest.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Failed to read install manifest: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse install manifest JSON: {exc}") from exc


def read_manifest_version(repo_root: Path) -> str:
    payload = read_manifest(repo_root)
    version = payload.get("packageVersion")
    if not isinstance(version, str) or not version:
        raise RuntimeError("install-manifest.json is missing packageVersion")
    return version


def read_lockfile(repo_root: Path) -> dict:
    lockfile_path = repo_root / ".github" / "xanadAssistant-lock.json"
    try:
        return json.loads(lockfile_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Failed to read {lockfile_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse {lockfile_path} JSON: {exc}") from exc


def run_generate(repo_root: Path, *, quiet: bool = False) -> None:
    generate_script = repo_root / "scripts" / "generate.py"
    if not generate_script.is_file():
        raise RuntimeError(f"Generate script not found: {generate_script}")
    try:
        kwargs: dict[str, object] = {}
        if quiet:
            kwargs["capture_output"] = True
            kwargs["text"] = True
        subprocess.run([sys.executable, str(generate_script)], cwd=repo_root, check=True, **kwargs)
    except subprocess.CalledProcessError as exc:
        details = ""
        if quiet:
            output = ((exc.stdout or "") + (exc.stderr or "")).strip()
            if output:
                details = f": {output}"
        raise RuntimeError(f"scripts/generate.py failed with exit code {exc.returncode}{details}") from exc


def sync_manifest(repo_root: Path, version: str, *, check_only: bool, quiet: bool = False) -> bool:
    current = read_manifest_version(repo_root)
    if current == version:
        return False
    if check_only:
        return True
    run_generate(repo_root, quiet=quiet)
    refreshed = read_manifest_version(repo_root)
    if refreshed != version:
        raise RuntimeError(
            f"Generated manifest packageVersion {refreshed!r} does not match VERSION {version!r}"
        )
    return True


def sync_lockfile(repo_root: Path, manifest: dict, *, check_only: bool) -> tuple[bool, dict]:
    lockfile_path = repo_root / ".github" / "xanadAssistant-lock.json"
    lockfile = read_lockfile(repo_root)
    expected_manifest_hash = sha256_json(manifest)
    current_manifest_hash = lockfile.get("manifest", {}).get("hash")
    changed = current_manifest_hash != expected_manifest_hash

    if changed:
        if check_only:
            return True, lockfile
        lockfile.setdefault("manifest", {})["hash"] = expected_manifest_hash
        current_timestamp = _current_timestamp()
        timestamps = lockfile.setdefault("timestamps", {})
        timestamps["appliedAt"] = current_timestamp
        timestamps["updatedAt"] = current_timestamp
        _write_text_atomic(lockfile_path, json.dumps(lockfile, indent=2) + "\n")
    return changed, lockfile


def sync_copilot_version_summary(repo_root: Path, manifest: dict, lockfile: dict, *, check_only: bool) -> bool:
    summary_path = repo_root / ".github" / "copilot-version.md"
    try:
        original = summary_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to read {summary_path}: {exc}") from exc

    updated = build_copilot_version_summary(lockfile, manifest)
    changed = updated != original
    if changed and not check_only:
        _write_text_atomic(summary_path, updated)
    return changed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report stale version artifacts without updating them.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root containing VERSION (default: inferred from this script).",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    quiet: bool = False,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else _default_repo_root()
    version = None
    snapshots = None if args.check else _capture_artifact_snapshots(repo_root)
    try:
        version = read_canonical_version(repo_root)
        stale_paths: list[str] = []

        if sync_manifest(repo_root, version, check_only=args.check, quiet=quiet):
            stale_paths.append("template/setup/install-manifest.json")

        manifest = read_manifest(repo_root)
        lockfile_changed, lockfile = sync_lockfile(repo_root, manifest, check_only=args.check)
        if lockfile_changed:
            stale_paths.append(".github/xanadAssistant-lock.json")
            if not args.check:
                lockfile = read_lockfile(repo_root)

        if sync_copilot_version_summary(repo_root, manifest, lockfile, check_only=args.check):
            stale_paths.append(".github/copilot-version.md")
    except RuntimeError as exc:
        if snapshots is not None:
            _restore_artifact_snapshots(snapshots)
        print(f"Version bump check failed: {exc}", file=stderr)
        return 2

    if args.check:
        if stale_paths:
            print(
                "Stale version references detected for "
                f"VERSION {version}: {', '.join(stale_paths)}",
                file=stderr,
            )
            return 1
        print(f"Version references already match VERSION {version}.", file=stdout)
        return 0

    if stale_paths:
        print(f"Updated version references for VERSION {version}: {', '.join(stale_paths)}", file=stdout)
    else:
        print(f"No version updates needed for VERSION {version}.", file=stdout)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())