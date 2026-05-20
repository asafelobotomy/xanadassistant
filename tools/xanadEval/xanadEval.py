#!/usr/bin/env python3
"""xanadEval — skill analyser and eval runner for Copilot surface files.

Static commands (no API key required):
  tokens <path>          Structural metrics: token count, sections, nesting
  check  <path>          Spec-compliance and advisory checks
  suggest <path>         Scaffold an eval task suite from frontmatter
  coverage [root]        Skill-to-eval coverage report
  compare <ref>          Git-ref token-diff
  report  [paths]        Self-contained HTML check report

Dynamic commands (require GITHUB_TOKEN or GH_TOKEN):
  run     <eval.yaml>    Execute eval tasks against GitHub Models
  grade   <eval.yaml> <results.json>   Re-run graders on existing results
  quality <path>         LLM-as-judge: score skill on 5 quality dimensions
  dev     <path>         Surface top improvement suggestions
  results list  [dir]    List saved result files
  results compare <f1> <f2>  Compare pass-rate deltas across runs
  results view  <file>   Display a saved result file
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
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
        return 0  # no list items at all
    depths = [
        len(m.group(1)) // 2
        for m in re.finditer(r"^( +)[-*\d]", content, re.MULTILINE)
    ]
    return max(depths, default=0) + 1


# ── GitHub Models integration ─────────────────────────────────────────────────

_GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_RESULTS_DIR = ".xanadEval"
_QUALITY_DIMENSIONS = [
    "clarity", "completeness", "trigger_precision", "scope_coverage", "anti_patterns",
]


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
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected response format: {e}") from e


def _load_spec(path: str) -> dict:
    """Load an eval spec (YAML preferred when PyYAML is available, else JSON)."""
    text = Path(path).read_text(encoding="utf-8")
    if _yaml is not None:
        result = _yaml.safe_load(text)
        if isinstance(result, dict):
            return result
    # JSON fallback — valid JSON is also valid YAML, so this covers both cases
    # when PyYAML is absent.
    return json.loads(text)


def _load_tasks(eval_dir: Path, task_refs: list) -> list[dict]:
    """Expand task references (glob strings or inline dicts) into task dicts."""
    tasks: list[dict] = []
    for ref in task_refs:
        if isinstance(ref, dict):
            tasks.append(ref)
        elif isinstance(ref, str):
            for fp in sorted(eval_dir.glob(ref)):
                raw = fp.read_text(encoding="utf-8")
                tasks.append(_yaml.safe_load(raw) if _yaml else json.loads(raw))
    return tasks


def _extract_first_json_object(text: str) -> dict | None:
    """Return the first balanced JSON object found in *text*, or None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
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
    return not pattern and not contains  # trivial pass when no criteria configured


def _grade_behavior(response: str, config: dict) -> bool:
    """Pass when the response respects a token budget (tool-call counts unavailable)."""
    max_tokens = config.get("max_tokens")
    if max_tokens is not None:
        return _count_tokens(response) <= int(max_tokens)
    return True  # max_tool_calls cannot be verified without trace data


def _grade_prompt_judge(
    response: str, config: dict, model: str, token: str
) -> tuple[bool, float]:
    """LLM-as-judge grader; returns (passed, score 0–1)."""
    rubric = config.get("rubric", "Is this response helpful and relevant?")
    threshold = float(config.get("threshold", 0.7))
    prompt = (
        f"Rate the following response on this rubric: {rubric}\n\n"
        f"RESPONSE:\n{response[:2000]}\n\n"
        "Return ONLY a JSON object: "
        '{"score": <float 0-1>, "reasoning": "<brief>"}'
    )
    reply = _call_model([{"role": "user", "content": prompt}], model, token)
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


# ── tokens ────────────────────────────────────────────────────────────────────


