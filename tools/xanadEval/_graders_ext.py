"""Extended grader types for xanadEval: trigger, file, diff, code, action_sequence, tool_constraint.

Internal implementation detail — import ``xanadEval`` directly, not this module.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from _common import _parse_frontmatter

# ── Trigger grader helpers ────────────────────────────────────────────────────

_TRIGGER_STOP_WORDS = frozenset({
    "the", "and", "for", "with", "this", "that", "from", "into", "your", "you",
    "are", "was", "were", "what", "where", "how", "why", "not", "can", "should",
    "using", "about", "have", "has", "had", "but", "all", "any", "too", "out",
    "get", "let", "will", "its", "use", "may", "per", "via", "set", "run",
})


def _tokenize(text: str) -> list[str]:
    """Lowercase tokens ≥3 chars, excluding stop words."""
    return [
        t for t in re.findall(r"[a-z][a-z0-9_-]*", text.lower())
        if len(t) >= 3 and t not in _TRIGGER_STOP_WORDS
    ]


def _parse_use_for_phrases(description: str) -> list[str]:
    """Extract USE FOR: / WHEN: / TRIGGERS: phrases from a skill description."""
    upper = description.upper()
    section = ""
    for marker, offset in (("USE FOR:", 8), ("WHEN:", 5), ("TRIGGERS:", 9)):
        idx = upper.find(marker)
        if idx != -1:
            section = description[idx + offset:]
            break
    if not section:
        return []

    # Stop at DO NOT USE FOR: or similar negative section
    for stop in ("DO NOT USE FOR:", "DO NOT USE", "WHEN NOT", "INVOKES:"):
        stop_idx = section.upper().find(stop)
        if stop_idx >= 0:
            section = section[:stop_idx]

    # Quoted phrases take priority
    quoted = re.findall(r'["\u201C\u201D]([^"\u201C\u201D]+)["\u201C\u201D]', section)
    if quoted:
        return [q.strip() for q in quoted if q.strip()]

    # Fall back: comma/period-separated
    parts = re.split(r"[,.]", section)
    return [p.strip() for p in parts if len(p.strip()) >= 3]


# ── _grade_trigger ─────────────────────────────────────────────────────────────


def _grade_trigger(
    prompt: str,
    config: dict,
    eval_dir: Path | None = None,
) -> tuple[bool, float, dict]:
    """Heuristic grader: score prompt-to-skill relevance.

    Config keys:
      - ``skill_path``  — path to SKILL.md or its directory (required)
      - ``mode``        — ``positive`` (score >= threshold passes) or
                          ``negative`` (score < threshold passes)
      - ``threshold``   — float 0.0–1.0, default 0.6

    Returns ``(passed, score, details)`` where *details* carries diagnostic info
    or an ``error`` key on configuration/file errors.
    """
    skill_path_cfg = str(config.get("skill_path", "")).strip()
    if not skill_path_cfg:
        return False, 0.0, {"error": "trigger grader: 'skill_path' is required"}

    mode = str(config.get("mode", "")).lower().strip()
    if mode not in ("positive", "negative"):
        return False, 0.0, {
            "error": f"trigger grader: mode must be 'positive' or 'negative', got {mode!r}"
        }

    try:
        threshold = float(config.get("threshold", 0.6))
    except (TypeError, ValueError):
        threshold = 0.6
    if not 0.0 <= threshold <= 1.0:
        return False, 0.0, {"error": "trigger grader: threshold must be between 0.0 and 1.0"}

    # Resolve skill_path: try as-is (absolute), then relative to eval_dir
    skill_path = Path(skill_path_cfg)
    if not skill_path.is_absolute() and eval_dir is not None:
        skill_path = (eval_dir / skill_path).resolve()
    if skill_path.is_dir():
        skill_path = skill_path / "SKILL.md"

    try:
        skill_content = skill_path.read_text(encoding="utf-8")
    except OSError as e:
        return False, 0.0, {"error": f"trigger grader: cannot read {skill_path}: {e}"}

    fm = _parse_frontmatter(skill_content)
    name = fm.get("name", skill_path.parent.name)
    description = fm.get("description", "")

    # Trim description at DO NOT USE FOR: before keyword extraction
    do_not_idx = description.upper().find("DO NOT USE FOR:")
    clean_desc = description[:do_not_idx].strip() if do_not_idx >= 0 else description

    # Body = everything after the closing --- fence
    parts = skill_content.split("---\n", 2)
    body = parts[2] if len(parts) == 3 else skill_content

    # Build keyword set from name + clean description + body
    keywords: set[str] = set(_tokenize(f"{name} {clean_desc} {body}"))

    # Augment with USE FOR phrase tokens
    phrases = _parse_use_for_phrases(description)
    for phrase in phrases:
        keywords.update(_tokenize(phrase))

    if not keywords:
        return False, 0.0, {
            "error": f"trigger grader: no usable keywords found in {skill_path}"
        }

    # ── Score the prompt ──────────────────────────────────────────────────────
    prompt_tokens = _tokenize(prompt)
    if not prompt_tokens:
        passed = mode == "negative"
        return passed, 0.0, {
            "mode": mode, "threshold": threshold, "skill_path": skill_path_cfg,
            "matched_keywords": [], "matched_count": 0,
            "keyword_count": len(keywords), "phrase_score": 0.0,
        }

    unique_prompt = set(prompt_tokens)
    matched = [t for t in unique_prompt if t in keywords]
    token_score = len(matched) / len(unique_prompt)

    # Phrase score: exact substring → 1.0; else token Jaccard
    phrase_score = 0.0
    prompt_lower = prompt.lower()
    for phrase in phrases:
        phrase_lower = phrase.lower().strip()
        if not phrase_lower:
            continue
        if phrase_lower in prompt_lower:
            phrase_score = 1.0
            break
        phrase_toks = _tokenize(phrase)
        if not phrase_toks:
            continue
        hits = sum(1 for t in phrase_toks if t in unique_prompt)
        candidate = hits / len(phrase_toks)
        if candidate > phrase_score:
            phrase_score = candidate

    score = max(token_score, phrase_score)
    passed = score >= threshold if mode == "positive" else score < threshold

    return passed, round(score, 3), {
        "mode": mode,
        "threshold": threshold,
        "skill_path": skill_path_cfg,
        "matched_keywords": sorted(matched),
        "matched_count": len(matched),
        "keyword_count": len(keywords),
        "phrase_score": round(phrase_score, 3),
    }


# ── _grade_file ───────────────────────────────────────────────────────────────


def _grade_file(
    config: dict,
    workspace: Path | None = None,
) -> tuple[bool, float, str]:
    """Validate file existence and content patterns in a workspace directory.

    Config keys:
      - ``workspace``        — base directory (falls back to config key, then cwd)
      - ``must_exist``       — list of relative paths that must be present
      - ``must_not_exist``   — list of relative paths that must be absent
      - ``content_patterns`` — list of {path, must_match, must_not_match} checks

    Partial scoring: ``passed_checks / total_checks``.
    All paths must be relative and must not escape the workspace via ``..``.
    """
    ws = workspace or Path(str(config.get("workspace", "."))).resolve()

    def _safe(p: str) -> Path | None:
        fp = Path(p)
        if fp.is_absolute() or ".." in fp.parts:
            return None  # reject unsafe paths
        return ws / fp

    checks: list[bool] = []
    errors: list[str] = []

    for path_str in config.get("must_exist", []):
        resolved = _safe(str(path_str))
        if resolved is None:
            errors.append(f"unsafe path rejected: {path_str!r}")
            checks.append(False)
        else:
            checks.append(resolved.exists())

    for path_str in config.get("must_not_exist", []):
        resolved = _safe(str(path_str))
        if resolved is None:
            errors.append(f"unsafe path rejected: {path_str!r}")
            checks.append(False)
        else:
            checks.append(not resolved.exists())

    for cp in config.get("content_patterns", []):
        path_str = str(cp.get("path", ""))
        resolved = _safe(path_str)
        n_pats = len(cp.get("must_match", [])) + len(cp.get("must_not_match", []))
        if resolved is None:
            errors.append(f"unsafe path rejected: {path_str!r}")
            checks.extend([False] * (1 + n_pats))
            continue

        exists = resolved.exists()
        checks.append(exists)
        if not exists:
            checks.extend([False] * n_pats)
            continue

        try:
            content = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError:
            checks.extend([False] * n_pats)
            continue

        for pat in cp.get("must_match", []):
            checks.append(bool(re.search(str(pat), content)))
        for pat in cp.get("must_not_match", []):
            checks.append(not bool(re.search(str(pat), content)))

    if not checks:
        return (
            False, 0.0,
            "file grader: at least one of must_exist/must_not_exist/content_patterns is required",
        )

    passed = all(checks)
    score = round(sum(1 for c in checks if c) / len(checks), 3)
    summary = f"{sum(checks)}/{len(checks)} checks passed"
    feedback = ("; ".join(errors) + " — " if errors else "") + summary
    return passed, score, feedback


# ── _grade_diff ───────────────────────────────────────────────────────────────


def _grade_diff(
    config: dict,
    workspace: Path | None = None,
    context_dir: Path | None = None,
) -> tuple[bool, float, str]:
    """Compare workspace files against expected snapshots or line fragments.

    Config keys:
      - ``expected_files`` — list of {path, snapshot?, contains?} (required)
      - ``workspace``      — base directory for file paths (default: cwd)
      - ``context_dir``    — base for resolving snapshot paths (default: workspace)

    Contains prefix rules:
      ``+fragment`` or bare ``fragment`` → must appear;
      ``-fragment``                      → must be absent.

    Partial scoring: ``passed_checks / total_checks``.
    """
    ws = workspace or Path(str(config.get("workspace", "."))).resolve()
    ctx = context_dir or Path(str(config.get("context_dir", str(ws)))).resolve()

    def _safe_ws(p: str) -> Path | None:
        fp = Path(p)
        return None if (fp.is_absolute() or ".." in fp.parts) else ws / fp

    def _safe_ctx(p: str) -> Path | None:
        fp = Path(p)
        return None if (fp.is_absolute() or ".." in fp.parts) else ctx / fp

    checks: list[bool] = []
    errors: list[str] = []

    for entry in config.get("expected_files", []):
        path_str = str(entry.get("path", ""))
        resolved = _safe_ws(path_str)
        if resolved is None:
            errors.append(f"unsafe path rejected: {path_str!r}")
            checks.append(False)
            continue

        exists = resolved.exists()
        checks.append(exists)
        if not exists:
            n = bool(entry.get("snapshot")) + len(entry.get("contains", []))
            checks.extend([False] * n)
            continue

        try:
            actual = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError:
            n = bool(entry.get("snapshot")) + len(entry.get("contains", []))
            checks.extend([False] * n)
            continue

        if entry.get("snapshot"):
            snap = _safe_ctx(str(entry["snapshot"]))
            if snap is None:
                errors.append(f"unsafe snapshot path rejected: {entry['snapshot']!r}")
                checks.append(False)
            else:
                try:
                    expected = snap.read_text(encoding="utf-8", errors="replace")
                    checks.append(actual == expected)
                except OSError:
                    checks.append(False)

        for fragment in entry.get("contains", []):
            frag = str(fragment)
            if frag.startswith("+"):
                checks.append(frag[1:] in actual)
            elif frag.startswith("-"):
                checks.append(frag[1:] not in actual)
            else:
                checks.append(frag in actual)

    if not checks:
        return False, 0.0, "diff grader: 'expected_files' must be a non-empty list"

    passed = all(checks)
    score = round(sum(1 for c in checks if c) / len(checks), 3)
    summary = f"{sum(checks)}/{len(checks)} diff checks passed"
    feedback = ("; ".join(errors) + " — " if errors else "") + summary
    return passed, score, feedback


# ── _grade_code ───────────────────────────────────────────────────────────────

# Restricted builtins available inside code grader assertions.
_CODE_SAFE_GLOBALS: dict = {
    "__builtins__": {},
    "len": len, "any": any, "all": all,
    "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "set": set,
    "min": min, "max": max, "abs": abs, "round": round,
    "re": re,
}


def _grade_code(
    response: str,
    config: dict,
    ctx: dict | None = None,
) -> tuple[bool, float, str]:
    """Assertion-based grader: evaluate Python expressions against response context.

    Config keys:
      - ``assertions`` — list of Python expression strings (required)

    Available context variables: ``output`` (str), ``outcome`` (dict),
    ``transcript`` (list), ``tool_calls`` (list), ``errors`` (list),
    ``duration_ms`` (int).

    Scoring: ``passed_assertions / total_assertions``.

    Generator expressions are not supported (restriction of eval in a restricted
    scope). Use explicit list comprehensions or ``any``/``all`` with a list literal.
    """
    assertions = list(config.get("assertions", []))
    if not assertions:
        return False, 0.0, "code grader: 'assertions' must be a non-empty list"

    _ctx = ctx or {}
    ns = dict(_CODE_SAFE_GLOBALS)
    ns.update({
        "output": response,
        "outcome": _ctx.get("outcome", {}),
        "transcript": _ctx.get("transcript", []),
        "tool_calls": _ctx.get("tool_calls", []),
        "errors": _ctx.get("errors", []),
        "duration_ms": _ctx.get("duration_ms", 0),
    })

    passed_count = 0
    failures: list[str] = []
    for expr in assertions:
        try:
            result = eval(compile(str(expr), "<assertion>", "eval"), ns)  # noqa: S307
            if result:
                passed_count += 1
            else:
                failures.append(f"FAIL: {expr!r}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"ERROR in {expr!r}: {e}")

    total = len(assertions)
    passed = passed_count == total
    score = round(passed_count / total, 3)
    feedback = "All assertions passed" if passed else "; ".join(failures)
    return passed, score, feedback


# ── _grade_action_sequence ─────────────────────────────────────────────────────


def _grade_action_sequence(
    config: dict,
    ctx: dict | None = None,
) -> tuple[bool, float, str]:
    """Validate tool call sequences against expected actions.

    Config keys:
      - ``expected_actions`` — list of tool name strings (required)
      - ``matching_mode``    — ``exact_match``, ``in_order_match``, or
                               ``any_order_match`` (required)

    Actual actions are read from ``ctx["tool_calls"]``, which should be a list of
    strings or dicts with a ``"tool"`` key.

    Scoring: F1 score (harmonic mean of precision and recall).
    """
    expected = [str(a) for a in config.get("expected_actions", [])]
    if not expected:
        return False, 0.0, "action_sequence grader: 'expected_actions' must be non-empty"

    mode = str(config.get("matching_mode", "in_order_match")).lower()
    if mode not in ("exact_match", "in_order_match", "any_order_match"):
        return False, 0.0, f"action_sequence grader: unknown matching_mode {mode!r}"

    raw = list((ctx or {}).get("tool_calls", []))
    if not raw:
        return False, 0.0, "action_sequence grader: no tool_calls in context"

    actual = [str(a.get("tool", a)) if isinstance(a, dict) else str(a) for a in raw]

    if mode == "exact_match":
        pairs = list(zip(actual, expected))
        tp = sum(1 for a, e in pairs if a == e)
        matched = actual == expected
    elif mode == "in_order_match":
        tp = 0
        ai = 0
        for e in expected:
            while ai < len(actual):
                if actual[ai] == e:
                    tp += 1
                    ai += 1
                    break
                ai += 1
        matched = tp == len(expected)
    else:  # any_order_match
        exp_c = Counter(expected)
        act_c = Counter(actual)
        tp = sum(min(v, act_c[k]) for k, v in exp_c.items())
        matched = all(act_c[k] >= v for k, v in exp_c.items())

    precision = tp / len(actual) if actual else 0.0
    recall = tp / len(expected) if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return matched, round(f1, 3), (
        f"precision={precision:.3f} recall={recall:.3f} f1={f1:.3f}"
        f" tp={tp} expected={len(expected)} actual={len(actual)}"
    )


# ── _grade_tool_constraint ─────────────────────────────────────────────────────


def _grade_tool_constraint(
    config: dict,
    ctx: dict | None = None,
) -> tuple[bool, float, str]:
    """Validate which tools were used or avoided.

    Config keys:
      - ``expect_tools`` — list of tool specs that MUST have been called
      - ``reject_tools`` — list of tool specs that MUST NOT have been called

    At least one of ``expect_tools`` / ``reject_tools`` must be non-empty.

    Each tool spec is a dict with:
      - ``tool``            — regex matched against tool name (required)
      - ``command_pattern`` — regex on the ``command`` argument (optional)
      - ``skill_pattern``   — regex on the ``skill`` argument (optional)
      - ``path_pattern``    — regex on the ``path`` argument (optional)

    Actual tool calls come from ``ctx["tool_calls"]`` — a list of strings or dicts
    with a ``"tool"`` key plus optional argument keys.

    Scoring: ``passed_checks / total_checks``.
    """
    expect = list(config.get("expect_tools", []))
    reject = list(config.get("reject_tools", []))
    max_calls = config.get("max_calls")
    if not expect and not reject and max_calls is None:
        return (
            False, 0.0,
            "tool_constraint grader: at least one of expect_tools/reject_tools/max_calls is required",
        )

    raw = list((ctx or {}).get("tool_calls", []))

    def _match(spec: dict, call: dict | str) -> bool:
        if isinstance(call, str):
            call = {"tool": call}
        if not re.search(str(spec.get("tool", "")), str(call.get("tool", "")), re.IGNORECASE):
            return False
        for cfg_key, call_key in (
            ("command_pattern", "command"),
            ("skill_pattern", "skill"),
            ("path_pattern", "path"),
        ):
            pattern = spec.get(cfg_key)
            if pattern and not re.search(str(pattern), str(call.get(call_key, ""))):
                return False
        return True

    checks: list[bool] = []
    for spec in expect:
        checks.append(any(_match(spec, c) for c in raw))
    for spec in reject:
        checks.append(not any(_match(spec, c) for c in raw))
    if max_calls is not None:
        try:
            checks.append(len(raw) <= int(max_calls))
        except (TypeError, ValueError):
            pass

    if not checks:
        return False, 0.0, "tool_constraint grader: no checks derived from config"

    passed = all(checks)
    score = round(sum(1 for c in checks if c) / len(checks), 3)
    return passed, score, f"{sum(checks)}/{len(checks)} constraint checks passed"


# ── _grade_script ──────────────────────────────────────────────────────────────────────────────


def _grade_script(
    config: dict,
    *,
    response: str = "",
    ctx: dict | None = None,
) -> tuple[bool, float, str]:
    """External script grader: serialise ctx as JSON to stdin, parse JSON from stdout.

    Config keys:
      - ``command``  — required executable name or path
      - ``args``     — list of additional arguments (default: [])
      - ``timeout``  — max execution time in seconds (default: 30)

    The script receives a JSON object via stdin with keys: ``response``, ``output``,
    ``transcript``, ``tool_calls``, ``errors``, ``duration_ms``.  If stdout is valid JSON with
    ``score`` and ``passed`` keys those values are used; otherwise exit code 0 = pass (1.0).

    Expected stdout JSON: ``{"score": float, "passed": bool, "message": str}``.
    """
    command = str(config.get("command", "")).strip()
    if not command:
        return False, 0.0, "script grader: 'command' is required"
    args = [str(a) for a in config.get("args", [])]
    try:
        timeout = int(config.get("timeout", 30))
    except (TypeError, ValueError):
        return False, 0.0, "script grader: 'timeout' must be an integer"
    _ctx = ctx or {}
    payload = json.dumps({
        "response": response,
        "output": _ctx.get("output", ""),
        "transcript": _ctx.get("transcript", []),
        "tool_calls": _ctx.get("tool_calls", []),
        "errors": _ctx.get("errors", []),
        "duration_ms": _ctx.get("duration_ms", 0),
    })
    try:
        result = subprocess.run(
            [command] + args,
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, 0.0, f"script grader: command not found: {command!r}"
    except subprocess.TimeoutExpired:
        return False, 0.0, f"script grader: timed out after {timeout}s"
    except OSError as e:
        return False, 0.0, f"script grader: {e}"
    stdout = (result.stdout or "").strip()
    try:
        out = json.loads(stdout) if stdout else {}
        if isinstance(out, dict) and "score" in out:
            score = max(0.0, min(1.0, float(out["score"])))
            passed = bool(out.get("passed", score >= 0.5))
            return passed, round(score, 3), str(out.get("message", ""))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    passed = result.returncode == 0
    feedback = (stdout or (result.stderr or "").strip())[:500]
    return passed, 1.0 if passed else 0.0, feedback


# ── _grade_human ──────────────────────────────────────────────────────────────────────────────


def _grade_human(
    config: dict,
    *,
    response: str = "",
    ctx: dict | None = None,
) -> tuple[bool | None, float | None, dict]:
    """Human-in-the-loop grader: returns a pending marker with criteria for review.

    This grader always returns ``pass=None, score=None`` — scoring must be resolved
    externally (e.g. via the ``workspace_grade_human`` MCP tool).

    Config keys:
      - ``criteria``     — list of criterion strings to display to the reviewer
      - ``instructions`` — free-text instructions for the reviewer (optional)
    """
    criteria = list(config.get("criteria", []))
    instructions = str(config.get("instructions", ""))
    payload: dict = {"pending": True, "criteria": criteria}
    if instructions:
        payload["instructions"] = instructions
    return None, None, payload


# ── _grade_skill_invocation ──────────────────────────────────────────────────────────────────


def _grade_skill_invocation(
    config: dict,
    *,
    response: str = "",
    ctx: dict | None = None,
) -> tuple[bool, float, str]:
    """Validate which skills or agents were invoked during execution.

    Config keys:
      - ``required_skills``  — list of skill names that MUST have been invoked
      - ``forbidden_skills`` — list of skill names that MUST NOT have been invoked
      - ``mode``             — ``exact_match``, ``in_order``, or ``any_order`` (default: ``any_order``)
      - ``allow_extra``      — whether extra invocations beyond required are ok (default: ``True``)

    Actual invocations are read from ``ctx["skill_invocations"]`` — a list of
    skill name strings written by the agent runner or MCP interceptor.

    Scoring: F1 score of required skills; ``allow_extra: false`` penalises extra calls.
    Forbidden invocations are a hard fail (score 0.0).
    """
    required = [str(s) for s in config.get("required_skills", [])]
    forbidden = [str(s) for s in config.get("forbidden_skills", [])]
    if not required and not forbidden:
        return (
            False, 0.0,
            "skill_invocation grader: required_skills or forbidden_skills is required",
        )
    mode = str(config.get("mode", "any_order")).lower()
    if mode not in ("exact_match", "in_order", "any_order"):
        return False, 0.0, f"skill_invocation grader: unknown mode {mode!r}"
    allow_extra = bool(config.get("allow_extra", True))

    actual = [str(s) for s in list((ctx or {}).get("skill_invocations", []))]

    forbidden_hit = [s for s in actual if s in forbidden]
    if forbidden_hit:
        return False, 0.0, f"skill_invocation grader: forbidden skills invoked: {forbidden_hit}"

    if not required:
        return True, 1.0, "no required skills; 0 forbidden violations"

    if mode == "exact_match":
        tp = sum(1 for a, e in zip(actual, required) if a == e)
        matched = actual == required
    elif mode == "in_order":
        tp = 0
        ai = 0
        for e in required:
            while ai < len(actual):
                if actual[ai] == e:
                    tp += 1
                    ai += 1
                    break
                ai += 1
        matched = tp == len(required)
    else:  # any_order
        req_c = Counter(required)
        act_c = Counter(actual)
        tp = sum(min(v, act_c[k]) for k, v in req_c.items())
        matched = all(act_c[k] >= v for k, v in req_c.items())

    precision = tp / len(actual) if actual else 0.0
    recall = tp / len(required)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    if not allow_extra and len(actual) > len(required):
        f1 = round(f1 * (len(required) / len(actual)), 3)
        matched = False
    return matched, round(f1, 3), (
        f"precision={precision:.3f} recall={recall:.3f} f1={f1:.3f}"
        f" tp={tp} required={len(required)} actual={len(actual)}"
    )
