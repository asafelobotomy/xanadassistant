from __future__ import annotations

import argparse
from functools import partial


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", required=True, help="Consumer repository to inspect or modify.")
    parser.add_argument("--package-root", default=None, help="Local xanadAssistant package checkout.")
    parser.add_argument("--source", help="Package source identifier.")
    parser.add_argument("--version", help="Requested release version.")
    parser.add_argument("--ref", help="Requested source ref.")
    parser.add_argument("--allow-mutable-ref", action="store_true", help="Allow branch-like remote refs; prefer --version or a full commit SHA.")
    parser.add_argument("--json", action="store_true", help="Emit a single JSON result.")
    parser.add_argument("--json-lines", action="store_true", help="Emit JSON Lines protocol events.")
    parser.add_argument("--non-interactive", action="store_true", help="Disable interactive prompting.")
    parser.add_argument("--dry-run", action="store_true", help="Avoid managed writes.")
    parser.add_argument("--answers", help="Path to answer file.")
    parser.add_argument("--resolutions", default=None, help="Path to conflict-resolutions.json for pre-existing file decisions.")
    parser.add_argument("--plan-out", help="Path to write a serialized plan.")
    parser.add_argument("--report-out", help="Path to write a structured report.")
    parser.add_argument("--log-file", help="Path to write a plain-text operational log.")
    parser.add_argument("--ui", choices=["quiet", "agent", "tui"], default="quiet", help="Presentation mode.")


def build_parser() -> argparse.ArgumentParser:
    parser_class = partial(argparse.ArgumentParser, allow_abbrev=False)
    parser = parser_class(description="xanadAssistant lifecycle tool.")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=parser_class)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect workspace state.")
    add_common_arguments(inspect_parser)

    check_parser = subparsers.add_parser("health-check", help="Check managed workspace state.")
    add_common_arguments(check_parser)

    interview_parser = subparsers.add_parser("interview", help="Emit structured lifecycle questions.")
    add_common_arguments(interview_parser)
    interview_parser.add_argument(
        "--mode",
        choices=["setup", "update", "repair", "factory-restore"],
        default="setup",
        help="Lifecycle mode requiring questions.",
    )

    for command in ("setup", "apply", "update", "repair", "factory-restore"):
        help_text = (
            "Retired command tombstone; use setup, update, repair, or factory-restore instead."
            if command == "apply"
            else f"{command} workspace state."
        )
        command_parser = subparsers.add_parser(command, help=help_text)
        add_common_arguments(command_parser)
        if command in {"setup", "apply"}:
            command_parser.add_argument("--plan", default=None, help="Path to a serialized lifecycle plan to apply.")
        if command in {"repair", "factory-restore"}:
            command_parser.add_argument(
                "--sanitize",
                action="store_true",
                help="Archive unmanaged Copilot-shaped files found in managed directories.",
            )

    plan_parser = subparsers.add_parser("plan", help="Generate a lifecycle plan.")
    plan_subparsers = plan_parser.add_subparsers(dest="mode", required=True, parser_class=parser_class)
    for mode in ("setup", "update", "repair", "factory-restore"):
        mode_parser = plan_subparsers.add_parser(mode, help=f"Generate a {mode} plan.")
        add_common_arguments(mode_parser)
        if mode in {"repair", "factory-restore"}:
            mode_parser.add_argument(
                "--sanitize",
                action="store_true",
                help="Include sanitize archive actions for unmanaged Copilot-shaped files.",
            )

    health_check_parser = subparsers.add_parser("health-report", help="Collect and format a workspace health report.")
    add_common_arguments(health_check_parser)
    health_check_parser.add_argument("--label", default=None, help="Optional workspace alias for the health report.")

    return parser
