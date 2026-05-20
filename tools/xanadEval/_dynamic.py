"""Dynamic eval commands for xanadEval: run, grade.

Requires GITHUB_TOKEN or GH_TOKEN. Uses bind_api() so that
mock.patch("xanadEval._call_model") is intercepted at runtime.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
from pathlib import Path

import _common
from _common import (
    _DEFAULT_MODEL, _DEFAULT_RESULTS_DIR,
    _aggregate_trials, _get_token, _load_spec, _load_tasks, _run_graders,
    _yaml,
)

# ── bind_api ──────────────────────────────────────────────────────────────────
# xanadEval.py binds itself here so mock.patch("xanadEval._call_model") works
# for tests that call cmd_run / cmd_grade.

_api: object = _common

def bind_api(m: object) -> None:
    """Bind the xanadEval wrapper module as the runtime API source."""
    global _api
    _api = m


# ── run ───────────────────────────────────────────────────────────────────────


def cmd_run(eval_path: str, model: str, trials: int, fmt: str) -> int:
    """Execute eval tasks against GitHub Models and save results."""
    token = _get_token()
    if not token:
        print("xanadEval run: GITHUB_TOKEN (or GH_TOKEN) is not set", file=sys.stderr)
        return 2

    try:
        spec = _load_spec(eval_path)
    except Exception as e:
        print(f"xanadEval run: cannot load {eval_path}: {e}", file=sys.stderr)
        if _yaml is None:
            print("  hint: install PyYAML — pip install pyyaml", file=sys.stderr)
        return 2

    eval_dir = Path(eval_path).parent
    skill_name = spec.get("name", eval_dir.name)
    safe_skill_name = re.sub(r"[^a-zA-Z0-9._-]", "-", skill_name)
    graders_spec = spec.get("graders", [])

    try:
        tasks = _load_tasks(eval_dir, spec.get("tasks", []))
    except Exception as e:
        print(f"xanadEval run: cannot load tasks: {e}", file=sys.stderr)
        if _yaml is None:
            print("  hint: install PyYAML \u2014 pip install pyyaml", file=sys.stderr)
        return 2
    if not tasks:
        print(f"xanadEval run: no tasks found in {eval_path}", file=sys.stderr)
        return 2

    skill_path = eval_dir.parent.parent / "skills" / eval_dir.name / "SKILL.md"
    skill_content = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""

    task_results: list[dict] = []
    for task in tasks:
        task_id = task.get("id", "?")
        prompt = str(task.get("prompt", ""))
        messages: list[dict] = []
        if skill_content:
            messages.append({"role": "system", "content": skill_content[:6000]})
        messages.append({"role": "user", "content": prompt})

        responses: list[str] = []
        for _ in range(max(trials, 1)):
            try:
                # Dispatch through _api so mock.patch("xanadEval._call_model") works.
                responses.append(_api._call_model(messages, model, token))  # type: ignore[union-attr]
            except RuntimeError as e:
                print(f"  error on {task_id}: {e}", file=sys.stderr)
                responses.append("")

        response = responses[0] if responses else ""
        absent_patterns = [str(p) for p in task.get("expected_absent", [])]
        all_trial_graders: list[list[dict]] = []
        for resp in responses:
            trial_gr = _run_graders(resp, graders_spec, model, token)
            for pattern in absent_patterns:
                hit = bool(re.search(pattern, resp, re.IGNORECASE))
                trial_gr.append({"type": "expected_absent", "name": pattern,
                                 "pass": not hit, "score": 0.0 if hit else 1.0})
            all_trial_graders.append(trial_gr)

        grader_results = (
            all_trial_graders[0]
            if len(all_trial_graders) == 1
            else _aggregate_trials(all_trial_graders, len(responses))
        )

        graded = [g for g in grader_results if g.get("pass") is not None]
        passed = bool(graded) and all(g["pass"] for g in graded)
        score = (sum(g["score"] for g in graded) / len(graded)) if graded else 0.0
        task_results.append({
            "id": task_id,
            "prompt": prompt[:300] + "\u2026" if len(prompt) > 300 else prompt,
            "response": response[:800] + "\u2026" if len(response) > 800 else response,
            "graders": grader_results,
            "passed": passed,
            "score": round(score, 3),
        })

    total = len(task_results)
    passed_count = sum(1 for t in task_results if t["passed"])
    pass_rate = round(passed_count / total, 3) if total else 0.0
    avg_score = round(sum(t["score"] for t in task_results) / total, 3) if total else 0.0
    _now = datetime.datetime.now(datetime.UTC)
    timestamp = _now.isoformat()
    result = {
        "eval": str(eval_path),
        "skill": skill_name,
        "model": model,
        "timestamp": timestamp,
        "summary": {"total": total, "passed": passed_count, "pass_rate": pass_rate, "score": avg_score},
        "tasks": task_results,
    }

    results_dir = eval_dir.parent.parent / _DEFAULT_RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = _now.strftime("%Y%m%dT%H%M%S")
    safe_model = re.sub(r"[^a-zA-Z0-9._-]", "-", model)
    result_file = results_dir / f"{safe_skill_name}-{ts}-{safe_model}.json"
    _tmp = result_file.with_suffix(".tmp")
    _tmp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    os.replace(_tmp, result_file)

    if fmt == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"xanadEval run \u2014 {skill_name}  [{model}]")
        print(f"  {passed_count}/{total} tasks passed  ({pass_rate:.0%})  score: {avg_score:.3f}")
        for t in task_results:
            icon = "\u2713" if t["passed"] else "\u2717"
            print(f"  {icon} {t['id']}")
        print(f"\n  saved: {result_file}")
    return 0 if passed_count == total else 1


# ── grade ─────────────────────────────────────────────────────────────────────


def cmd_grade(eval_path: str, results_path: str, model: str | None, fmt: str) -> int:
    """Re-run graders against an existing results file without re-invoking the model."""
    token = _get_token()
    try:
        spec = _load_spec(eval_path)
    except Exception as e:
        print(f"xanadEval grade: cannot load {eval_path}: {e}", file=sys.stderr)
        return 2
    try:
        prev = json.loads(Path(results_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"xanadEval grade: cannot load results {results_path}: {e}", file=sys.stderr)
        return 2

    graders_spec = spec.get("graders", [])
    has_prompt_graders = any(g.get("type") == "prompt" for g in graders_spec)
    if has_prompt_graders and not token:
        print(
            "xanadEval grade: eval contains prompt graders but GITHUB_TOKEN (or GH_TOKEN) "
            "is not set; re-grading would overwrite existing results with skipped records",
            file=sys.stderr,
        )
        return 2
    run_model = model or prev.get("model", _DEFAULT_MODEL)

    updated: list[dict] = []
    for task in prev.get("tasks", []):
        response = task.get("response", "")
        grader_results = _run_graders(response, graders_spec, run_model, token or "")
        # Re-apply expected_absent checks persisted from the original run
        for saved_g in task.get("graders", []):
            if saved_g.get("type") == "expected_absent":
                pattern = saved_g.get("name", "")
                if pattern:
                    hit = bool(re.search(pattern, response, re.IGNORECASE))
                    grader_results.append({
                        "type": "expected_absent",
                        "name": pattern,
                        "pass": not hit,
                        "score": 0.0 if hit else 1.0,
                    })
        graded = [g for g in grader_results if g.get("pass") is not None]
        passed = bool(graded) and all(g["pass"] for g in graded)
        score = (sum(g["score"] for g in graded) / len(graded)) if graded else 0.0
        updated.append({**task, "graders": grader_results, "passed": passed,
                        "score": round(score, 3)})

    total = len(updated)
    passed_count = sum(1 for t in updated if t["passed"])
    pass_rate = round(passed_count / total, 3) if total else 0.0
    avg_score = round(sum(t["score"] for t in updated) / total, 3) if total else 0.0
    result = {
        **prev,
        "tasks": updated,
        "graded_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "summary": {"total": total, "passed": passed_count, "pass_rate": pass_rate,
                    "score": avg_score},
    }
    _dest = Path(results_path)
    _tmp = _dest.with_suffix(".tmp")
    _tmp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    os.replace(_tmp, _dest)

    if fmt == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"xanadEval grade \u2014 {results_path}")
        print(f"  {passed_count}/{total} passed  ({pass_rate:.0%})  score: {avg_score:.3f}")
    return 0 if passed_count == total else 1
