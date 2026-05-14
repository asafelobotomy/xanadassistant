"""Commit agent eval: treatment (full agent prompt) vs control (bare model).

Loads the commit agent system prompt from agents/commit.agent.md,
resolves pack tokens from packs/core/tokens.json, then runs each task
from _eval_commit_tasks.py against both arms. Scores via _eval_commit_judge.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_FILE = REPO_ROOT / "agents" / "commit.agent.md"
_CORE_TOKENS = REPO_ROOT / "packs" / "core" / "tokens.json"

DEFAULT_MODEL = "openai/gpt-4o-mini"
RESULTS_DIR = REPO_ROOT / "results"


# ── System prompt ─────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    """Return the commit agent body with pack tokens resolved from core pack."""
    text = _AGENT_FILE.read_text(encoding="utf-8")
    if text.startswith("---"):
        _, _, after_first = text.partition("---\n")
        _, _, body = after_first.partition("---\n")
    else:
        body = text
    tokens: dict[str, str] = json.loads(_CORE_TOKENS.read_text(encoding="utf-8"))
    for key, value in tokens.items():
        body = body.replace("{{" + key + "}}", value)
    return body.strip()


# ── Eval runner ───────────────────────────────────────────────────────────────

def run(model: str = DEFAULT_MODEL) -> dict:
    """Run all commit tasks: treatment vs control. Returns full results dict."""
    import _eval_client as _client
    import _eval_commit_judge as _judge
    import _eval_commit_tasks as _tasks

    system_prompt = load_system_prompt()
    task_results = []

    for task in _tasks.COMMIT_TASKS:
        msg = task["user_message"]
        t_msgs = [{"role": "system", "content": system_prompt},
                  {"role": "user",   "content": msg}]
        c_msgs = [{"role": "user", "content": msg}]

        t = _client.call(t_msgs, model)
        t_parsed = _judge.parse(t.content)
        t_score  = _judge.score(t_parsed, task)

        c = _client.call(c_msgs, model)
        c_parsed = _judge.parse(c.content)
        c_score  = _judge.score(c_parsed, task)

        task_results.append({
            "task":  task["name"],
            "notes": task["notes"],
            "treatment": {
                "response":          t.content,
                "parsed":            t_parsed,
                "score":             t_score,
                "prompt_tokens":     t.prompt_tokens,
                "completion_tokens": t.completion_tokens,
                "latency_ms":        t.latency_ms,
            },
            "control": {
                "response":          c.content,
                "parsed":            c_parsed,
                "score":             c_score,
                "prompt_tokens":     c.prompt_tokens,
                "completion_tokens": c.completion_tokens,
                "latency_ms":        c.latency_ms,
            },
        })

    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "agent":     "commit",
        "model":     model,
        "tasks":     task_results,
    }


# ── Result display ────────────────────────────────────────────────────────────

def print_results(data: dict) -> int:
    """Print a comparison table to stdout. Returns 1 if treatment never outscores control."""
    tasks = data["tasks"]
    hdr = (f"  {'Task':<28} {'Arm':<12} {'Type':<10} "
           f"{'Fmt':>3} {'Typ':>3} {'Qly':>3} {'Scr':>3}  "
           f"{'P-tok':>5} {'C-tok':>5}  {'ms':>6}")
    div = "  " + "─" * (len(hdr) - 2)
    print(f"\n=== COMMIT EVAL — treatment vs control  (model: {data['model']}) ===")
    print(hdr)
    print(div)

    t_scores: list[int] = []
    c_scores: list[int] = []

    for entry in tasks:
        for arm in ("treatment", "control"):
            d   = entry[arm]
            sc  = d["score"]
            typ = d["parsed"].get("type") or "—"
            fv  = "✓" if sc["format_valid"]    else "✗"
            tc  = "✓" if sc["type_correct"]    else ("—" if sc["type_correct"] is None else "✗")
            qc  = "✓" if sc["quality_correct"] else "✗"
            pts = d["prompt_tokens"]
            cts = d["completion_tokens"]
            lat = d["latency_ms"]
            print(f"  {entry['task']:<28} {arm:<12} {typ:<10} "
                  f"{fv:>3} {tc:>3} {qc:>3} {sc['score']:>3}  "
                  f"{pts:>5} {cts:>5}  {lat:>6.0f}")
            if arm == "treatment":
                t_scores.append(sc["score"])
            else:
                c_scores.append(sc["score"])
        print()

    t_avg = sum(t_scores) / len(t_scores) if t_scores else 0.0
    c_avg = sum(c_scores) / len(c_scores) if c_scores else 0.0
    delta = t_avg - c_avg
    avg_overhead = (
        sum(e["treatment"]["prompt_tokens"] - e["control"]["prompt_tokens"]
            for e in tasks) // len(tasks)
    )

    print(div)
    print(f"\n  Treatment avg score: {t_avg:.2f}/3   Control avg score: {c_avg:.2f}/3")
    verdict = "treatment better" if delta > 0 else ("no advantage" if delta == 0 else "treatment WORSE")
    print(f"  Delta: {delta:+.2f}  ({verdict})")
    print(f"  Avg prompt-token overhead per call: {avg_overhead:+d} tokens")
    print(f"\n{len(tasks)} tasks complete.")
    return 0 if delta >= 0 else 1


def save_results(data: dict) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / f"eval-commit-{ts}.json"
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    try:
        display = out.relative_to(REPO_ROOT)
    except ValueError:
        display = out
    print(f"\n  Results saved → {display}")
    return out
