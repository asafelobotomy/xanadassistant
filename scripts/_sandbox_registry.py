"""Workspace registry shape validators for the developer sandbox.

Called at test time to assert that all module-level registry dicts carry
the required metadata keys and valid shapes.
"""
from __future__ import annotations

_REQUIRED_KEYS = frozenset({"desc", "fn", "expected_state", "expected_exit_codes", "expected_findings"})
_REQUIRED_EC_CMDS = frozenset({"inspect", "check"})


def validate_entry(name: str, entry: dict) -> list[str]:
    """Return validation error strings for one workspace entry (empty list = valid)."""
    errors: list[str] = []
    for key in _REQUIRED_KEYS:
        if key not in entry:
            errors.append(f"{name!r}: missing required key {key!r}")
    ec = entry.get("expected_exit_codes")
    if isinstance(ec, dict):
        for cmd in _REQUIRED_EC_CMDS:
            if cmd not in ec:
                errors.append(f"{name!r}: expected_exit_codes missing {cmd!r} entry")
    elif ec is not None:
        errors.append(f"{name!r}: expected_exit_codes must be a dict")
    findings = entry.get("expected_findings")
    if findings is not None and not isinstance(findings, list):
        errors.append(f"{name!r}: expected_findings must be a list or None")
    return errors


def validate_workspace_dict(workspaces: dict, *, skip_missing_meta: bool = False) -> list[str]:
    """Return all validation errors across a workspace registry dict.

    skip_missing_meta=True: skip entries without expected_exit_codes (e.g. base workspaces
    in sandbox.py that intentionally omit lifecycle metadata).
    """
    errors: list[str] = []
    for name, entry in workspaces.items():
        if skip_missing_meta and "expected_exit_codes" not in entry:
            continue
        errors.extend(validate_entry(name, entry))
    return errors
