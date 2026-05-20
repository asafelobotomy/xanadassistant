"""Static analysis commands for xanadEval: tokens, check, suggest.

No API key required. All functions call helpers from _common.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from _common import (
    TOKEN_BUDGET,
    _count_tokens, _max_nesting_depth, _parse_frontmatter,
    _read, _yaml_str,
)


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
    """Run spec and advisory checks on *content*; return (spec, advisory, compliance_level).

    File-type detection: files whose name ends in ``.agent.md`` are checked
    against agent conventions; all other files are checked against SKILL.md
    conventions.  The two sets share the same universal checks but differ in
    the structure-specific checks that follow.
    """
    fm = _parse_frontmatter(content)
    name = fm.get("name", "")
    description = fm.get("description", "")
    token_count = _count_tokens(content)
    is_agent = Path(path).name.endswith(".agent.md")

    # (id, passed, detail)
    spec: list[tuple[str, bool, str]] = []
    advisory: list[tuple[str, bool, str]] = []

    # ── universal spec checks ─────────────────────────────────────────────────
    spec.append(("spec-frontmatter", bool(fm), "frontmatter present"))
    spec.append(("spec-name", bool(name), f"name: {name!r}"))
    spec.append(("spec-description", bool(description), "description present"))

    # ── file-type-specific spec checks ───────────────────────────────────────
    if is_agent:
        # Agents live flat in agents/; check filename instead of parent dir.
        # Comparison is case-insensitive: frontmatter names are title-case
        # (e.g. "Cleaner") but filenames are lowercase ("cleaner.agent.md"),
        # while mixed-case names like "xanadLifecycle" preserve their case.
        actual_fname = Path(path).name
        spec.append((
            "spec-filename-match",
            actual_fname.lower() == f"{name.lower()}.agent.md",
            f"filename matches name ({actual_fname!r})",
        ))

        spec.append((
            "spec-token-budget", token_count <= TOKEN_BUDGET,
            f"token count {token_count:,} / {TOKEN_BUDGET:,}",
        ))

        # Agents define use-cases via "Your role:" prose or an explicit list.
        has_use = "Your role:" in content or "Use this agent for" in content
        spec.append(("spec-when-to-use", has_use, "role / use-case statement present"))

        # Agents should explicitly list what they must NOT do.
        has_not_use = "Do not use this agent for" in content
        spec.append((
            "spec-when-not-to-use", has_not_use,
            "exclusion list present (\"Do not use this agent for\")",
        ))

        # Agents must contain a numbered workflow (regardless of heading name).
        numbered = re.findall(r"^\s*\d+\. ", content, re.MULTILINE)
        spec.append((
            "spec-workflow-steps", len(numbered) >= 2,
            f"numbered workflow steps: {len(numbered)} found (minimum 2)",
        ))

        # Advisory: agents must document their memory integration.
        advisory.append((
            "memory-section", "## Memory" in content,
            "## Memory section present",
        ))
    else:
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

        # Advisory: SKILL.md files should have 2–6 modules.
        modules = re.findall(r"^## Module \d+", content, re.MULTILINE)
        module_count = len(modules)
        advisory.append((
            "module-count", 2 <= module_count <= 6,
            f"module count: {module_count} (2\u20136 is the acceptable range)",
        ))

    # ── shared advisory checks ────────────────────────────────────────────────
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
        # Agents live one level below the repo root (agents/).
        # Skills live two levels below (skills/<name>/SKILL.md).
        if is_agent:
            eval_path = Path(path).parent.parent / "evals" / name / "eval.yaml"
        else:
            eval_path = Path(path).parent.parent.parent / "evals" / name / "eval.yaml"
        found = eval_path.exists()
        msg = (
            "eval suite: found"
            if found
            else f"eval suite: not found (expected at evals/{name}/eval.yaml)"
        )
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
    is_agent = Path(path).name.endswith(".agent.md")

    # Validate name before using in path construction or YAML output.
    if not name or "/" in name or "\\" in name or name.startswith("."):
        print(
            f"xanadEval suggest: unsafe or empty skill name {name!r}",
            file=sys.stderr,
        )
        return 2

    desc_short = (description[:100] + "...") if len(description) > 100 else description
    kind = "agent" if is_agent else "skill"

    eval_yaml = (
        f"name: {_yaml_str(name + '-eval')}\n"
        f"description: {_yaml_str('Evaluates ' + name + ' ' + kind + ' behaviour')}\n\n"
        f"graders:\n"
        f"  - type: text\n"
        f"    name: references_{kind}\n"
        f"    config:\n"
        f"      pattern: {_yaml_str('(?i)(' + re.escape(name) + '|' + kind + ')')}\n\n"
        f"  - type: behavior\n"
        f"    name: completion_bound\n"
        f"    config:\n"
        f"      max_tokens: 2000\n\n"
        f"tasks:\n  - {_yaml_str('tasks/*.yaml')}\n"
    )
    positive_task_yaml = (
        f"id: positive-trigger-1\n"
        f"description: {_yaml_str('Verify ' + kind + ' triggers on its primary use case')}\n"
        f"prompt: |\n  {desc_short}\n"
        f"tags:\n  - basic\n  - smoke\n  - positive\n"
    )
    negative_task_yaml = (
        f"id: negative-trigger-1\n"
        f"description: {_yaml_str('Verify ' + kind + ' does NOT trigger on an unrelated request')}\n"
        f"prompt: |\n  What is the current time and date?\n"
        f"expected_absent:\n  - {_yaml_str('(?i)(' + re.escape(name) + ')')}\n"
        f"tags:\n  - smoke\n  - negative\n"
    )

    # Resolve the eval directory.
    # Agents:  agents/{name}.agent.md  → {repo-root}/evals/{name}/
    # Skills:  skills/{name}/SKILL.md  → {repo-root}/evals/{name}/
    if is_agent:
        eval_dir = Path(path).parent.parent / "evals" / name
    else:
        skill_dir_parent = Path(path).parent.parent  # expected: .../skills/
        if skill_dir_parent.name != "skills":
            print(
                f"xanadEval suggest: SKILL.md is not under a 'skills/' directory "
                f"(found: {skill_dir_parent.name!r}); output paths are relative to "
                f"{skill_dir_parent.parent}",
                file=sys.stderr,
            )
        eval_dir = skill_dir_parent.parent / "evals" / name

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
        try:
            eval_dir.mkdir(parents=True, exist_ok=True)
            (eval_dir / "tasks").mkdir(exist_ok=True)
            (eval_dir / "eval.yaml").write_text(eval_yaml, encoding="utf-8")
            (eval_dir / "tasks" / "positive-trigger-1.yaml").write_text(
                positive_task_yaml, encoding="utf-8"
            )
            (eval_dir / "tasks" / "negative-trigger-1.yaml").write_text(
                negative_task_yaml, encoding="utf-8"
            )
        except OSError as e:
            print(f"xanadEval suggest: cannot write eval files: {e}", file=sys.stderr)
            return 2
        print(f"Written: {eval_dir / 'eval.yaml'}")
        print(f"Written: {eval_dir / 'tasks' / 'positive-trigger-1.yaml'}")
        print(f"Written: {eval_dir / 'tasks' / 'negative-trigger-1.yaml'}")

    return 0
