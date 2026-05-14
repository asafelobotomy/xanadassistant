"""Validation logic for sandbox workspaces.

Runs inspect + check against workspaces that carry expected_exit_codes metadata,
then asserts exit codes, install state, and (optionally) stale-entry findings.

Called from sandbox.py's `validate` subcommand.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_CLI = REPO_ROOT / "scripts" / "lifecycle" / "xanadAssistant.py"


def _lc(*args: str, workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CLI), *args,
         "--workspace", str(workspace), "--package-root", str(REPO_ROOT)],
        capture_output=True, text=True, check=False,
    )


def _stale_ids(stdout: str) -> list[str]:
    """Extract sorted list of stale entry IDs from check --json stdout."""
    try:
        entries = json.loads(stdout).get("result", {}).get("entries", [])
        return sorted(e["id"] for e in entries if e.get("status") == "stale")
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def cmd_validate(workspaces: dict, sandbox_dir: Path) -> None:
    """Assert exit codes and lifecycle state for all workspaces with expected_exit_codes."""
    total_pass = total_fail = total_skip = 0
    rows: list[tuple[str, str, str]] = []

    for name, meta in workspaces.items():
        if "expected_exit_codes" not in meta:
            total_skip += 1
            continue
        ws = sandbox_dir / name
        if not ws.exists():
            rows.append((name, "directory missing", "SKIP"))
            total_skip += 1
            continue

        expected_ec = meta["expected_exit_codes"]
        expected_state = meta.get("expected_state")
        expected_findings = meta.get("expected_findings")
        failures: list[str] = []

        # ── inspect ──────────────────────────────────────────────────────────
        ri = _lc("inspect", "--json", workspace=ws)
        exp_i = expected_ec.get("inspect", 0)
        if ri.returncode != exp_i:
            failures.append(f"inspect exit {ri.returncode}≠{exp_i}")
        if expected_state is not None:
            try:
                actual_state = json.loads(ri.stdout).get("result", {}).get("installState", "?")
            except json.JSONDecodeError:
                actual_state = "?"
            if actual_state != expected_state:
                failures.append(f"state {actual_state!r}≠{expected_state!r}")

        # ── check ─────────────────────────────────────────────────────────────
        rc = _lc("check", "--json", workspace=ws)
        exp_c = expected_ec.get("check", 0)
        if rc.returncode != exp_c:
            failures.append(f"check exit {rc.returncode}≠{exp_c}")
        if expected_findings is not None:
            actual_findings = _stale_ids(rc.stdout)
            expected_sorted = sorted(expected_findings)
            if actual_findings != expected_sorted:
                extra = sorted(set(actual_findings) - set(expected_sorted))
                missing = sorted(set(expected_sorted) - set(actual_findings))
                if extra:
                    failures.append(f"unexpected stale: {extra}")
                if missing:
                    failures.append(f"missing stale: {missing}")

        if failures:
            total_fail += 1
            rows.append((name, " | ".join(failures), "FAIL"))
        else:
            total_pass += 1
            rows.append((name, "inspect+check+findings", "PASS"))

    # ── output ────────────────────────────────────────────────────────────────
    print(f"\n  {'Workspace':<32} {'Detail':<34} Result")
    print("  " + "─" * 72)
    for ws_name, detail, result in rows:
        print(f"  {ws_name:<32} {detail:<34} {result}")
    print(f"\n{total_pass} passed, {total_fail} failed, {total_skip} skipped (no metadata or dir missing)")
    if total_fail:
        sys.exit(1)