def cmd_tokens(path: str, fmt: str) -> int:
    """Print structural metrics for the file at *path*."""
    content = _read(path)
    token_count = _count_tokens(content)

    sections = len(re.findall(r"^#{1,6} ", content, re.MULTILINE))
    fences = re.findall(r"^```", content, re.MULTILINE)
    code_blocks = len(fences) // 2
    numbered = re.findall(r"^\s*\d+\. ", content, re.MULTILINE)
    workflow_detected = len(numbered) >= 3
    max_depth = _max_nesting_depth(content)

    if fmt == "json":
        print(
            json.dumps(
                {
                    "token_count": token_count,
                    "token_budget": TOKEN_BUDGET,
                    "sections": sections,
                    "code_blocks": code_blocks,
                    "workflow_steps_detected": workflow_detected,
                    "max_nesting_depth": max_depth,
                },
                indent=2,
            )
        )
    else:
        budget_flag = "\u2713" if token_count <= TOKEN_BUDGET else "\u2717"
        wf = "detected" if workflow_detected else "not detected"
        label = Path(path).name
        print(f"xanadEval tokens \u2014 {label}")
        print(
            f"  token_count       : {token_count:,}"
            f"  {budget_flag} budget {TOKEN_BUDGET:,}"
        )
        print(f"  sections          : {sections}")
        print(f"  code_blocks       : {code_blocks}")
        print(f"  workflow_steps    : {wf}")
        print(f"  max_nesting_depth : {max_depth}")
    return 0


# ── check ─────────────────────────────────────────────────────────────────────


def _build_check_result(
    content: str, path: str
) -> tuple[list[tuple[str, bool, str]], list[tuple[str, bool, str]], str]:
    """Run spec and advisory checks on *content*; return (spec, advisory, compliance_level)."""
    fm = _parse_frontmatter(content)
    name = fm.get("name", "")
    description = fm.get("description", "")
    token_count = _count_tokens(content)

    # (id, passed, detail)
    spec: list[tuple[str, bool, str]] = []
    advisory: list[tuple[str, bool, str]] = []

    spec.append(("spec-frontmatter", bool(fm), "frontmatter present"))
    spec.append(("spec-name", bool(name), f"name: {name!r}"))
    spec.append(("spec-description", bool(description), "description present"))
    dir_name = Path(path).parent.name
    spec.append((
        "spec-dir-match", name == dir_name or dir_name == ".",
        f"name matches directory ({dir_name!r})",
    ))
    spec.append((
        "spec-token-budget", token_count <= TOKEN_BUDGET,
        f"token count {token_count:,} / {TOKEN_BUDGET:,}",
    ))
    spec.append(("spec-verify-checklist", "## Verify" in content, "## Verify checklist present"))
    spec.append(("spec-when-to-use", "## When to use" in content, "## When to use present"))
    spec.append((
        "spec-when-not-to-use", "## When NOT to use" in content,
        "## When NOT to use present",
    ))
    has_steps = "## Steps" in content or bool(
        re.search(r"^## Module \d+", content, re.MULTILINE)
    )
    spec.append((
        "spec-steps-or-modules", has_steps,
        "workflow structure present (## Steps or ## Module N)",
    ))

    modules = re.findall(r"^## Module \d+", content, re.MULTILINE)
    module_count = len(modules)
    advisory.append((
        "module-count", 2 <= module_count <= 6,
        f"module count: {module_count} (2\u20136 is the acceptable range)",
    ))

    advisory.append((
        "description-quality", len(description) >= 20,
        f"description length: {len(description)} chars (minimum 20)",
    ))

    section_bodies = re.split(r"^## ", content, flags=re.MULTILINE)
    max_rules = max(
        (len(re.findall(r"^[-*] ", body, re.MULTILINE)) for body in section_bodies),
        default=0,
    )
    advisory.append((
        "over-specificity", max_rules <= 10,
        f"max rules per section: {max_rules} (threshold: 10)",
    ))

    neg_hits = re.findall(
        r"\b(ignore|skip|bypass|override|never ask|always proceed)\b",
        content,
        re.IGNORECASE,
    )
    advisory.append((
        "negative-delta-risk", len(neg_hits) == 0,
        f"negative-delta patterns: {len(neg_hits)} found",
    ))

    max_depth = _max_nesting_depth(content)
    advisory.append((
        "complexity", max_depth <= 3,
        f"max nesting depth: {max_depth} (threshold: 3)",
    ))

    if name:
        eval_path = Path(path).parent.parent.parent / "evals" / name / "eval.yaml"
        found = eval_path.exists()
        msg = "eval suite: found" if found else f"eval suite: not found (expected at evals/{name}/eval.yaml)"
        advisory.append(("eval-presence", found, msg))

    spec_score = sum(1 for _, ok, _ in spec if ok) / len(spec)
    adv_score = sum(1 for _, ok, _ in advisory if ok) / len(advisory)
    weighted = spec_score * 0.7 + adv_score * 0.3
    level = (
        "High"
        if weighted >= 0.90
        else "Medium-High"
        if weighted >= 0.75
        else "Medium"
        if weighted >= 0.50
        else "Low"
    )
    return spec, advisory, level


