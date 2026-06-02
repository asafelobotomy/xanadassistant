from __future__ import annotations

from pathlib import Path

from scripts.lifecycle._xanad._apply_executor import execute_apply_plan
from scripts.lifecycle._xanad._execute_apply_compat import (
    load_apply_plan as _load_apply_plan,
    validate_apply_plan_package as _validate_apply_plan_package,
    validate_apply_plan_paths as _validate_apply_plan_paths,
    validate_relative_plan_path as _validate_relative_plan_path_impl,
)
from scripts.lifecycle._xanad._errors import DEFAULT_POLICY_PATH, LifecycleCommandError
from scripts.lifecycle._xanad._loader import load_json, load_manifest
from scripts.lifecycle._xanad._merge import sha256_json
from scripts.lifecycle._xanad._migration import CURRENT_PACKAGE_NAME
from scripts.lifecycle._xanad._plan_b import build_plan_result
from scripts.lifecycle._xanad._source import build_source_summary


def _validate_relative_plan_path(path_value: object, field: str) -> str:
    return _validate_relative_plan_path_impl(path_value, field)


def validate_apply_plan_paths(plan_payload: dict, package_root: Path) -> None:
    _validate_apply_plan_paths(
        plan_payload,
        package_root,
        load_manifest=load_manifest,
        load_json=load_json,
        default_policy_path=DEFAULT_POLICY_PATH,
    )


def load_apply_plan(plan_path: str | None, workspace: Path) -> dict:
    return _load_apply_plan(plan_path, workspace)


def validate_apply_plan_package(plan_payload: dict, package_root: Path) -> None:
    _validate_apply_plan_package(
        plan_payload,
        package_root,
        current_package_name=CURRENT_PACKAGE_NAME,
        build_source_summary=build_source_summary,
        load_manifest=load_manifest,
        load_json=load_json,
        sha256_json=sha256_json,
        default_policy_path=DEFAULT_POLICY_PATH,
    )


def _execute_serialized_plan(
    command: str,
    workspace: Path,
    package_root: Path,
    dry_run: bool,
    plan_path: str | None,
    expected_mode: str | None = None,
) -> dict:
    plan_payload = load_apply_plan(plan_path, workspace)
    if expected_mode is not None and plan_payload["mode"] != expected_mode:
        raise LifecycleCommandError(
            "contract_input_failure",
            f"{command.capitalize()} requires a serialized {expected_mode} plan.",
            4,
            {"command": command, "expectedMode": expected_mode, "mode": plan_payload["mode"]},
        )
    validate_apply_plan_paths(plan_payload, package_root)
    validate_apply_plan_package(plan_payload, package_root)
    if plan_payload["result"].get("conflictDetails"):
        raise LifecycleCommandError(
            "approval_or_answers_required",
            "Pack token conflicts must be resolved before applying.",
            6,
            {"questionIds": [c["questionId"] for c in plan_payload["result"]["conflictDetails"]]},
        )
    apply_result = execute_apply_plan(workspace, package_root, plan_payload, dry_run=dry_run)
    return {
        "command": command,
        "mode": plan_payload["mode"],
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "ok",
        "warnings": plan_payload.get("warnings", []),
        "errors": [],
        "result": apply_result,
    }


def build_execution_result(
    command: str, mode: str, workspace: Path, package_root: Path,
    answers_path: str | None, non_interactive: bool, dry_run: bool = False,
    resolutions_path: str | None = None,
    sanitize: bool = False,
) -> dict:
    plan_payload = build_plan_result(workspace, package_root, mode, answers_path, non_interactive, resolutions_path=resolutions_path, sanitize=sanitize)
    if plan_payload["result"].get("conflictDetails"):
        raise LifecycleCommandError(
            "approval_or_answers_required",
            "Pack token conflicts must be resolved before applying.", 6,
            {"questionIds": [c["questionId"] for c in plan_payload["result"]["conflictDetails"]]},
        )
    apply_result = execute_apply_plan(workspace, package_root, plan_payload, dry_run=dry_run)
    return {
        "command": command, "mode": mode,
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "ok",
        "warnings": plan_payload["warnings"],
        "errors": [],
        "result": apply_result,
    }


def build_apply_result(
    workspace: Path, package_root: Path, answers_path: str | None,
    non_interactive: bool, dry_run: bool = False, resolutions_path: str | None = None,
    plan_path: str | None = None,
) -> dict:
    if answers_path is not None:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Apply does not accept --answers; answer collection must be resolved before serializing the plan.",
            4,
            {"argument": "--answers"},
        )
    if non_interactive:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Apply does not accept --non-interactive; the serialized plan already freezes interactive decisions.",
            4,
            {"argument": "--non-interactive"},
        )
    if resolutions_path is not None:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Apply does not accept --resolutions; conflict decisions must be recorded in the serialized plan.",
            4,
            {"argument": "--resolutions"},
        )
    return _execute_serialized_plan("apply", workspace, package_root, dry_run, plan_path)


def build_setup_result(
    workspace: Path,
    package_root: Path,
    answers_path: str | None = None,
    non_interactive: bool = False,
    dry_run: bool = False,
    resolutions_path: str | None = None,
    plan_path: str | None = None,
) -> dict:
    if answers_path is not None:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Setup does not accept --answers; answer collection must be resolved before serializing the plan.",
            4,
            {"argument": "--answers"},
        )
    if non_interactive:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Setup does not accept --non-interactive; the serialized plan already freezes interactive decisions.",
            4,
            {"argument": "--non-interactive"},
        )
    if resolutions_path is not None:
        raise LifecycleCommandError(
            "contract_input_failure",
            "Setup does not accept --resolutions; conflict decisions must be recorded in the serialized plan.",
            4,
            {"argument": "--resolutions"},
        )
    return _execute_serialized_plan("setup", workspace, package_root, dry_run, plan_path, expected_mode="setup")
