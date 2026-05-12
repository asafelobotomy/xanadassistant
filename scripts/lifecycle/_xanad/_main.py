from __future__ import annotations

import argparse
from pathlib import Path

from scripts.lifecycle._xanad._execute_apply import build_apply_result, build_execution_result
from scripts.lifecycle._xanad._check import build_check_result
from scripts.lifecycle._xanad._cli import build_parser
from scripts.lifecycle._xanad._errors import LifecycleCommandError, _State
from scripts.lifecycle._xanad._inspect import build_inspect_result
from scripts.lifecycle._xanad._interview import build_error_payload, build_interview_result
from scripts.lifecycle._xanad._plan_a import write_plan_output
from scripts.lifecycle._xanad._plan_b import build_plan_result
from scripts.lifecycle._xanad._progress import build_not_implemented_payload, emit_payload
from scripts.lifecycle._xanad._source import resolve_effective_package_root, resolve_workspace


def _attach_output_path(path_value: str | None, payload: dict, result_key: str) -> None:
    output_path = write_plan_output(path_value, payload)
    if output_path is not None:
        payload.setdefault("result", {})[result_key] = output_path


def _run_execution_command(
    args: argparse.Namespace,
    workspace: Path,
    package_root: Path,
    use_json_lines: bool,
    command: str,
    mode: str,
) -> int:
    try:
        if command == "apply":
            payload = build_apply_result(
                workspace,
                package_root,
                args.answers,
                args.non_interactive,
                dry_run=args.dry_run,
            )
        else:
            payload = build_execution_result(
                command,
                mode,
                workspace,
                package_root,
                args.answers,
                args.non_interactive,
                dry_run=args.dry_run,
            )
    except LifecycleCommandError as error:
        payload, exit_code = build_error_payload(
            command,
            workspace,
            package_root,
            error.code,
            error.message,
            error.exit_code,
            mode=mode,
            details=error.details,
        )
        _attach_output_path(args.report_out, payload, "reportOut")
        emit_payload(payload, args.ui, use_json_lines)
        return exit_code

    _attach_output_path(args.report_out, payload, "reportOut")
    emit_payload(payload, args.ui, use_json_lines)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_file_path = getattr(args, "log_file", None)
    if log_file_path:
        try:
            _State.log_file = Path(log_file_path).open("w", encoding="utf-8")
        except OSError as exc:
            payload, exit_code = build_error_payload(
                getattr(args, "command", "unknown"),
                Path(getattr(args, "workspace", ".")),
                Path("."),
                "contract_input_failure",
                f"Cannot open log file: {exc}",
                4,
            )
            emit_payload(payload, getattr(args, "ui", "quiet"), False)
            return exit_code

    try:
        return _run_lifecycle(args)
    finally:
        if _State.log_file is not None:
            _State.log_file.close()
            _State.log_file = None


def _run_lifecycle(args: argparse.Namespace) -> int:
    """Inner lifecycle dispatch — separated so main() can close _State.log_file on exit."""
    write_commands = {"apply", "update", "repair", "factory-restore"}
    workspace = resolve_workspace(args.workspace, create=args.command in write_commands)
    if args.json and args.json_lines:
        payload, exit_code = build_error_payload(
            args.command,
            workspace,
            Path("."),
            "invalid_invocation",
            "--json and --json-lines cannot be used together.",
            2,
            mode=getattr(args, "mode", None),
            details={"flags": ["--json", "--json-lines"]},
        )
        emit_payload(payload, args.ui, False)
        return exit_code

    use_json_lines = bool(args.json_lines)

    try:
        package_root, _resolved_source_info = resolve_effective_package_root(
            getattr(args, "package_root", None),
            getattr(args, "source", None),
            getattr(args, "version", None),
            getattr(args, "ref", None),
        )
        _State.session_source_info = _resolved_source_info
    except LifecycleCommandError as error:
        payload, exit_code = build_error_payload(
            getattr(args, "command", "unknown"),
            workspace, Path("."),
            error.code, error.message, error.exit_code, details=error.details,
        )
        emit_payload(payload, args.ui, use_json_lines)
        return exit_code

    if args.command == "inspect":
        try:
            payload = build_inspect_result(workspace, package_root)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "inspect", workspace, package_root,
                error.code, error.message, error.exit_code, details=error.details,
            )
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "check":
        try:
            payload = build_check_result(workspace, package_root)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "check", workspace, package_root,
                error.code, error.message, error.exit_code, details=error.details,
            )
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code
        emit_payload(payload, args.ui, use_json_lines)
        return 0 if payload["status"] == "clean" else 7

    if args.command == "interview":
        try:
            payload = build_interview_result(workspace, package_root, args.mode)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "interview", workspace, package_root,
                error.code, error.message, error.exit_code,
                mode=args.mode, details=error.details,
            )
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "plan":
        try:
            payload = build_plan_result(workspace, package_root, args.mode, args.answers, args.non_interactive)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "plan", workspace, package_root,
                error.code, error.message, error.exit_code, mode=args.mode, details=error.details,
            )
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code
        _attach_output_path(args.plan_out, payload, "planOut")
        emit_payload(payload, args.ui, use_json_lines)
        return 0 if not payload["errors"] else 4

    if args.command == "apply":
        return _run_execution_command(args, workspace, package_root, use_json_lines, "apply", "setup")

    if args.command == "update":
        return _run_execution_command(args, workspace, package_root, use_json_lines, "update", "update")

    if args.command == "repair":
        return _run_execution_command(args, workspace, package_root, use_json_lines, "repair", "repair")

    if args.command == "factory-restore":
        return _run_execution_command(
            args,
            workspace,
            package_root,
            use_json_lines,
            "factory-restore",
            "factory-restore",
        )

    mode = getattr(args, "mode", None)  # pragma: no cover
    payload = build_not_implemented_payload(args.command, workspace, package_root, mode)  # pragma: no cover
    emit_payload(payload, args.ui, use_json_lines)  # pragma: no cover
    return 1  # pragma: no cover
