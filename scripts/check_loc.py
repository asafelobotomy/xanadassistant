#!/usr/bin/env python3
"""LOC gate — enforces the default 250-warning / 400-hard-limit per-file policy.

Usage:
    python3 scripts/check_loc.py [--hard-only] [file ...]

Without file arguments, scans the whole repo (respecting .gitignore via git ls-files).
Exit codes:
    0  All files within limits.
    1  One or more files exceed their hard limit.

Files above their warning threshold but at or below their hard limit emit warnings but do
not fail.  Per-file hard-limit overrides are documented in HARD_LIMIT_OVERRIDES.

Scoped to: *.py, *.md, *.sh files that are tracked by git (or provided explicitly).
JSON / schema / lock files are excluded — they are data, not source.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

WARN_LIMIT = 250
HARD_LIMIT = 400
REPO_ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = {".py", ".md", ".sh"}
WARN_LIMIT_OVERRIDES = {
    # ── Agent surface files ───────────────────────────────────────────────────────
    # Agent definitions are long-form instruction documents; they grow with features.
    "agents/xanadLifecycle.agent.md": 370,

    # ── Top-level project docs ─────────────────────────────────────────────────────
    "README.md": 330,
    "docs/archive/memory-mcp.md": 300,

    # ── Consumer MCP scripts (single-file delivery) ───────────────────────────────
    # Consumer workspaces receive these MCP servers as single files, so they need a little
    # more room than the default warning budget while still honoring the hard limit.
    "mcp/scripts/sequentialThinkingMcp.py": 310,
    "mcp/scripts/memoryMcp.py": 600,
    "mcp/scripts/webMcp.py": 450,
    "mcp/scripts/xanadWorkspaceMcp.py": 500,
    "mcp/scripts/gitMcp.py": 450,
    "mcp/scripts/githubMcp.py": 450,
    "mcp/scripts/_memory_mcp_shared.py": 420,

    # ── Pack MCP scripts (consumer-facing single-file scripts) ────────────────────
    "packs/secure/mcp/secureOsv.py": 300,
    "packs/shapeup/mcp/shapeupScopeCheck.py": 300,

    # ── Lifecycle engine submodules ───────────────────────────────────────────────
    # Each submodule is intentionally scoped; these grew slightly beyond 250 while
    # remaining well under the hard limit.
    "scripts/lifecycle/_xanad/_apply_executor.py": 410,
    "scripts/lifecycle/_xanad/_execute_apply_compat.py": 320,
    "scripts/lifecycle/_xanad/_interview.py": 300,
    "scripts/lifecycle/_xanad/_main.py": 310,
    "scripts/lifecycle/_xanad/_plan_b.py": 310,

    "scripts/lifecycle/generate_manifest.py": 310,

    # ── Lifecycle tests ────────────────────────────────────────────────────────────
    "tests/lifecycle/test_apply_contracts.py": 460,
    "tests/lifecycle/test_apply_executor.py": 330,
    "tests/lifecycle/test_health_check.py": 260,
    "tests/lifecycle/test_main_dispatch.py": 300,
    "tests/lifecycle/test_plan_action_helpers.py": 380,
    "tests/lifecycle/test_plan_agent_tokens.py": 320,
    "tests/lifecycle/test_plan_interview.py": 320,
    "tests/lifecycle/test_progress_and_defaults.py": 290,
    "tests/lifecycle/test_source_and_state.py": 330,

    # ── MCP test modules ───────────────────────────────────────────────────────────
    "tests/mcp_servers/test_web_mcp.py": 420,
    "tests/mcp_servers/test_xanad_workspace_mcp_lifecycle.py": 280,
    "tests/mcp_servers/test_memory_mcp.py": 380,

    # ── Prompt contract test module ────────────────────────────────────────────────
    # Grows with each new per-agent contract assertion; one test per invariant.
    "tests/repo/test_prompt_contracts.py": 400,

    # ── xanadEval tool and test modules ───────────────────────────────────────────
    # _common.py: grew with retry logic, new grader types, and extended _run_graders dispatch.
    "tools/xanadEval/_common.py": 700,
    # graders_ext module: trigger/file/diff/code/action_sequence/tool_constraint/script/human/skill_invocation.
    "tools/xanadEval/_graders_ext.py": 740,
    # graders test: grew with LlmGraderTests and LlmComparisonGraderTests.
    "tests/tools/test_xanadEval_graders.py": 480,
    # runtime test: grew with RetryTests, ExpectedFieldTests, TagsFilterTests, AgentSurfaceResolutionTests.
    "tests/tools/test_xanadEval_runtime.py": 540,
    # graders_ext test: trigger, file, diff, code, action_sequence, tool_constraint tests.
    "tests/tools/test_xanadEval_graders_ext.py": 560,
    # graders_ext2 test: script, human, skill_invocation, max_calls tests.
    "tests/tools/test_xanadEval_graders_ext2.py": 300,
    # workspace_grade_human MCP tests.
    "tests/mcp_servers/test_xanad_workspace_mcp_grade_human.py": 200,
}
HARD_LIMIT_OVERRIDES: dict[str, int] = {
    # Lifecycle apply executor: grew with _run_backup_phase, _run_actions_phase, _run_post_apply_phase
    # helpers, then _ActionCtx NamedTuple and per-action handler extraction (H3 refactor).
    "scripts/lifecycle/_xanad/_apply_executor.py": 430,
    # Web MCP server: grew with robots.txt support, retry logic, and WAF classification.
    "mcp/scripts/webMcp.py": 510,
    # Web MCP test suite: expanded to cover new fetch, retry, and search paths.
    "tests/mcp_servers/test_web_mcp.py": 470,
    # Workspace MCP (pre-existing): grew with command hardening and workspace_grade_human.
    "mcp/scripts/xanadWorkspaceMcp.py": 540,
    # Git MCP server: grew with structured mutation envelopes, _run_flags_completed,
    # _mutation_result helper, git_diff_staged_stat / git_diff_unstaged_stat tools,
    # extended stash/rebase/push tool surface for the Commit-agent migration,
    # and git_merge (start/continue/abort) to replace runCommands for merge workflows.
    "mcp/scripts/gitMcp.py": 600,
    # xanadEval _common.py: grew with retry logic in _call_model, text/behavior grader
    # overhauls (AND semantics, not_contains, regex_match/not_match, partial scoring,
    # min_tokens), new grader types (_grade_json_schema, _grade_program, _grade_llm,
    # _grade_llm_comparison), and extended _run_graders dispatch for all grader types.
    "tools/xanadEval/_common.py": 760,
    # xanadEval _graders_ext.py: all nine extended grader types (adds script/human/skill_invocation).
    "tools/xanadEval/_graders_ext.py": 800,
    # graders test: grew with LlmGraderTests and LlmComparisonGraderTests.
    "tests/tools/test_xanadEval_graders.py": 520,
    # graders_ext2 test: new test module for script/human/skill_invocation/max_calls.
    "tests/tools/test_xanadEval_graders_ext2.py": 340,
    # xanadEval runtime tests: grew with RetryTests, ExpectedFieldTests, TagsFilterTests
    # covering the new _call_model retry, expected task field, and --tags filter features;
    # AgentSurfaceResolutionTests + H2 zero-filter guard covering eval surface resolution;
    # and GradeCommandTests expanded with expected-grader re-grading coverage (C1).
    "tests/tools/test_xanadEval_runtime.py": 740,
    # graders_ext tests: all nine extended grader unit test classes.
    "tests/tools/test_xanadEval_graders_ext.py": 700,
    # workspace_grade_human MCP tests.
    "tests/mcp_servers/test_xanad_workspace_mcp_grade_human.py": 220,
    # xanadEval graders extension test suite: comprehensive grader coverage requires extended length.
    # GE-T1: added three regression tests for _grade_trigger skill_path traversal prevention.
    "tests/tools/test_xanadEval_graders_ext.py": 820,
    # Memory MCP shared module: grew with versioned migration helpers and session isolation.
    "mcp/scripts/_memory_mcp_shared.py": 460,
    # Memory MCP entrypoint: grew with session_id threading and branch-scoped rule fixes.
    "mcp/scripts/memoryMcp.py": 450,
    # apply_contracts test: grew with S1 backup/archive contract validation tests and
    # S2 delete-surface restriction tests.
    "tests/lifecycle/test_apply_contracts.py": 520,
}


def collect_files(roots: list[str]) -> list[Path]:
    if roots:
        return [Path(p) for p in roots if Path(p).is_file()]
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [
            Path(p)
            for p in result.stdout.splitlines()
            if p and Path(p).suffix in EXTENSIONS
            and not p.startswith(".github/")
        ]
    except (subprocess.CalledProcessError, OSError):
        # Fallback: walk the repo root (git unavailable or not a git repo)
        repo_root = Path(__file__).resolve().parents[1]
        return [
            path
            for path in repo_root.rglob("*")
            if path.is_file() and path.suffix in EXTENSIONS
            and ".git" not in path.parts
            and ".github" not in path.parts
        ]


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _path_key(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def warning_limit_for(path: Path) -> int:
    return WARN_LIMIT_OVERRIDES.get(_path_key(path), WARN_LIMIT)


def hard_limit_for(path: Path) -> int:
    return HARD_LIMIT_OVERRIDES.get(_path_key(path), HARD_LIMIT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hard-only", action="store_true", help="Only report hard-limit violations.")
    parser.add_argument("files", nargs="*", help="Files to check (default: all tracked files).")
    args = parser.parse_args(argv)

    files = collect_files(args.files)
    warnings: list[tuple[Path, int, int]] = []
    violations: list[tuple[Path, int, int]] = []
    read_errors: list[tuple[Path, str]] = []

    for path in sorted(files):
        try:
            n = count_lines(path)
        except OSError as exc:
            read_errors.append((path, str(exc)))
            continue
        warn_limit = warning_limit_for(path)
        hard_limit = hard_limit_for(path)
        if n > hard_limit:
            violations.append((path, n, hard_limit))
        elif n > warn_limit and not args.hard_only:
            warnings.append((path, n, warn_limit))

    for path, n, warn_limit in warnings:
        suffix = "" if warn_limit == WARN_LIMIT else f"  (warn limit: {warn_limit})"
        print(f"WARN  {n:>5} lines  {path}{suffix}", file=sys.stderr)

    for path, err in read_errors:
        print(f"ERROR  unreadable  {path}: {err}", file=sys.stderr)

    for path, n, hard_limit in violations:
        print(f"ERROR {n:>5} lines  {path}  (hard limit: {hard_limit})", file=sys.stderr)

    if violations or read_errors:
        print(
            f"\nLOC gate FAILED: {len(violations)} file(s) exceed the hard limit, "
            f"{len(read_errors)} unreadable.",
            file=sys.stderr,
        )
        return 1

    if warnings:
        print(
            f"\nLOC gate: {len(warnings)} file(s) exceed their warning threshold.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
