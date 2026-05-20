"""Shared helpers, constants, model integration, and graders for xanadEval.

Internal implementation detail — import ``xanadEval`` directly, not this module.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

TOKEN_BUDGET: int = 16_000
_CHARS_PER_TOKEN: int = 4  # fallback when tiktoken is unavailable

try:
    import tiktoken as _tiktoken
    _TK_ENC = _tiktoken.get_encoding("cl100k_base")
except ImportError:
    _tiktoken = None  # type: ignore[assignment]
    _TK_ENC = None

try:
    import yaml as _yaml
except ImportError:
    _yaml = None  # type: ignore[assignment]

_GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_RESULTS_DIR = ".xanadEval"
_QUALITY_DIMENSIONS = [
    "clarity", "completeness", "trigger_precision", "scope_coverage", "anti_patterns",
]

# ── bind_api ──────────────────────────────────────────────────────────────────
# xanadEval.py calls bind_api(sys.modules["xanadEval"]) after import so that
# mock.patch("xanadEval._call_model") is intercepted by _grade_prompt_judge here.

_api: object = None


def bind_api(m: object) -> None:
    """Bind the xanadEval wrapper module as the runtime API source."""
    global _api
    _api = m


# ── Helpers ───────────────────────────────────────────────────────────────────


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"xanadEval: file not found: {path}", file=sys.stderr)
    except UnicodeDecodeError:
        print(f"xanadEval: file is not valid UTF-8: {path}", file=sys.stderr)
    except OSError as e:
        print(f"xanadEval: cannot read {path}: {e}", file=sys.stderr)
    sys.exit(2)


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Return key/value pairs from YAML frontmatter (normalises BOM and CRLF)."""
    content = content.lstrip("\ufeff").replace("\r\n", "\n")
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, _, rest = line.partition(":")
            result[key.strip()] = rest.strip().strip("\"'")
    return result


def _count_tokens(content: str) -> int:
    """Return BPE token count via tiktoken (cl100k_base) or chars/4 fallback."""
    if _TK_ENC is not None:
        return len(_TK_ENC.encode(content))
    return len(content) // _CHARS_PER_TOKEN


def _yaml_str(value: str) -> str:
    """Escape a string for safe use as a YAML double-quoted scalar."""
    v = value.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + v.replace("\n", "\\n").replace("\r", "\\r") + '"'


def _max_nesting_depth(content: str) -> int:
    """Maximum list nesting depth; 0 when no list items are present."""
    if not re.search(r"^[ ]*[-*]|^\d+\.", content, re.MULTILINE):
        return 0
    depths = [
        len(m.group(1)) // 2
        for m in re.finditer(r"^( +)[-*\d]", content, re.MULTILINE)
    ]
    return max(depths, default=0) + 1


# ── GitHub Models integration ─────────────────────────────────────────────────


def _get_token() -> str | None:
    """Return the first available GitHub token from the environment."""
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _call_model(messages: list[dict], model: str, token: str) -> str:
    """POST to GitHub Models (OpenAI-compatible) and return the assistant reply."""
    payload = json.dumps({"model": model, "messages": messages}).encode()
    req = urllib.request.Request(
        _GITHUB_MODELS_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:200]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response from API: {e}") from e
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected response format: {e}") from e


def _load_spec(path: str) -> dict:
    """Load an eval spec (YAML preferred when PyYAML is available, else JSON)."""
    text = Path(path).read_text(encoding="utf-8")
    if _yaml is not None:
        result = _yaml.safe_load(text)
    else:
        result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError(
            f"eval spec must be a mapping, got {type(result).__name__}"
        )
    return result


def _load_tasks(eval_dir: Path, task_refs: list) -> list[dict]:
    """Expand task references (glob strings or inline dicts) into task dicts."""
    tasks: list[dict] = []
    for ref in task_refs:
        if isinstance(ref, dict):
            tasks.append(ref)
        elif isinstance(ref, str):
            ref_path = Path(ref)
            if ref_path.is_absolute() or ".." in ref_path.parts:
                raise ValueError(
                    f"Task ref {ref!r} is not allowed: paths must be relative "
                    f"and must not escape the eval directory"
                )
            for fp in sorted(eval_dir.glob(ref)):
                raw = fp.read_text(encoding="utf-8")
                parsed = _yaml.safe_load(raw) if _yaml else json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError(
                        f"{fp.name}: expected a task mapping, got {type(parsed).__name__}"
                    )
                tasks.append(parsed)
    return tasks


