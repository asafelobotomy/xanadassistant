"""Results management commands for xanadEval: results list, view, compare.

No model API calls required — no bind_api needed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from _common import _DEFAULT_RESULTS_DIR  # noqa: F401  (re-exported for consumers)


# ── results list ──────────────────────────────────────────────────────────────


def cmd_results_list(results_dir: str, fmt: str) -> int:
    """List saved eval result files."""
    rdir = Path(results_dir)
    if not rdir.exists():
        print(f"xanadEval results: directory not found: {results_dir}", file=sys.stderr)
        return 1
    files = sorted(rdir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        print(f"xanadEval results: no result files in {results_dir}", file=sys.stderr)
        return 1
    records: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            records.append({
                "file": f.name,
                "skill": data.get("skill", "?"),
                "model": data.get("model", "?"),
                "timestamp": data.get("timestamp", "?"),
                "pass_rate": data.get("summary", {}).get("pass_rate"),
                "score": data.get("summary", {}).get("score"),
            })
        except (OSError, json.JSONDecodeError):
            continue
    if fmt == "json":
        print(json.dumps(records, indent=2))
    else:
        print(f"xanadEval results \u2014 {results_dir}")
        for r in records:
            pr = f"{r['pass_rate']:.0%}" if r["pass_rate"] is not None else "?"
            sc = f"{r['score']:.3f}" if r["score"] is not None else "?"
            print(f"  {r['file']:<60}  {pr}  score: {sc}")
    return 0


# ── results view ──────────────────────────────────────────────────────────────


def cmd_results_view(results_path: str, fmt: str) -> int:
    """Display a saved eval result file."""
    try:
        data = json.loads(Path(results_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"xanadEval results view: {e}", file=sys.stderr)
        return 2
    if fmt == "json":
        print(json.dumps(data, indent=2))
    else:
        summary = data.get("summary", {})
        pr = summary.get("pass_rate")
        print(f"xanadEval results view \u2014 {Path(results_path).name}")
        print(f"  skill:     {data.get('skill', '?')}")
        print(f"  model:     {data.get('model', '?')}")
        print(f"  timestamp: {data.get('timestamp', '?')}")
        if pr is not None:
            print(f"  pass_rate: {pr:.0%}")
        print(f"  score:     {summary.get('score', '?')}")
        print()
        for t in data.get("tasks", []):
            icon = "\u2713" if t.get("passed") else "\u2717"
            score = t.get("score", 0)
            print(f"  {icon} {t.get('id', '?'):<40}  score: {score:.3f}")
            for g in t.get("graders", []):
                g_icon = "\u2713" if g.get("pass") else ("?" if g.get("pass") is None else "\u2717")
                note = (
                    f"  [{g.get('skipped') or g.get('error', '')}]"
                    if (g.get("skipped") or g.get("error"))
                    else ""
                )
                print(f"      {g_icon} {g.get('type', '?')}/{g.get('name', '?')}{note}")
    return 0


# ── results compare ───────────────────────────────────────────────────────────


def cmd_compare_results(files: list[str], fmt: str) -> int:
    """Compare pass-rate and per-task scores across two or more result files."""
    if len(files) < 2:
        print("xanadEval results compare: provide at least 2 result files", file=sys.stderr)
        return 2
    loaded: list[tuple[str, dict]] = []
    for f in files:
        try:
            loaded.append((f, json.loads(Path(f).read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError) as e:
            print(f"xanadEval results compare: cannot load {f}: {e}", file=sys.stderr)
            return 2

    base_name, base_data = loaded[0]
    base_tasks = {t["id"]: t for t in base_data.get("tasks", [])}
    deltas: list[dict] = []
    for fname, rdata in loaded[1:]:
        compare_tasks = {t["id"]: t for t in rdata.get("tasks", [])}
        for tid in sorted(set(base_tasks) | set(compare_tasks)):
            if tid in base_tasks and tid in compare_tasks:
                bt, ct = base_tasks[tid], compare_tasks[tid]
                _bs = bt.get("score")
                _cs = ct.get("score")
                _bs_f = float(_bs) if _bs is not None else 0.0
                _cs_f = float(_cs) if _cs is not None else 0.0
                deltas.append({
                    "task": tid,
                    "baseline_score": _bs_f,
                    "compare_score": _cs_f,
                    "delta": round(_cs_f - _bs_f, 3),
                    "baseline_pass": bt.get("passed"),
                    "compare_pass": ct.get("passed"),
                    "compare_file": fname,
                    "status": "changed",
                })
            elif tid in compare_tasks:
                ct = compare_tasks[tid]
                deltas.append({
                    "task": tid,
                    "baseline_score": None,
                    "compare_score": ct.get("score", 0),
                    "delta": None,
                    "baseline_pass": None,
                    "compare_pass": ct.get("passed"),
                    "compare_file": fname,
                    "status": "added",
                })
            else:
                bt = base_tasks[tid]
                deltas.append({
                    "task": tid,
                    "baseline_score": bt.get("score", 0),
                    "compare_score": None,
                    "delta": None,
                    "baseline_pass": bt.get("passed"),
                    "compare_pass": None,
                    "compare_file": fname,
                    "status": "removed",
                })

    if fmt == "json":
        print(json.dumps({
            "baseline": base_name,
            "baseline_summary": base_data.get("summary", {}),
            "files": [{"file": f, "summary": d.get("summary", {})} for f, d in loaded[1:]],
            "task_deltas": deltas,
        }, indent=2))
    else:
        base_s = base_data.get("summary", {})
        bpr = base_s.get("pass_rate")
        print("xanadEval results compare")
        print(f"  baseline: {base_name}")
        print(f"    pass_rate: {bpr:.0%}  score: {base_s.get('score', '?')}"
              if bpr is not None else f"    {base_s}")
        for fname, fdata in loaded[1:]:
            fs = fdata.get("summary", {})
            fpr = fs.get("pass_rate")
            print(f"  compare:  {fname}")
            print(f"    pass_rate: {fpr:.0%}  score: {fs.get('score', '?')}"
                  if fpr is not None else f"    {fs}")
        if deltas:
            print("\n  task deltas:")
            for d in deltas:
                status = d.get("status", "changed")
                if status == "added":
                    print(f"    + {d['task']:<40}  (added)")
                elif status == "removed":
                    print(f"    - {d['task']:<40}  (removed)")
                else:
                    arrow = "\u2191" if d["delta"] > 0 else ("\u2193" if d["delta"] < 0 else "=")
                    print(
                        f"    {d['task']:<40}  "
                        f"{d['baseline_score']:.3f} {arrow} {d['compare_score']:.3f}"
                        f"  (\u0394{d['delta']:+.3f})"
                    )
    return 0
