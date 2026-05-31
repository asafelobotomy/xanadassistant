from __future__ import annotations

import argparse
from pathlib import Path

from scripts.lifecycle._xanad._execute_apply import build_apply_result, build_execution_result, build_setup_result, load_apply_plan
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


def _dispatch_simple_command(
    command: str,
    builder,
    args: argparse.Namespace,
    workspace: Path,
    package_root: Path,
    use_json_lines: bool,
    *,
    success_exit_fn=lambda payload: 0,
) -> int:
    """Run a single lifecycle command builder, emit the payload, and return the exit code."""
    try:
        payload = builder()
    except LifecycleCommandError as error:
        payload, exit_code = build_error_payload(
            command, workspace, package_root,
            error.code, error.message, error.exit_code,
            mode=getattr(args, "mode", None), details=error.details,
        )
        emit_payload(payload, args.ui, use_json_lines)
        return exit_code
    emit_payload(payload, args.ui, use_json_lines)
    return success_exit_fn(payload)


def _run_execution_command(
    args: argparse.Namespace,
    workspace: Path,
    package_root: Path,
    use_json_lines: bool,
    command: str,
    mode: str,
) -> int:
    error_mode = mode
    try:
        if command == "setup":
            payload = build_setup_result(
                workspace,
                package_root,
                answers_path=args.answers,
                non_interactive=args.non_interactive,
                dry_run=args.dry_run,
                resolutions_path=getattr(args, "resolutions", None),
                plan_path=getattr(args, "plan", None),
            )
            error_mode = payload.get("mode")
        elif command == "apply":
            payload = build_apply_result(
                workspace,
                package_root,
                args.answers,
                args.non_interactive,
                dry_run=args.dry_run,
                resolutions_path=getattr(args, "resolutions", None),
                plan_path=getattr(args, "plan", None),
            )
            error_mode = payload.get("mode")
        else:
            payload = build_execution_result(
                command,
                mode,
                workspace,
                package_root,
                args.answers,
                args.non_interactive,
                dry_run=args.dry_run,
                resolutions_path=getattr(args, "resolutions", None),
            )
    except LifecycleCommandError as error:
        if command in {"setup", "apply"}:
            plan_path = getattr(args, "plan", None)
            if plan_path:
                try:
                    error_mode = load_apply_plan(plan_path, workspace).get("mode")
                except LifecycleCommandError:
                    error_mode = None
        payload, exit_code = build_error_payload(
            command,
            workspace,
            package_root,
            error.code,
            error.message,
            error.exit_code,
            mode=error_mode,
            details=error.details,
        )
        _attach_output_path(args.report_out, payload, "reportOut")
        emit_payload(payload, args.ui, use_json_lines)
        return exit_code

    _attach_output_path(args.report_out, payload, "reportOut")
    emit_payload(payload, args.ui, use_json_lines)
    return 0


def _build_retired_apply_payload(args: argparse.Namespace, workspace: Path) -> tuple[dict, int]:
    mode = None
    plan_path = getattr(args, "plan", None)
    if plan_path:
        try:
            mode = load_apply_plan(plan_path, workspace).get("mode")
        except LifecycleCommandError:
            mode = None

    replacements = {
        "setup": "setup",
        "update": "update",
        "repair": "repair",
        "factory-restore": "factory-restore",
    }
    if mode == "setup":
        message = "The apply command is retired. Use setup with this serialized setup plan instead."
    elif mode in {"update", "repair", "factory-restore"}:
        message = f"The apply command is retired. Use the top-level {mode} command instead of applying a serialized {mode} plan."
    else:
        message = "The apply command is retired. Use setup for serialized setup plans, or use the top-level update, repair, or factory-restore commands."

    return (
        {
            "command": "apply",
            "mode": mode,
            "workspace": str(workspace),
            "source": {"kind": "retired-command"},
            "status": "error",
            "warnings": [],
            "errors": [
                {
                    "code": "retired_command",
                    "message": message,
                    "details": {
                        "retiredCommand": "apply",
                        "replacementCommands": replacements,
                    },
                }
            ],
            "result": {},
        },
        4,
    )


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
    write_commands = {"setup"}
    require_exists_commands = {"inspect", "health-check"}
    workspace = resolve_workspace(
        args.workspace,
        create=args.command in write_commands,
        require_exists=args.command in require_exists_commands,
    )
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

    if args.command == "apply":
        payload, exit_code = _build_retired_apply_payload(args, workspace)
        _attach_output_path(args.report_out, payload, "reportOut")
        emit_payload(payload, args.ui, use_json_lines)
        return exit_code

    try:
        package_root, _resolved_source_info = resolve_effective_package_root(
            getattr(args, "package_root", None),
            getattr(args, "source", None),
            getattr(args, "version", None),
            getattr(args, "ref", None),
            getattr(args, "allow_mutable_ref", False),
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
        return _dispatch_simple_command(
            "inspect", lambda: build_inspect_result(workspace, package_root),
            args, workspace, package_root, use_json_lines,
        )

    if args.command == "health-check":
        return _dispatch_simple_command(
            "health-check", lambda: build_check_result(workspace, package_root),
            args, workspace, package_root, use_json_lines,
            success_exit_fn=lambda p: 0 if p["status"] == "clean" else 7,
        )

    if args.command == "interview":
        return _dispatch_simple_command(
            "interview", lambda: build_interview_result(workspace, package_root, args.mode),
            args, workspace, package_root, use_json_lines,
        )

    if args.command == "plan":
        try:
            payload = build_plan_result(workspace, package_root, args.mode, args.answers, args.non_interactive, resolutions_path=getattr(args, "resolutions", None))
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

    if args.command == "setup":
        return _run_execution_command(args, workspace, package_root, use_json_lines, "setup", None)

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

    if args.command == "health-report":
        from scripts.lifecycle._xanad._health_check import build_health_check_result
        try:
            payload = build_health_check_result(
                workspace, package_root, label=getattr(args, "label", None)
            )
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "health-report", workspace, package_root,
                error.code, error.message, error.exit_code, details=error.details,
            )
            _attach_output_path(args.report_out, payload, "reportOut")
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code
        _attach_output_path(args.report_out, payload, "reportOut")
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    mode = getattr(args, "mode", None)  # pragma: no cover
    payload = build_not_implemented_payload(args.command, workspace, package_root, mode)  # pragma: no cover
    emit_payload(payload, args.ui, use_json_lines)  # pragma: no cover
    return 1  # pragma: no cover
