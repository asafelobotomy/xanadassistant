"""Reporting commands for xanadEval: coverage, compare, report.

No API key required. All functions call helpers from _common and _static.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _common import _count_tokens, _parse_frontmatter
from _static import _build_check_result


# ── coverage ──────────────────────────────────────────────────────────────────


def cmd_coverage(root: str, fmt: str) -> int:
    """Scan a root directory for SKILL.md files and report eval coverage."""
    root_path = Path(root).resolve()
    skill_files = sorted(root_path.rglob("SKILL.md"))

    if not skill_files:
        print(f"xanadEval coverage: no SKILL.md files found under {root}", file=sys.stderr)
        return 1

    results = []
    for skill_file in skill_files:
        try:
            text = skill_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        name = fm.get("name") or skill_file.parent.name

        # Standard layout: <root>/skills/<name>/SKILL.md → <root>/evals/<name>/eval.yaml
        skill_root = skill_file.parent.parent.parent
        eval_yaml_path = skill_root / "evals" / name / "eval.yaml"
        task_count = 0
        if eval_yaml_path.exists():
            tasks_dir = eval_yaml_path.parent / "tasks"
            if tasks_dir.is_dir():
                task_count = sum(1 for f in tasks_dir.glob("*.yaml"))

        if not eval_yaml_path.exists():
            status = "missing"
        elif task_count == 0:
            status = "partial"
        else:
            status = "covered"

        results.append({
            "name": name,
            "path": str(skill_file.relative_to(root_path)),
            "eval_present": eval_yaml_path.exists(),
            "task_count": task_count,
            "status": status,
        })

    total = len(results)
    covered = sum(1 for r in results if r["status"] == "covered")
    partial = sum(1 for r in results if r["status"] == "partial")
    missing = sum(1 for r in results if r["status"] == "missing")
    pct = round(covered / total * 100) if total else 0

    if fmt == "json":
        print(json.dumps({
            "total": total,
            "covered": covered,
            "partial": partial,
            "missing": missing,
            "coverage_pct": pct,
            "skills": results,
        }, indent=2))
    else:
        print(f"xanadEval coverage \u2014 {root}")
        print(f"  {total} skill(s): {covered} covered, {partial} partial, {missing} missing  ({pct}%)")
        print()
        icons = {"covered": "\u2713", "partial": "~", "missing": "\u2717"}
        for r in results:
            icon = icons[r["status"]]
            tasks_note = f"{r['task_count']} task(s)" if r["eval_present"] else "no eval.yaml"
            print(f"  {icon} {r['name']:<30} {tasks_note}")

    return 0 if missing == 0 else 1


# ── compare ───────────────────────────────────────────────────────────────────


def cmd_compare(
    ref: str,
    paths: list[str],
    skills: bool,
    threshold: int | None,
    strict: bool,
    fmt: str,
) -> int:
    """Compare token counts between working tree and a git ref."""
    repo_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if repo_result.returncode != 0:
        print("xanadEval compare: not a git repository", file=sys.stderr)
        return 2
    repo_root = Path(repo_result.stdout.strip())

    if skills:
        file_paths: list[Path] = sorted(Path(".").resolve().rglob("SKILL.md"))
    elif paths:
        file_paths = [Path(p).resolve() for p in paths]
    else:
        print("xanadEval compare: specify paths or --skills", file=sys.stderr)
        return 2

    results: list[dict] = []
    any_over_threshold = False
    for fp in file_paths:
        try:
            new_content = fp.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            rel = fp.relative_to(repo_root)
        except ValueError:
            print(f"xanadEval compare: {fp} is outside the git repo", file=sys.stderr)
            continue

        old_proc = subprocess.run(
            ["git", "show", f"{ref}:{rel.as_posix()}"],
            capture_output=True,
            text=True,
        )
        new_count = _count_tokens(new_content)
        if old_proc.returncode != 0:
            results.append({
                "file": str(rel),
                "old_tokens": None,
                "new_tokens": new_count,
                "delta_pct": None,
                "status": "new",
            })
            continue

        old_count = _count_tokens(old_proc.stdout)
        if old_count == 0:
            delta_pct = None
            status = "new"
        else:
            delta_pct = round((new_count - old_count) / old_count * 100, 1)
            if threshold is not None and delta_pct > threshold:
                status = "over"
                any_over_threshold = True
            elif strict and threshold is not None and delta_pct < -threshold:
                status = "under"
                any_over_threshold = True
            else:
                status = "ok"

        results.append({
            "file": str(rel),
            "old_tokens": old_count,
            "new_tokens": new_count,
            "delta_pct": delta_pct,
            "status": status,
        })

    exit_code = 1 if (threshold is not None and any_over_threshold) else 0

    if fmt == "json":
        print(json.dumps(
            {"ref": ref, "threshold": threshold, "strict": strict, "files": results},
            indent=2,
        ))
    else:
        print(f"xanadEval compare \u2014 vs {ref}")
        for r in results:
            delta_str = f"{r['delta_pct']:+.1f}%" if r["delta_pct"] is not None else "(new)"
            flag = " \u26a0" if r["status"] in ("over", "under") else ""
            old_disp = str(r["old_tokens"]) if r["old_tokens"] is not None else "new"
            print(f"  {r['file']:<50}  {old_disp:>6} \u2192 {r['new_tokens']:>6}  {delta_str}{flag}")
        if threshold is not None:
            outcome = "FAIL" if any_over_threshold else "pass"
            print(f"\n  threshold: \u00b1{threshold}%  {outcome}")

    return exit_code


# ── report ────────────────────────────────────────────────────────────────────


def cmd_report(paths: list[str], output: str | None) -> int:
    """Generate a self-contained HTML report from check results."""
    records: list[dict] = []
    for p in paths:
        try:
            content = Path(p).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"xanadEval report: skipping {p}: {e}", file=sys.stderr)
            continue
        spec, advisory, level = _build_check_result(content, p)
        skill_name = Path(p).parent.name
        for id_, ok, detail in spec:
            records.append({"skill": skill_name, "check": id_, "pass": ok, "detail": detail, "type": "spec"})
        for id_, ok, detail in advisory:
            records.append({"skill": skill_name, "check": id_, "pass": ok, "detail": detail, "type": "advisory"})

    if not records:
        print("xanadEval report: no results to report", file=sys.stderr)
        return 1

    # Escape </ to prevent </script> from breaking out of the script block.
    data_json = json.dumps(records, indent=2).replace("</", "<\\/")
    total = len(records)
    passed = sum(1 for r in records if r["pass"])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>xanadEval Report</title>
<style>
  body {{ font-family: monospace; padding: 1rem; background: #fafafa; }}
  h1 {{ margin-bottom: 0.25rem; }}
  #summary {{ margin-bottom: 1rem; color: #555; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #333; color: #fff; padding: 0.4rem 0.8rem; text-align: left; }}
  td {{ border: 1px solid #ddd; padding: 0.35rem 0.8rem; }}
  tr:nth-child(even) {{ background: #f2f2f2; }}
  .pass {{ color: #2a7a2a; font-weight: bold; }}
  .fail {{ color: #c0392b; font-weight: bold; }}
  .spec {{ background: #eef4ff !important; }}
</style>
</head>
<body>
<h1>xanadEval Report</h1>
<div id="summary"></div>
<table><thead>
  <tr><th>Skill</th><th>Type</th><th>Check</th><th>Pass</th><th>Detail</th></tr>
</thead><tbody id="tbody"></tbody></table>
<script>
const data = {data_json};
let pass = 0, fail = 0;
data.forEach(r => {{
  const tr = document.createElement('tr');
  if (r.type === 'spec') tr.className = 'spec';
  ['skill', 'type', 'check'].forEach(k => {{
    const td = document.createElement('td');
    td.textContent = r[k];
    tr.appendChild(td);
  }});
  const tdPass = document.createElement('td');
  tdPass.className = r.pass ? 'pass' : 'fail';
  tdPass.textContent = r.pass ? '\u2713' : '\u2717';
  tr.appendChild(tdPass);
  const tdDetail = document.createElement('td');
  tdDetail.textContent = r.detail;
  tr.appendChild(tdDetail);
  document.getElementById('tbody').appendChild(tr);
  r.pass ? pass++ : fail++;
}});
document.getElementById('summary').textContent =
  `${{pass}} passed, ${{fail}} failed (${{data.length}} total checks)`;
</script>
</body></html>"""

    out_path = output or "xanadEval-report.html"
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"Written: {out_path}  ({passed}/{total} checks passing)")
    return 0
