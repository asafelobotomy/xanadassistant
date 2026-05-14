#!/usr/bin/env python3
"""Agent quality eval harness for xanadAssistant.

Commands: triage [--model MODEL] [--save]

Requires:
  GITHUB_TOKEN   — GitHub PAT with models:read scope
  XANAD_EVAL_ENABLED=1  — explicit opt-in (prevents accidental API charges)

Usage:
  python3 scripts/eval.py triage
  python3 scripts/eval.py triage --model anthropic/claude-haiku-4-5 --save
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _eval_triage


def _require_eval_enabled() -> None:
    if not os.getenv("XANAD_EVAL_ENABLED"):
        print(
            "Set XANAD_EVAL_ENABLED=1 to enable the eval harness.\n"
            "This flag is required to prevent unintended API usage charges.",
            file=sys.stderr,
        )
        sys.exit(2)
    if not os.getenv("GITHUB_TOKEN"):
        print(
            "GITHUB_TOKEN is not set. Provide a token with models:read scope.",
            file=sys.stderr,
        )
        sys.exit(2)


def cmd_triage(model: str, save: bool) -> None:
    _require_eval_enabled()
    print(f"Running triage eval  ({len(__import__('_eval_tasks').TRIAGE_TASKS)} tasks, model: {model})")
    data = _eval_triage.run(model=model)
    rc = _eval_triage.print_results(data)
    if save:
        _eval_triage.save_results(data)
    sys.exit(rc)


def main() -> None:
    p = argparse.ArgumentParser(
        prog="eval.py",
        description="Agent quality eval harness.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    triage_p = sub.add_parser("triage", help="Eval the Triage agent vs control")
    triage_p.add_argument(
        "--model",
        default=_eval_triage.DEFAULT_MODEL,
        help=f"GitHub Models model ID (default: {_eval_triage.DEFAULT_MODEL})",
    )
    triage_p.add_argument(
        "--save",
        action="store_true",
        help="Save results to results/eval-triage-<timestamp>.json",
    )

    args = p.parse_args()
    if args.cmd == "triage":
        cmd_triage(args.model, args.save)


if __name__ == "__main__":
    main()
