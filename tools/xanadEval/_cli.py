"""CLI entry point for xanadEval.

Parses command-line arguments and dispatches to the appropriate command function.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import _DEFAULT_MODEL, _DEFAULT_RESULTS_DIR
from _static import cmd_check, cmd_suggest, cmd_tokens
from _reporting import cmd_compare, cmd_coverage, cmd_report
from _dynamic import cmd_grade, cmd_run
from _feedback import cmd_dev, cmd_quality
from _results import cmd_compare_results, cmd_results_list, cmd_results_view


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
    p_run.add_argument(
        "--tags",
        nargs="*",
        default=None,
        metavar="TAG",
        help="Only run tasks with at least one of these tags (e.g. --tags smoke positive)",
    )
    _add_format(p_run)

    p_grd = sub.add_parser(
        "grade",
        help="Re-run graders against existing results without re-invoking the model",
    )
    p_grd.add_argument("eval_path", metavar="eval.yaml", help="Path to the eval spec")
    p_grd.add_argument("results_path", metavar="results.json",
                       help="Path to the results file to re-grade")
    p_grd.add_argument(
        "--model",
        default=None,
        metavar="MODEL",
        help="Override the model for prompt graders (default: use model from results file)",
    )
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
        return cmd_run(args.eval_path, args.model, args.trials, args.fmt,
                       tags=args.tags or None)
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
