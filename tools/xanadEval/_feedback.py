"""Feedback analysis commands for xanadEval: quality, dev.

Requires GITHUB_TOKEN or GH_TOKEN. Uses bind_api() so that
mock.patch("xanadEval._call_model") is intercepted at runtime.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import _common
from _common import (
    _QUALITY_DIMENSIONS, _extract_first_json_object, _get_token, _read,
)

# ── bind_api ──────────────────────────────────────────────────────────────────
# xanadEval.py binds itself here so mock.patch("xanadEval._call_model") works
# for tests that call cmd_quality / cmd_dev.

_api: object = _common

def bind_api(m: object) -> None:
    """Bind the xanadEval wrapper module as the runtime API source."""
    global _api
    _api = m


# ── quality ───────────────────────────────────────────────────────────────────

_QUALITY_PROMPT = """\
You are a Copilot skill reviewer. Score this SKILL.md on 5 dimensions (each 0.0\u20131.0):
1. clarity \u2014 Is the purpose, scope, and steps clearly written with unambiguous language?
2. completeness \u2014 Are all standard sections present (When to use, When NOT to use, Steps/Modules, Verify)?
3. trigger_precision \u2014 Are trigger phrases specific enough to avoid false-positive invocations?
4. scope_coverage \u2014 Does the skill cover the full breadth of its stated purpose without gaps?
5. anti_patterns \u2014 Absence of problems (vague language, over-broad triggers, missing guardrails). 1.0 = none found.

SKILL.md:
```
{content}
```

Return ONLY valid JSON \u2014 no prose before or after:
{{"clarity":<f>,"completeness":<f>,"trigger_precision":<f>,"scope_coverage":<f>,"anti_patterns":<f>,"overall":<f>,"summary":"<one sentence>"}}
"""


def cmd_quality(path: str, model: str, fmt: str) -> int:
    """LLM-as-judge: score a SKILL.md on 5 quality dimensions via GitHub Models."""
    token = _get_token()
    if not token:
        print("xanadEval quality: GITHUB_TOKEN (or GH_TOKEN) is not set", file=sys.stderr)
        return 2

    content = _read(path)
    try:
        reply = _api._call_model(  # type: ignore[union-attr]
            [{"role": "user", "content": _QUALITY_PROMPT.format(content=content[:8000])}],
            model, token,
        )
    except RuntimeError as e:
        print(f"xanadEval quality: model error \u2014 {e}", file=sys.stderr)
        return 1

    scores = _extract_first_json_object(reply)
    if scores is None:
        print(f"xanadEval quality: could not parse JSON from response:\n{reply[:300]}",
              file=sys.stderr)
        return 1
    try:
        summary = str(scores.pop("summary", ""))
    except (TypeError, ValueError) as e:
        print(f"xanadEval quality: JSON parse error \u2014 {e}", file=sys.stderr)
        return 1

    _bad = [d for d in _QUALITY_DIMENSIONS + ["overall"]
            if not isinstance(scores.get(d), (int, float))]
    if _bad:
        print(f"xanadEval quality: non-numeric score fields: {', '.join(_bad)}",
              file=sys.stderr)
        return 1

    if fmt == "json":
        print(json.dumps({"path": path, "model": model, "scores": scores,
                          "summary": summary}, indent=2))
    else:
        label = Path(path).name
        print(f"xanadEval quality \u2014 {label}  [{model}]")
        for dim in _QUALITY_DIMENSIONS:
            score = float(scores.get(dim, 0))
            filled = int(score * 10)
            bar = "\u2588" * filled + "\u2591" * (10 - filled)
            print(f"  {dim:<20} {bar}  {score:.2f}")
        overall = float(scores.get(
            "overall",
            sum(float(scores.get(d, 0)) for d in _QUALITY_DIMENSIONS) / len(_QUALITY_DIMENSIONS),
        ))
        print(f"\n  overall: {overall:.2f}")
        if summary:
            print(f"  {summary}")
    return 0


# ── dev ───────────────────────────────────────────────────────────────────────

_DEV_PROMPT = """\
You are a Copilot skill expert. Analyse this SKILL.md and return a JSON object with:
- Scores for clarity, completeness, trigger_precision, scope_coverage, anti_patterns (each 0.0\u20131.0)
- overall score (0.0\u20131.0)
- top 3 concrete, actionable "improvements" (list of strings)
- One-sentence "summary" of the most important issue

SKILL.md:
```
{content}
```

Return ONLY valid JSON:
{{"clarity":<f>,"completeness":<f>,"trigger_precision":<f>,"scope_coverage":<f>,"anti_patterns":<f>,"overall":<f>,"improvements":["...","...","..."],"summary":"..."}}
"""


def cmd_dev(path: str, model: str, fmt: str) -> int:
    """Analyse a SKILL.md and surface the top improvement suggestions."""
    token = _get_token()
    if not token:
        print("xanadEval dev: GITHUB_TOKEN (or GH_TOKEN) is not set", file=sys.stderr)
        return 2

    content = _read(path)
    try:
        reply = _api._call_model(  # type: ignore[union-attr]
            [{"role": "user", "content": _DEV_PROMPT.format(content=content[:8000])}],
            model, token,
        )
    except RuntimeError as e:
        print(f"xanadEval dev: model error \u2014 {e}", file=sys.stderr)
        return 1

    analysis = _extract_first_json_object(reply)
    if analysis is None:
        print(f"xanadEval dev: could not parse JSON from response:\n{reply[:300]}",
              file=sys.stderr)
        return 1

    _bad = [d for d in _QUALITY_DIMENSIONS + ["overall"]
            if not isinstance(analysis.get(d), (int, float))]
    if _bad:
        print(f"xanadEval dev: non-numeric score fields: {', '.join(_bad)}",
              file=sys.stderr)
        return 1

    overall = float(analysis.get("overall", 0))
    improvements = analysis.get("improvements", [])
    summary = str(analysis.get("summary", ""))

    if fmt == "json":
        print(json.dumps({"path": path, "model": model, "analysis": analysis}, indent=2))
    else:
        label = Path(path).name
        print(f"xanadEval dev \u2014 {label}  [{model}]")
        for dim in _QUALITY_DIMENSIONS:
            score = float(analysis.get(dim, 0))
            filled = int(score * 10)
            bar = "\u2588" * filled + "\u2591" * (10 - filled)
            print(f"  {dim:<20} {bar}  {score:.2f}")
        print(f"\n  overall: {overall:.2f}")
        if summary:
            print(f"  {summary}")
        if improvements:
            print("\n  improvements:")
            for i, imp in enumerate(improvements, 1):
                print(f"    {i}. {imp}")
        if overall >= 0.90:
            print("\n  \u2713 skill is already high quality")
        else:
            print(f"\n  re-run after addressing suggestions: xanadEval dev {path}")
    return 0