def cmd_check(path: str, fmt: str) -> int:
    """Spec compliance and advisory checks; exits non-zero when a spec check fails."""
    content = _read(path)
    spec, advisory, level = _build_check_result(content, path)
    exit_code = 0 if all(ok for _, ok, _ in spec) else 1

    if fmt == "json":
        print(
            json.dumps(
                {
                    "compliance": level,
                    "spec_checks": [
                        {"id": k, "pass": ok, "detail": d} for k, ok, d in spec
                    ],
                    "advisory_checks": [
                        {"id": k, "pass": ok, "detail": d} for k, ok, d in advisory
                    ],
                },
                indent=2,
            )
        )
    else:
        label = Path(path).name
        print(f"xanadEval check \u2014 {label}")
        print(f"  compliance: {level}")
        print()
        print("  spec checks:")
        for _, ok, d in spec:
            print(f"    {chr(10003) if ok else chr(10007)} {d}")
        print()
        print("  advisory checks:")
        for _, ok, d in advisory:
            print(f"    {chr(10003) if ok else chr(10007)} {d}")

    return exit_code


# ── suggest ───────────────────────────────────────────────────────────────────


def cmd_suggest(path: str, dry_run: bool) -> int:
    """Scaffold a minimal eval task suite; dry-run prints, --apply writes files."""
    content = _read(path)
    fm = _parse_frontmatter(content)
    name = fm.get("name") or Path(path).parent.name
    description = fm.get("description", "")

    # Validate name before using in path construction or YAML output.
    if not name or "/" in name or "\\" in name or name.startswith("."):
        print(
            f"xanadEval suggest: unsafe or empty skill name {name!r}",
            file=sys.stderr,
        )
        return 2

    desc_short = (description[:100] + "...") if len(description) > 100 else description

    eval_yaml = (
        f"name: {_yaml_str(name + '-eval')}\n"
        f"description: {_yaml_str('Evaluates ' + name + ' skill behaviour')}\n\n"
        f"graders:\n"
        f"  - type: text\n"
        f"    name: references_skill\n"
        f"    config:\n"
        f"      pattern: {_yaml_str('(?i)(' + re.escape(name) + '|skill)')}\n\n"
        f"  - type: behavior\n"
        f"    name: completion_bound\n"
        f"    config:\n"
        f"      max_tokens: 2000\n\n"
        f"tasks:\n  - {_yaml_str('tasks/*.yaml')}\n"
    )
    positive_task_yaml = (
        f"id: positive-trigger-1\n"
        f"description: {_yaml_str('Verify skill triggers on its primary use case')}\n"
        f"prompt: |\n  {desc_short}\n"
        f"tags:\n  - basic\n  - smoke\n  - positive\n"
    )
    negative_task_yaml = (
        f"id: negative-trigger-1\n"
        f"description: {_yaml_str('Verify skill does NOT trigger on an unrelated request')}\n"
        f"prompt: |\n  What is the current time and date?\n"
        f"expected_absent:\n  - {_yaml_str('(?i)(' + re.escape(name) + ')')}\n"
        f"tags:\n  - smoke\n  - negative\n"
    )

    # Canonical layout: <repo-root>/skills/<name>/SKILL.md → <repo-root>/evals/<name>/
    skill_dir_parent = Path(path).parent.parent  # expected: .../skills/
    if skill_dir_parent.name != "skills":
        print(
            f"xanadEval suggest: SKILL.md is not under a 'skills/' directory "
            f"(found: {skill_dir_parent.name!r}); output paths are relative to "
            f"{skill_dir_parent.parent}",
            file=sys.stderr,
        )

    if dry_run:
        label = Path(path).name
        print(f"# xanadEval suggest --dry-run \u2014 {label}")
        print(f"# Would write: evals/{name}/eval.yaml")
        print()
        print(eval_yaml)
        print(f"# Would write: evals/{name}/tasks/positive-trigger-1.yaml")
        print()
        print(positive_task_yaml)
        print(f"# Would write: evals/{name}/tasks/negative-trigger-1.yaml")
        print()
        print(negative_task_yaml)
    else:
        eval_dir = skill_dir_parent.parent / "evals" / name
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "tasks").mkdir(exist_ok=True)
        (eval_dir / "eval.yaml").write_text(eval_yaml, encoding="utf-8")
        (eval_dir / "tasks" / "positive-trigger-1.yaml").write_text(
            positive_task_yaml, encoding="utf-8"
        )
        (eval_dir / "tasks" / "negative-trigger-1.yaml").write_text(
            negative_task_yaml, encoding="utf-8"
        )
        print(f"Written: {eval_dir / 'eval.yaml'}")
        print(f"Written: {eval_dir / 'tasks' / 'positive-trigger-1.yaml'}")
        print(f"Written: {eval_dir / 'tasks' / 'negative-trigger-1.yaml'}")

    return 0


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
                responses.append(_call_model(messages, model, token))
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
    result_file = results_dir / f"{skill_name}-{ts}-{safe_model}.json"
    result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")

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
    Path(results_path).write_text(json.dumps(result, indent=2), encoding="utf-8")

    if fmt == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"xanadEval grade \u2014 {results_path}")
        print(f"  {passed_count}/{total} passed  ({pass_rate:.0%})  score: {avg_score:.3f}")
    return 0 if passed_count == total else 1


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
        reply = _call_model(
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
        reply = _call_model(
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


# ── results ───────────────────────────────────────────────────────────────────


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
                delta = ct.get("score", 0) - bt.get("score", 0)
                deltas.append({
                    "task": tid,
                    "baseline_score": bt.get("score", 0),
                    "compare_score": ct.get("score", 0),
                    "delta": round(delta, 3),
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


# ── CLI ───────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="xanadEval",
        description=(
            "Skill analyser and eval runner for Copilot surface files (xanadAssistant). "
            "Static commands require no API key. Dynamic commands (run, grade, quality, dev, "
            "results) require GITHUB_TOKEN or GH_TOKEN."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="fmt",
        help="Output format (default: text)",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    def _add_format(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--format",
            choices=["text", "json"],
            default=argparse.SUPPRESS,
            dest="fmt",
            help="Output format (default: text); overrides the global --format flag",
        )

    p_tok = sub.add_parser(
        "tokens",
        help="Structural metrics: token estimate, sections, code blocks, workflow steps",
    )
    p_tok.add_argument("path", help="Path to the surface file")
    _add_format(p_tok)

    p_chk = sub.add_parser(
        "check",
        help="Spec compliance and advisory checks (exits non-zero on spec failure)",
    )
    p_chk.add_argument("path", help="Path to the SKILL.md file")
    _add_format(p_chk)

    p_sug = sub.add_parser(
        "suggest",
        help="Scaffold a minimal eval task suite from frontmatter metadata",
    )
    p_sug.add_argument("path", help="Path to the SKILL.md file")
    mode = p_sug.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="Print scaffolded YAML to stdout without writing files (default)",
    )
    mode.add_argument(
        "--apply",
        dest="apply",
        action="store_true",
        help="Write scaffolded files to evals/<name>/",
    )
    p_sug.set_defaults(apply=False)

    p_cov = sub.add_parser(
        "coverage",
        help="Scan a directory for SKILL.md files and report eval coverage",
    )
    p_cov.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory to scan (default: current directory)",
    )
    _add_format(p_cov)

    p_cmp = sub.add_parser(
        "compare",
        help="Compare token counts between working tree and a git ref",
    )
    p_cmp.add_argument("ref", help="Git ref to compare against (e.g. main, HEAD~1)")
    p_cmp.add_argument(
        "paths",
        nargs="*",
        help="Files to compare (omit when using --skills)",
    )
    p_cmp.add_argument(
        "--skills",
        action="store_true",
        help="Scan all SKILL.md files under the current directory",
    )
    p_cmp.add_argument(
        "--threshold",
        type=int,
        default=None,
        metavar="N",
        help="Exit 1 if any file grows by more than N%% (e.g. 10)",
    )
    p_cmp.add_argument(
        "--strict",
        action="store_true",
        help="Also fail if any file shrinks by more than threshold%%",
    )
    _add_format(p_cmp)

    p_rep = sub.add_parser(
        "report",
        help="Generate a self-contained HTML report from check results",
    )
    p_rep.add_argument(
        "paths",
        nargs="*",
        help="SKILL.md file(s) to include; omit to scan current directory",
    )
    p_rep.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Output HTML file (default: xanadEval-report.html)",
    )

    # ── Dynamic commands ─────────────────────────────────────────────────────

    def _add_model(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--model",
            default=_DEFAULT_MODEL,
            metavar="MODEL",
            help=f"GitHub Models model name (default: {_DEFAULT_MODEL})",
        )

    p_run = sub.add_parser(
        "run",
        help="Execute eval tasks against GitHub Models (requires GITHUB_TOKEN)",
    )
    p_run.add_argument("eval_path", metavar="eval.yaml", help="Path to the eval spec")
    _add_model(p_run)
    p_run.add_argument(
        "--trials", type=int, default=1, metavar="N",
        help="Number of trials per task (default: 1)",
    )
    _add_format(p_run)

    p_grd = sub.add_parser(
        "grade",
        help="Re-run graders against existing results without re-invoking the model",
    )
    p_grd.add_argument("eval_path", metavar="eval.yaml", help="Path to the eval spec")
    p_grd.add_argument("results_path", metavar="results.json",
                       help="Path to the results file to re-grade")
    _add_model(p_grd)
    _add_format(p_grd)

    p_qlt = sub.add_parser(
        "quality",
        help="LLM-as-judge: score a SKILL.md on 5 quality dimensions (requires GITHUB_TOKEN)",
    )
    p_qlt.add_argument("path", help="Path to the SKILL.md file")
    _add_model(p_qlt)
    _add_format(p_qlt)

    p_dev = sub.add_parser(
        "dev",
        help="Analyse a SKILL.md and surface the top improvement suggestions (requires GITHUB_TOKEN)",
    )
    p_dev.add_argument("path", help="Path to the SKILL.md file")
    _add_model(p_dev)
    _add_format(p_dev)

    p_res = sub.add_parser("results", help="Manage saved eval result files")
    res_sub = p_res.add_subparsers(dest="results_action", required=True)

    p_res_list = res_sub.add_parser("list", help="List saved result files")
    p_res_list.add_argument(
        "results_dir", nargs="?", default=_DEFAULT_RESULTS_DIR,
        metavar="DIR", help=f"Results directory (default: {_DEFAULT_RESULTS_DIR})",
    )
    _add_format(p_res_list)

    p_res_cmp = res_sub.add_parser("compare",
                                   help="Compare pass-rate and per-task scores across runs")
    p_res_cmp.add_argument("files", nargs="+", metavar="result.json",
                           help="Two or more result JSON files to compare")
    _add_format(p_res_cmp)

    p_res_view = res_sub.add_parser("view", help="Display a saved result file")
    p_res_view.add_argument("results_path", metavar="result.json",
                            help="Path to the result file")
    _add_format(p_res_view)

    args = parser.parse_args(argv)

    if args.cmd == "tokens":
        return cmd_tokens(args.path, args.fmt)
    if args.cmd == "check":
        return cmd_check(args.path, args.fmt)
    if args.cmd == "suggest":
        return cmd_suggest(args.path, dry_run=not args.apply)
    if args.cmd == "coverage":
        return cmd_coverage(args.root, args.fmt)
    if args.cmd == "compare":
        return cmd_compare(
            args.ref, args.paths, args.skills, args.threshold, args.strict, args.fmt
        )
    if args.cmd == "report":
        report_paths = args.paths
        if not report_paths:
            report_paths = [str(p) for p in Path(".").rglob("SKILL.md")]
        return cmd_report(report_paths, args.output)
    if args.cmd == "run":
        return cmd_run(args.eval_path, args.model, args.trials, args.fmt)
    if args.cmd == "grade":
        return cmd_grade(args.eval_path, args.results_path, args.model, args.fmt)
    if args.cmd == "quality":
        return cmd_quality(args.path, args.model, args.fmt)
    if args.cmd == "dev":
        return cmd_dev(args.path, args.model, args.fmt)
    if args.cmd == "results":
        if args.results_action == "list":
            return cmd_results_list(args.results_dir, args.fmt)
        if args.results_action == "compare":
            return cmd_compare_results(args.files, args.fmt)
        if args.results_action == "view":
            return cmd_results_view(args.results_path, args.fmt)
    return 1  # unreachable — argparse guarantees a subcommand


if __name__ == "__main__":
    sys.exit(main())
