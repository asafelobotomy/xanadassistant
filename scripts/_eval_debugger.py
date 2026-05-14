"""Debugger agent eval: treatment (full agent prompt) vs control (bare model).

Loads the debugger agent system prompt from agents/debugger.agent.md,
resolves pack tokens from packs/core/tokens.json, then runs each task
from _eval_debugger_tasks.py against both arms. Scores via _eval_debugger_judge.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_FILE  = REPO_ROOT / "agents" / "debugger.agent.md"
_CORE_TOKENS = REPO_ROOT / "packs" / "core" / "tokens.json"

DEFAULT_MODEL = "openai/gpt-4o-mini"
RESULTS_DIR   = REPO_ROOT / "results"


# ── System prompt ─────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    """Return the debugger agent body with pack tokens resolved from core pack."""
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
    """Run all debugger tasks: treatment vs control. Returns full results dict."""
    import _eval_client as _client
    import _eval_debugger_judge as _judge
    import _eval_debugger_tasks as _tasks

    system_prompt = load_system_prompt()
    task_results  = []

    for task in _tasks.DEBUGGER_TASKS:
        req    = task["user_request"]
        t_msgs = [{"role": "system", "content": system_prompt},
                  {"role": "user",   "content": req}]
        c_msgs = [{"role": "user", "content": req}]

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
        "eval":   "debugger",
        "model":  model,
        "tasks":  task_results,
    }


# ── Results display ───────────────────────────────────────────────────────────

_TICK = "\u2713"
_CROSS = "\u2717"
_COL = 28


def _fmt(val: bool | None) -> str:
    if val is None:
        return " \u2014"
    return f" {_TICK}" if val else f" {_CROSS}"


def print_results(data: dict) -> int:
    """Print a results table to stdout. Returns exit code (0 = treatment won)."""
    model = data["model"]
    tasks = data["tasks"]
    header = (
        f"\n=== DEBUGGER EVAL — treatment vs control  (model: {model}) ===\n"
        f"  {'Task':<{_COL}} {'Arm':<12} {'Cau':>3} {'Fix':>3} {'Foc':>3} {'Scr':>4}"
        f"  {'P-tok':>5} {'C-tok':>5} {'ms':>8}"
    )
    print(header)
    print("  " + "\u2500" * (len(header) - 4))

    t_total = c_total = 0
    t_ptok_sum = c_ptok_sum = 0
    n = len(tasks)

    for tr in tasks:
        for arm_key, arm_label in [("treatment", "treatment"), ("control", "control")]:
            arm = tr[arm_key]
            s   = arm["score"]
            sc  = s["score"]
            print(
                f"  {tr['task']:<{_COL}} {arm_label:<12}"
                f"{_fmt(s['cause_identified'])}"
                f"{_fmt(s['fix_prescribed'])}"
                f"{_fmt(s['focused'])}"
                f" {sc:>3}"
                f"  {arm['prompt_tokens']:>5} {arm['completion_tokens']:>5}"
                f" {arm['latency_ms']:>8.0f}"
            )
            if arm_key == "treatment":
                t_total    += sc
                t_ptok_sum += arm["prompt_tokens"]
            else:
                c_total    += sc
                c_ptok_sum += arm["prompt_tokens"]
        print()

    print("  " + "\u2500" * (len(header) - 4))
    t_avg = t_total / n
    c_avg = c_total / n
    delta = t_avg - c_avg
    direction = "treatment better" if delta > 0 else "control better" if delta < 0 else "tied"
    print(f"\n  Treatment avg score: {t_avg:.2f}/3   Control avg score: {c_avg:.2f}/3")
    print(f"  Delta: {delta:+.2f}  ({direction})")
    print(f"  Avg prompt-token overhead per call: {(t_ptok_sum - c_ptok_sum) // n:+d} tokens\n")
    print(f"{n} tasks complete.")
    return 0 if delta >= 0 else 1


# ── Results save ──────────────────────────────────────────────────────────────

def save_results(data: dict) -> Path:
    """Write results JSON to results/eval-debugger-<timestamp>.json."""
    RESULTS_DIR.mkdir(exist_ok=True)
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = RESULTS_DIR / f"eval-debugger-{ts}.json"
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Results saved \u2192 {dest.relative_to(REPO_ROOT)}")
    return dest