def _extract_first_json_object(text: str) -> dict | None:
    """Return the first valid JSON object found in *text*, or None.

    Uses ``json.JSONDecoder.raw_decode`` so that ``}`` characters inside JSON
    strings are handled correctly.  Scans past malformed candidates — a reply
    like ``{bad} {"score": 1}`` correctly returns the second object.
    """
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(text):
        start = text.find("{", pos)
        if start == -1:
            return None
        try:
            obj, _ = decoder.raw_decode(text, start)
            if isinstance(obj, dict):
                return obj
            pos = start + 1
        except json.JSONDecodeError:
            pos = start + 1
    return None


# ── Graders ───────────────────────────────────────────────────────────────────


def _grade_text(response: str, config: dict) -> bool:
    """Pass when the response matches any 'contains' substring or 'pattern' regex."""
    pattern = config.get("pattern")
    contains = config.get("contains", [])
    if pattern and re.search(pattern, response):
        return True
    if contains and any(str(c).lower() in response.lower() for c in contains):
        return True
    return not pattern and not contains


def _grade_behavior(response: str, config: dict) -> bool:
    """Pass when the response respects a token budget (tool-call counts unavailable)."""
    max_tokens = config.get("max_tokens")
    if max_tokens is not None:
        return _count_tokens(response) <= int(max_tokens)
    return True


def _grade_prompt_judge(
    response: str, config: dict, model: str, token: str
) -> tuple[bool, float]:
    """LLM-as-judge grader; returns (passed, score 0–1)."""
    rubric = config.get("rubric", "Is this response helpful and relevant?")
    try:
        threshold = float(config.get("threshold", 0.7))
    except (TypeError, ValueError):
        return False, 0.0  # invalid threshold config — treat as grader spec error
    prompt = (
        f"Rate the following response on this rubric: {rubric}\n\n"
        f"RESPONSE:\n{response[:2000]}\n\n"
        "Return ONLY a JSON object: "
        '{"score": <float 0-1>, "reasoning": "<brief>"}'
    )
    # Dispatch through the bound wrapper so mock.patch("xanadEval._call_model") works.
    _cm = _api._call_model if _api is not None else _call_model  # type: ignore[union-attr]
    reply = _cm([{"role": "user", "content": prompt}], model, token)
    obj = _extract_first_json_object(reply)
    if obj is not None:
        try:
            score = float(obj.get("score", 0))
            return score >= threshold, score
        except (TypeError, ValueError):
            pass
    return False, 0.0


def _run_graders(
    response: str, graders_spec: list[dict], model: str, token: str
) -> list[dict]:
    """Apply a list of grader specs to *response*; return result records."""
    results: list[dict] = []
    for g in graders_spec:
        gtype = g.get("type", "")
        gname = g.get("name", gtype)
        config = g.get("config", {})
        if gtype == "text":
            passed = _grade_text(response, config)
            results.append({"type": gtype, "name": gname, "pass": passed,
                            "score": 1.0 if passed else 0.0})
        elif gtype == "behavior":
            passed = _grade_behavior(response, config)
            results.append({"type": gtype, "name": gname, "pass": passed,
                            "score": 1.0 if passed else 0.0})
        elif gtype == "prompt":
            if token:
                try:
                    passed, score = _grade_prompt_judge(response, config, model, token)
                    results.append({"type": gtype, "name": gname, "pass": passed, "score": score})
                except RuntimeError as e:
                    results.append({"type": gtype, "name": gname, "pass": None,
                                    "score": None, "error": str(e)})
            else:
                results.append({"type": gtype, "name": gname, "pass": None,
                                "score": None, "skipped": "no GITHUB_TOKEN"})
        else:
            results.append({"type": gtype, "name": gname, "pass": None,
                            "score": None, "skipped": f"grader '{gtype}' not supported"})
    return results


def _aggregate_trials(trial_results: list[list[dict]], n: int) -> list[dict]:
    """Merge per-trial grader records by index: average scores, majority-vote pass."""
    if not trial_results or not trial_results[0]:
        return []
    out: list[dict] = []
    for gi, base in enumerate(trial_results[0]):
        recs = [t[gi] for t in trial_results if gi < len(t)]
        passes = [r["pass"] for r in recs if r.get("pass") is not None]
        scores = [r["score"] for r in recs if r.get("score") is not None]
        merged = dict(base)
        merged["pass"] = (sum(1 for p in passes if p) > len(passes) / 2) if passes else None
        merged["score"] = round(sum(scores) / len(scores), 3) if scores else None
        merged["trials"] = n
        out.append(merged)
    return out
