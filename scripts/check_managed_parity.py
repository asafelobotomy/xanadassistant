#!/usr/bin/env python3
"""Maintainer parity gate — checks installed .github/ copies match their source.

Every managed file whose target path exists in the workspace must have content
identical to its source file.  Files with pack tokens are skipped because their
installed content diverges from source by design (tokens are replaced at install
time).  Managed files whose target does not yet exist are also skipped.

This script bypasses the consumer ownership model used by ``xanadAssistant.py
check``, so it catches drift in surfaces that are marked ``plugin-backed-copilot-
format`` and therefore skipped by the normal lifecycle check.

Usage:
    python3 scripts/check_managed_parity.py [--package-root PATH]

Exit codes:
    0  All present target files match their source.
    1  One or more target files differ from their source.
    2  Bad arguments or manifest not found.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def run(package_root: Path) -> int:
    manifest_path = package_root / "template" / "setup" / "install-manifest.json"
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    managed_files = json.loads(manifest_path.read_text(encoding="utf-8")).get("managedFiles", [])
    mismatches: list[str] = []
    checked = 0
    skipped_tokens = 0
    skipped_merge = 0

    for entry in managed_files:
        source_rel: str = entry.get("source", "")
        target_rel: str = entry.get("target", "")
        entry_id: str = entry.get("id", target_rel)
        tokens: list[str] = entry.get("tokens", [])
        strategy: str = entry.get("strategy", "")

        target_path = package_root / target_rel
        if not target_path.exists():
            continue

        # Merge/patch strategies produce installed content that legitimately
        # differs from source — skip them.
        if strategy not in {"replace-verbatim", "token-replace"}:
            skipped_merge += 1
            continue

        if tokens:
            # Token-replaced files: installed content differs from source by design.
            skipped_tokens += 1
            continue

        source_path = package_root / source_rel
        if not source_path.exists():
            print(f"WARNING: source missing for {entry_id}: {source_rel}", file=sys.stderr)
            continue

        source_hash = _sha256_file(source_path)
        target_hash = _sha256_file(target_path)
        checked += 1

        if source_hash != target_hash:
            mismatches.append(
                f"  {entry_id}\n    source: {source_rel}\n    target: {target_rel}"
            )

    if mismatches:
        print(
            f"Parity check FAILED: {len(mismatches)} file(s) differ from source "
            f"({checked} checked, {skipped_tokens} skipped due to tokens, "
            f"{skipped_merge} skipped due to merge strategy):",
            file=sys.stderr,
        )
        for msg in mismatches:
            print(msg, file=sys.stderr)
        return 1

    print(
        f"Parity check PASSED: {checked} file(s) match source "
        f"({skipped_tokens} skipped due to tokens, "
        f"{skipped_merge} skipped due to merge strategy).",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-root",
        default=".",
        help="Package root containing the manifest (default: current directory).",
    )
    args = parser.parse_args(argv)

    package_root = Path(args.package_root).resolve()
    if not package_root.is_dir():
        print(f"Package root does not exist: {package_root}", file=sys.stderr)
        return 2

    return run(package_root)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
