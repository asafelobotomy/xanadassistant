#!/usr/bin/env python3
"""xanadEval — static analysis for Copilot surface files.

Part of xanadAssistant. Installed to .github/tools/xanadEval/xanadEval.py
in consumer workspaces.

Commands:
  tokens <path> [--format json|text]   Structural metrics (token estimate, sections, …)
  check  <path> [--format json|text]   Spec compliance + advisory checks
  suggest <path> [--dry-run|--apply]   Scaffold an eval task suite from frontmatter
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# One token ≈ four characters (documented approximation — no tiktoken dep).
TOKEN_BUDGET: int = 16_000
_CHARS_PER_TOKEN: int = 4


# ── Helpers ───────────────────────────────────────────────────────────────────


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Return key/value pairs from YAML frontmatter delimited by ``---``."""
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" in line:
            key, _, rest = line.partition(":")
            result[key.strip()] = rest.strip().strip("\"'")
    return result


def _token_estimate(content: str) -> int:
    return len(content) // _CHARS_PER_TOKEN


def _max_nesting_depth(content: str) -> int:
    depths = [
        len(m.group(1)) // 2
        for m in re.finditer(r"^( +)[-*\d]", content, re.MULTILINE)
    ]
    return max(depths, default=0) + 1


# ── tokens ────────────────────────────────────────────────────────────────────


