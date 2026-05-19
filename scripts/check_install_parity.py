#!/usr/bin/env python3
"""Maintainer parity gate for a fresh local install in a temporary workspace.

This script plans and applies a non-interactive local setup into an empty
temporary workspace, then verifies that the installed managed files match the
package source using the parity checker. It closes the blind spot where the
package repo itself may not have every managed target installed.

Usage:
    python3 scripts/check_install_parity.py [--package-root PATH]

Exit codes:
    0  Fresh install parity passed.
    1  Installed files differ from expected source/rendered content.
    2  Bad arguments or missing package root.
    4  Lifecycle planning/apply contract failure.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import check_managed_parity
from scripts.lifecycle._xanad._execute_apply import build_setup_result
from scripts.lifecycle._xanad._plan_b import build_plan_result


def _write_answers_file(workspace: Path) -> Path:
    answers_path = workspace / "setup-answers.json"
    answers_path.write_text(json.dumps({}, indent=2) + "\n", encoding="utf-8")
    return answers_path


def run(package_root: Path) -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        answers_path = _write_answers_file(workspace)
        plan_payload = build_plan_result(
            workspace,
            package_root,
            "setup",
            str(answers_path),
            True,
        )
        if plan_payload["result"].get("conflictDetails"):
            print("Setup plan unexpectedly requires conflict resolution.", file=sys.stderr)
            return 4
        plan_path = workspace / "setup-plan.json"
        plan_path.write_text(json.dumps(plan_payload, indent=2) + "\n", encoding="utf-8")
        build_setup_result(
            workspace,
            package_root,
            dry_run=False,
            plan_path=str(plan_path),
        )
        return check_managed_parity.run(package_root, workspace)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-root",
        default=".",
        help="Package root containing lifecycle contracts and managed sources (default: current directory).",
    )
    args = parser.parse_args(argv)

    package_root = Path(args.package_root).resolve()
    if not package_root.is_dir():
        print(f"Package root does not exist: {package_root}", file=sys.stderr)
        return 2

    return run(package_root)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())