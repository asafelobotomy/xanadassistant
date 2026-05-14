"""Benchmark logic for sandbox workspaces.

Two modes:
  default  — single run per workspace + command; prints ms and PASS/FAIL.
  --timed  — 20 runs per workspace + command (2 warmup); prints p50/p95/stddev.

Called from sandbox.py's `benchmark` subcommand.
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_CLI = REPO_ROOT / "scripts" / "lifecycle" / "xanadAssistant.py"
RESULTS_DIR = REPO_ROOT / "results"

_TIMED_RUNS = 20
_TIMED_WARMUP = 2


def _lc(*args: str, workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CLI), *args,
         "--workspace", str(workspace), "--package-root", str(REPO_ROOT)],
        capture_output=True, text=True, check=False,
    )


def _percentile(sorted_ms: list[float], p: float) -> float:
    """Return the p-th percentile (0.0–1.0) of a sorted list."""
    idx = min(int(p * len(sorted_ms)), len(sorted_ms) - 1)
    return sorted_ms[max(0, idx)]


def _time_cmd(cmd: str, workspace: Path) -> dict:
    """Run cmd _TIMED_RUNS times, discard first _TIMED_WARMUP, return stats dict."""
    samples_ns: list[int] = []
    last_exit = 0
    for i in range(_TIMED_RUNS):
        t0 = time.perf_counter_ns()
        r = _lc(cmd, "--json", workspace=workspace)
        elapsed = time.perf_counter_ns() - t0
        if i >= _TIMED_WARMUP:
            samples_ns.append(elapsed)
        last_exit = r.returncode
    ms = sorted(ns / 1e6 for ns in samples_ns)
    n = len(ms)
    return {
        "exit": last_exit,
        "n": n,
        "mean_ms": round(sum(ms) / n, 1),
        "stddev_ms": round(statistics.stdev(ms) if n > 1 else 0.0, 1),
        "p5_ms": round(_percentile(ms, 0.05), 1),
        "p50_ms": round(_percentile(ms, 0.50), 1),
        "p95_ms": round(_percentile(ms, 0.95), 1),
    }


# ── Single-run benchmark ─────────────────────────────────────────────────────

def _run_section_single(
    workspaces: dict,
    sandbox_dir: Path,
    inspect_acc: list[int],
    check_acc: list[int],
    counters: list[int],     # [pass, fail, skip]
) -> None:
    row_fmt = "  {:<30} {:<9} {:>4} {:>7}  {}"
    for name, meta in workspaces.items():
        ws = sandbox_dir / name
        if not ws.exists():
            print(row_fmt.format(name, "—", "—", "—", "SKIP"))
            counters[2] += 1
            continue
        expected_state = meta.get("expected_state", "?")
        for cmd in ("inspect", "check"):
            t0 = time.monotonic()
            r = _lc(cmd, "--json", workspace=ws)
            ms = int((time.monotonic() - t0) * 1000)
            if cmd == "inspect":
                try:
                    actual = json.loads(r.stdout).get("result", {}).get("installState", "?")
                except json.JSONDecodeError:
                    actual = "?"
                ok = r.returncode == 0 and actual == expected_state
                note = f"state={actual}"
                if ok:
                    inspect_acc.append(ms)
            else:
                ok = r.returncode in (0, 7)
                note = f"exit={r.returncode}"
                if ok:
                    check_acc.append(ms)
            if ok:
                counters[0] += 1
            else:
                counters[1] += 1
            result = "PASS" if ok else f"FAIL  [{note}]"
            print(row_fmt.format(name, cmd, r.returncode, ms, result))


# ── Timed benchmark ──────────────────────────────────────────────────────────

def _run_section_timed(
    workspaces: dict,
    sandbox_dir: Path,
    save_data: dict,
    counters: list[int],
) -> dict:
    """Run timed measurements, populate save_data, return {inspect/check: p50_avg}."""
    header = f"  {'Workspace':<30} {'Cmd':<9} {'p50ms':>7} {'p95ms':>7} {'stddev':>7}  Result"
    print(header)
    print("  " + "─" * 66)
    inspect_p50s: list[float] = []
    check_p50s: list[float] = []

    for name, meta in workspaces.items():
        ws = sandbox_dir / name
        if not ws.exists():
            print(f"  {name:<30} {'—':<9} {'—':>7} {'—':>7} {'—':>7}  SKIP")
            counters[2] += 1
            continue
        budget_ms: int | None = meta.get("timing_budget_ms")
        ws_data: dict = {}
        for cmd in ("inspect", "check"):
            s = _time_cmd(cmd, ws)
            p50, p95, sd = s["p50_ms"], s["p95_ms"], s["stddev_ms"]
            over = budget_ms is not None and p95 > budget_ms
            result = f"OVER({p95:.0f}>{budget_ms}ms)" if over else "PASS"
            if over:
                counters[1] += 1
            else:
                counters[0] += 1
            print(f"  {name:<30} {cmd:<9} {p50:>7.0f} {p95:>7.0f} {sd:>7.1f}  {result}")
            ws_data[cmd] = s
            if cmd == "inspect":
                inspect_p50s.append(p50)
            else:
                check_p50s.append(p50)
        save_data[name] = ws_data

    avg_i = round(sum(inspect_p50s) / len(inspect_p50s), 1) if inspect_p50s else 0.0
    avg_c = round(sum(check_p50s) / len(check_p50s), 1) if check_p50s else 0.0
    return {"inspect": avg_i, "check": avg_c}


# ── Public command ────────────────────────────────────────────────────────────

def cmd_benchmark(
    agent_workspaces: dict,
    control_workspaces: dict,
    sandbox_dir: Path,
    *,
    timed: bool = False,
    save: bool = False,
) -> None:
    """Time inspect + check on control + agent/pack workspaces and compare."""
    if not sandbox_dir.exists():
        print("No sandbox. Run: python3 scripts/sandbox.py init")
        return

    if timed:
        _benchmark_timed(agent_workspaces, control_workspaces, sandbox_dir, save=save)
    else:
        _benchmark_single(agent_workspaces, control_workspaces, sandbox_dir)


def _benchmark_single(
    agent_workspaces: dict,
    control_workspaces: dict,
    sandbox_dir: Path,
) -> None:
    header = f"  {'Workspace':<30} {'Cmd':<9} {'Exit':>4} {'ms':>7}  Result"
    divider = "  " + "-" * 64
    ctrl_i_ms: list[int] = []
    ctrl_c_ms: list[int] = []
    ag_i_ms: list[int] = []
    ag_c_ms: list[int] = []
    counters = [0, 0, 0]   # [pass, fail, skip]

    print("\n=== CONTROL (baseline — no packs) ===")
    print(header)
    print(divider)
    _run_section_single(control_workspaces, sandbox_dir, ctrl_i_ms, ctrl_c_ms, counters)
    ctrl_i_avg = int(sum(ctrl_i_ms) / len(ctrl_i_ms)) if ctrl_i_ms else 0
    ctrl_c_avg = int(sum(ctrl_c_ms) / len(ctrl_c_ms)) if ctrl_c_ms else 0
    print(f"\n  Baseline avg — inspect: {ctrl_i_avg}ms  check: {ctrl_c_avg}ms")

    print("\n=== AGENT / PACK WORKSPACES ===")
    print(header)
    print(divider)
    _run_section_single(agent_workspaces, sandbox_dir, ag_i_ms, ag_c_ms, counters)
    ag_i_avg = int(sum(ag_i_ms) / len(ag_i_ms)) if ag_i_ms else 0
    ag_c_avg = int(sum(ag_c_ms) / len(ag_c_ms)) if ag_c_ms else 0
    print(f"\n  Agent/pack avg  — inspect: {ag_i_avg}ms  check: {ag_c_avg}ms")
    if ctrl_i_avg:
        print(f"  Overhead vs control — inspect: {ag_i_avg - ctrl_i_avg:+d}ms  "
              f"check: {ag_c_avg - ctrl_c_avg:+d}ms")

    print(f"\n{counters[0]} passed, {counters[1]} failed, {counters[2]} workspaces skipped")
    if counters[1]:
        sys.exit(1)


def _benchmark_timed(
    agent_workspaces: dict,
    control_workspaces: dict,
    sandbox_dir: Path,
    *,
    save: bool = False,
) -> None:
    n_measured = _TIMED_RUNS - _TIMED_WARMUP
    print(f"\n(timed mode: {_TIMED_RUNS} runs, {_TIMED_WARMUP} warmup, {n_measured} measured per cmd)")
    save_data: dict = {}
    counters = [0, 0, 0]

    print("\n=== CONTROL (baseline — no packs) ===")
    ctrl_avgs = _run_section_timed(control_workspaces, sandbox_dir, save_data, counters)
    print(f"\n  Baseline p50 avg — inspect: {ctrl_avgs['inspect']:.0f}ms  "
          f"check: {ctrl_avgs['check']:.0f}ms")

    print("\n=== AGENT / PACK WORKSPACES ===")
    ag_avgs = _run_section_timed(agent_workspaces, sandbox_dir, save_data, counters)
    print(f"\n  Agent/pack p50 avg — inspect: {ag_avgs['inspect']:.0f}ms  "
          f"check: {ag_avgs['check']:.0f}ms")
    if ctrl_avgs["inspect"]:
        print(f"  Overhead vs control — inspect: {ag_avgs['inspect'] - ctrl_avgs['inspect']:+.0f}ms  "
              f"check: {ag_avgs['check'] - ctrl_avgs['check']:+.0f}ms")

    if save:
        _save_results(save_data, ctrl_avgs, ag_avgs, n_measured)

    print(f"\n{counters[0]} passed, {counters[1]} budget violations, {counters[2]} workspaces skipped")
    if counters[1]:
        sys.exit(1)


def _save_results(
    save_data: dict,
    ctrl_avgs: dict,
    ag_avgs: dict,
    n_measured: int,
) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / f"bench-{ts}.json"
    payload = {
        "generated": datetime.now(tz=timezone.utc).isoformat(),
        "mode": "timed",
        "runs": _TIMED_RUNS,
        "warmup": _TIMED_WARMUP,
        "measured": n_measured,
        "control_baseline": {"inspect_p50_ms": ctrl_avgs["inspect"], "check_p50_ms": ctrl_avgs["check"]},
        "agent_avg": {"inspect_p50_ms": ag_avgs["inspect"], "check_p50_ms": ag_avgs["check"]},
        "workspaces": save_data,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        display = out.relative_to(REPO_ROOT)
    except ValueError:
        display = out
    print(f"\n  Results saved → {display}")