def cmd_tokens(path: str, fmt: str) -> int:
    """Print structural metrics for the file at *path*."""
    content = _read(path)
    token_est = _token_estimate(content)

    # Headings (any level)
    sections = len(re.findall(r"^#{1,6} ", content, re.MULTILINE))
    # Opening fence lines; pairs = complete code blocks
    fences = re.findall(r"^```", content, re.MULTILINE)
    code_blocks = len(fences) // 2
    # Workflow detected when ≥3 consecutive numbered list items exist
    numbered = re.findall(r"^\s*\d+\. ", content, re.MULTILINE)
    workflow_detected = len(numbered) >= 3
    max_depth = _max_nesting_depth(content)

    if fmt == "json":
        print(
            json.dumps(
                {
                    "token_estimate": token_est,
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
        budget_flag = "\u2713" if token_est <= TOKEN_BUDGET else "\u2717"
        wf = "detected" if workflow_detected else "not detected"
        label = Path(path).name
        print(f"xanadEval tokens \u2014 {label}")
        print(
            f"  token_estimate    : {token_est:,}"
            f"  {budget_flag} budget {TOKEN_BUDGET:,}"
        )
        print(f"  sections          : {sections}")
        print(f"  code_blocks       : {code_blocks}")
        print(f"  workflow_steps    : {wf}")
        print(f"  max_nesting_depth : {max_depth}")
    return 0


# ── check ─────────────────────────────────────────────────────────────────────


def cmd_check(path: str, fmt: str) -> int:
    """Spec compliance and advisory checks for the SKILL.md at *path*.

    Exits non-zero when any spec check fails.
    """
    content = _read(path)
    fm = _parse_frontmatter(content)
    name = fm.get("name", "")
    description = fm.get("description", "")
    token_est = _token_estimate(content)

    # (id, passed, detail)
    spec: list[tuple[str, bool, str]] = []
    advisory: list[tuple[str, bool, str]] = []

    # ── Spec checks ───────────────────────────────────────────────────────────
    spec.append(("spec-frontmatter", bool(fm), "frontmatter present"))
    spec.append(("spec-name", bool(name), f"name: {name!r}"))
    spec.append(("spec-description", bool(description), "description present"))
    dir_name = Path(path).parent.name
    spec.append(
        (
            "spec-dir-match",
            name == dir_name or dir_name == ".",
            f"name matches directory ({dir_name!r})",
        )
    )
    spec.append(
        (
            "spec-token-budget",
            token_est <= TOKEN_BUDGET,
            f"token estimate {token_est:,} / {TOKEN_BUDGET:,}",
        )
    )
    spec.append(
        ("spec-verify-checklist", "## Verify" in content, "## Verify checklist present")
    )
    spec.append(
        ("spec-when-to-use", "## When to use" in content, "## When to use present")
    )
    spec.append(
        (
            "spec-when-not-to-use",
            "## When NOT to use" in content,
            "## When NOT to use present",
        )
    )

    # ── Advisory checks ───────────────────────────────────────────────────────
    modules = re.findall(r"^## Module \d+", content, re.MULTILINE)
    module_count = len(modules)
    advisory.append(
        (
            "module-count",
            2 <= module_count <= 6,
            f"module count: {module_count} (2\u20136 is optimal)",
        )
    )

    section_bodies = re.split(r"^## ", content, flags=re.MULTILINE)
    max_rules = max(
        (len(re.findall(r"^[-*] ", body, re.MULTILINE)) for body in section_bodies),
        default=0,
    )
    advisory.append(
        (
            "over-specificity",
            max_rules <= 10,
            f"max rules per section: {max_rules} (threshold: 10)",
        )
    )

    neg_hits = re.findall(
        r"\b(ignore|skip|bypass|override|never ask|always proceed)\b",
        content,
        re.IGNORECASE,
    )
    advisory.append(
        (
            "negative-delta-risk",
            len(neg_hits) == 0,
            f"negative-delta patterns: {len(neg_hits)} found",
        )
    )

    max_depth = _max_nesting_depth(content)
    advisory.append(
        (
            "complexity",
            max_depth <= 3,
            f"max nesting depth: {max_depth} (threshold: 3)",
        )
    )

    # ── Compliance level ──────────────────────────────────────────────────────
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
    """Scaffold a minimal eval task suite from frontmatter metadata.

    With *dry_run* (default) prints to stdout.  With ``--apply`` writes files
    to ``evals/<name>/`` relative to the skill's grandparent directory.
    """
    content = _read(path)
    fm = _parse_frontmatter(content)
    name = fm.get("name") or Path(path).parent.name
    description = fm.get("description", "")
    desc_short = (description[:100] + "...") if len(description) > 100 else description

    eval_yaml = (
        f"name: {name}-eval\n"
        f'description: "Evaluates {name} skill behaviour"\n'
        f"\n"
        f"graders:\n"
        f"  - type: text\n"
        f"    name: references_skill\n"
        f"    config:\n"
        f"      pattern: \"(?i)({re.escape(name)}|skill)\"\n"
        f"\n"
        f"tasks:\n"
        f'  - "tasks/*.yaml"\n'
    )
    task_yaml = (
        f"id: basic-invocation\n"
        f'description: "Verify skill triggers on its primary use case"\n'
        f"prompt: |\n"
        f"  {desc_short}\n"
        f"tags:\n"
        f"  - basic\n"
        f"  - smoke\n"
    )

    if dry_run:
        label = Path(path).name
        print(f"# xanadEval suggest --dry-run \u2014 {label}")
        print(f"# Would write: evals/{name}/eval.yaml")
        print()
        print(eval_yaml)
        print(f"# Would write: evals/{name}/tasks/basic-invocation.yaml")
        print()
        print(task_yaml)
    else:
        # Place evals/ two levels above the SKILL.md (skill-dir → skills-root → repo-root)
        eval_dir = Path(path).parent.parent.parent / "evals" / name
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "tasks").mkdir(exist_ok=True)
        (eval_dir / "eval.yaml").write_text(eval_yaml, encoding="utf-8")
        (eval_dir / "tasks" / "basic-invocation.yaml").write_text(
            task_yaml, encoding="utf-8"
        )
        print(f"Written: {eval_dir / 'eval.yaml'}")
        print(f"Written: {eval_dir / 'tasks' / 'basic-invocation.yaml'}")

    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="xanadEval",
        description=(
            "Static analysis for Copilot surface files (part of xanadAssistant). "
            "Install location: .github/tools/xanadEval/xanadEval.py"
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

    p_tok = sub.add_parser(
        "tokens",
        help="Structural metrics: token estimate, sections, code blocks, workflow steps",
    )
    p_tok.add_argument("path", help="Path to the surface file")

    p_chk = sub.add_parser(
        "check",
        help="Spec compliance and advisory checks (exits non-zero on spec failure)",
    )
    p_chk.add_argument("path", help="Path to the SKILL.md file")

    p_sug = sub.add_parser(
        "suggest",
        help="Scaffold a minimal eval task suite from frontmatter metadata",
    )
    p_sug.add_argument("path", help="Path to the SKILL.md file")
    p_sug.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print scaffolded YAML to stdout without writing files (default)",
    )
    p_sug.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Write scaffolded files to evals/<name>/ (overrides --dry-run)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "tokens":
        return cmd_tokens(args.path, args.fmt)
    if args.cmd == "check":
        return cmd_check(args.path, args.fmt)
    if args.cmd == "suggest":
        return cmd_suggest(args.path, dry_run=not args.apply)
    return 1  # unreachable — argparse guarantees a subcommand


if __name__ == "__main__":
    sys.exit(main())
