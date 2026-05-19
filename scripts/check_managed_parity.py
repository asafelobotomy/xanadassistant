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

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.lifecycle._xanad._conditions import resolve_token_values
from scripts.lifecycle._xanad._defaults import derive_effective_plan_defaults
from scripts.lifecycle._xanad._plan_utils import expected_entry_bytes
from scripts.lifecycle._xanad._state import parse_lockfile_state
from scripts.lifecycle._xanad._loader import load_json, load_optional_json


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _load_metadata(package_root: Path) -> dict:
    template_setup = package_root / "template" / "setup"
    return {
        "packRegistry": load_optional_json(template_setup / "pack-registry.json") or {},
        "profileRegistry": load_optional_json(template_setup / "profile-registry.json") or {},
        "agentRegistry": load_optional_json(template_setup / "agent-registry.json") or {},
    }


def _build_token_values(package_root: Path, workspace: Path, manifest: dict) -> dict[str, str]:
    policy = load_json(package_root / "template" / "setup" / "install-policy.json")
    metadata = _load_metadata(package_root)
    lockfile_state = parse_lockfile_state(workspace)
    resolved_answers, _ = derive_effective_plan_defaults(policy, metadata, manifest, lockfile_state)
    return resolve_token_values(
        policy,
        workspace,
        resolved_answers,
        package_root=package_root,
        metadata=metadata,
    )


def run(package_root: Path, workspace: Path | None = None) -> int:
    manifest_path = package_root / "template" / "setup" / "install-manifest.json"
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    workspace_root = (workspace or package_root).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    managed_files = manifest.get("managedFiles", [])
    token_values: dict[str, str] | None = None
    mismatches: list[str] = []
    checked = 0
    skipped_merge = 0

    for entry in managed_files:
        source_rel: str = entry.get("source", "")
        target_rel: str = entry.get("target", "")
        entry_id: str = entry.get("id", target_rel)
        tokens: list[str] = entry.get("tokens", [])
        strategy: str = entry.get("strategy", "")

        target_path = workspace_root / target_rel
        if not target_path.exists():
            continue

        # Merge/patch strategies produce installed content that legitimately
        # differs from source — skip them.
        if strategy not in {"replace-verbatim", "token-replace"}:
            skipped_merge += 1
            continue

        source_path = package_root / source_rel
        if not source_path.exists():
            print(f"WARNING: source missing for {entry_id}: {source_rel}", file=sys.stderr)
            continue

        if strategy == "token-replace":
            if token_values is None:
                token_values = _build_token_values(package_root, workspace_root, manifest)
            expected_bytes = expected_entry_bytes(package_root, entry, token_values, target_path)
            if expected_bytes is None:
                mismatches.append(
                    f"  {entry_id}\n    source: {source_rel}\n    target: {target_rel}\n    reason: failed to render expected tokenized content"
                )
                continue
            unresolved_tokens = [token for token in tokens if token.encode("utf-8") in expected_bytes]
            if unresolved_tokens:
                mismatches.append(
                    f"  {entry_id}\n    source: {source_rel}\n    target: {target_rel}\n    reason: unresolved tokens {unresolved_tokens}"
                )
                continue
            expected_hash = f"sha256:{hashlib.sha256(expected_bytes).hexdigest()}"
        else:
            expected_hash = _sha256_file(source_path)

        target_hash = _sha256_file(target_path)
        checked += 1

        if expected_hash != target_hash:
            mismatches.append(
                f"  {entry_id}\n    source: {source_rel}\n    target: {target_rel}"
            )

    if mismatches:
        print(
            f"Parity check FAILED: {len(mismatches)} file(s) differ from source "
            f"({checked} checked, 0 skipped due to tokens, "
            f"{skipped_merge} skipped due to merge strategy):",
            file=sys.stderr,
        )
        for msg in mismatches:
            print(msg, file=sys.stderr)
        return 1

    print(
        f"Parity check PASSED: {checked} file(s) match source "
        f"(0 skipped due to tokens, "
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
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace root containing installed target files (default: package root).",
    )
    args = parser.parse_args(argv)

    package_root = Path(args.package_root).resolve()
    if not package_root.is_dir():
        print(f"Package root does not exist: {package_root}", file=sys.stderr)
        return 2

    workspace_root = package_root if args.workspace is None else Path(args.workspace).resolve()
    if not workspace_root.is_dir():
        print(f"Workspace root does not exist: {workspace_root}", file=sys.stderr)
        return 2

    return run(package_root, workspace_root)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
