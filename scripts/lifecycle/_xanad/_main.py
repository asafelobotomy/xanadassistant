from __future__ import annotations

import argparse
from pathlib import Path

from scripts.lifecycle._xanad._execute_apply import build_apply_result, build_execution_result
from scripts.lifecycle._xanad._check import build_check_result
from scripts.lifecycle._xanad._cli import build_parser
from scripts.lifecycle._xanad._errors import LifecycleCommandError, _State
from scripts.lifecycle._xanad._inspect import build_inspect_result
from scripts.lifecycle._xanad._interview import build_error_payload, build_interview_result
from scripts.lifecycle._xanad._plan_a import write_plan_output, write_report_output
from scripts.lifecycle._xanad._plan_b import build_plan_result
from scripts.lifecycle._xanad._progress import build_not_implemented_payload, emit_payload
from scripts.lifecycle._xanad._source import resolve_effective_package_root, resolve_workspace


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    log_file_path = getattr(args, "log_file", None)
    if log_file_path:
        _State.log_file = Path(log_file_path).open("w", encoding="utf-8")

    try:
        return _run_lifecycle(args)
    finally:
        if _State.log_file is not None:
            _State.log_file.close()
            _State.log_file = None


def _run_lifecycle(args: argparse.Namespace) -> int:
    """Inner lifecycle dispatch — separated so main() can close _State.log_file on exit."""
    workspace = resolve_workspace(args.workspace)
    use_json_lines = args.json_lines

    try:
        package_root, _resolved_source_info = resolve_effective_package_root(
            getattr(args, "package_root", None),
            getattr(args, "source", None),
            getattr(args, "version", None),
            getattr(args, "ref", None),
        )
        _State.session_source_info = _resolved_source_info
        # Keep xanad_assistant module attribute in sync for backward compat.
        import scripts.lifecycle.xanad_assistant as _xa_mod
        _xa_mod._session_source_info = _resolved_source_info
    except LifecycleCommandError as error:
        payload, exit_code = build_error_payload(
            getattr(args, "command", "unknown"),
            workspace, Path("."),
            error.code, error.message, error.exit_code, details=error.details,
        )
        emit_payload(payload, args.ui, use_json_lines)
        return exit_code

    if args.command == "inspect":
        payload = build_inspect_result(workspace, package_root)
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "check":
        payload = build_check_result(workspace, package_root)
        emit_payload(payload, args.ui, use_json_lines)
        return 0 if payload["status"] == "clean" else 7

    if args.command == "interview":
        payload = build_interview_result(workspace, package_root, args.mode)
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
        plan_out_path = write_plan_output(args.plan_out, payload)
        if plan_out_path is not None:
            payload["result"]["planOut"] = plan_out_path
        emit_payload(payload, args.ui, use_json_lines)
        return 0 if not payload["errors"] else 1

    if args.command == "apply":
        try:
            payload = build_apply_result(workspace, package_root, args.answers, args.non_interactive, dry_run=args.dry_run)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "apply", workspace, package_root,
                error.code, error.message, error.exit_code, mode="setup", details=error.details,
            )
            report_out_path = write_report_output(args.report_out, payload)
            if report_out_path is not None:
                payload.setdefault("result", {})["reportOut"] = report_out_path
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code
        report_out_path = write_report_output(args.report_out, payload)
        if report_out_path is not None:
            payload["result"]["reportOut"] = report_out_path
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "update":
        try:
            payload = build_execution_result("update", "update", workspace, package_root, args.answers, args.non_interactive, dry_run=args.dry_run)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "update", workspace, package_root,
                error.code, error.message, error.exit_code, mode="update", details=error.details,
            )
            report_out_path = write_report_output(args.report_out, payload)
            if report_out_path is not None:
                payload.setdefault("result", {})["reportOut"] = report_out_path
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code
        report_out_path = write_report_output(args.report_out, payload)
        if report_out_path is not None:
            payload["result"]["reportOut"] = report_out_path
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "repair":
        try:
            payload = build_execution_result("repair", "repair", workspace, package_root, args.answers, args.non_interactive, dry_run=args.dry_run)
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "repair", workspace, package_root,
                error.code, error.message, error.exit_code, mode="repair", details=error.details,
            )
            report_out_path = write_report_output(args.report_out, payload)
            if report_out_path is not None:
                payload.setdefault("result", {})["reportOut"] = report_out_path
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code
        report_out_path = write_report_output(args.report_out, payload)
        if report_out_path is not None:
            payload["result"]["reportOut"] = report_out_path
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    if args.command == "factory-restore":
        try:
            payload = build_execution_result(
                "factory-restore", "factory-restore", workspace, package_root,
                args.answers, args.non_interactive, dry_run=args.dry_run,
            )
        except LifecycleCommandError as error:
            payload, exit_code = build_error_payload(
                "factory-restore", workspace, package_root,
                error.code, error.message, error.exit_code,
                mode="factory-restore", details=error.details,
            )
            report_out_path = write_report_output(args.report_out, payload)
            if report_out_path is not None:
                payload.setdefault("result", {})["reportOut"] = report_out_path
            emit_payload(payload, args.ui, use_json_lines)
            return exit_code
        report_out_path = write_report_output(args.report_out, payload)
        if report_out_path is not None:
            payload["result"]["reportOut"] = report_out_path
        emit_payload(payload, args.ui, use_json_lines)
        return 0

    mode = getattr(args, "mode", None)
    payload = build_not_implemented_payload(args.command, workspace, package_root, mode)
    emit_payload(payload, args.ui, use_json_lines)
    return 1
