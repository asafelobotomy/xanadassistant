"""Extended grader types for xanadEval: trigger, file, diff.

Internal implementation detail — import ``xanadEval`` directly, not this module.
"""
from __future__ import annotations

import re
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
