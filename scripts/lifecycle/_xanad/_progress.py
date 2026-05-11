from __future__ import annotations

import os
import sys
from pathlib import Path

from scripts.lifecycle._xanad._emit import emit_json, emit_json_lines
from scripts.lifecycle._xanad._errors import _State
from scripts.lifecycle._xanad._source import build_source_summary


def _color_enabled() -> bool:
    """Return True when ANSI color output is appropriate."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stderr.isatty()


def _ansi(code: str, text: str) -> str:
    """Wrap text in an ANSI escape sequence when color is enabled."""
    if not _color_enabled():
        return text
    return f"\033[{code}m{text}\033[0m"


def _phase(label: str) -> str:
    return _ansi("36", label)  # cyan


def _ok(text: str) -> str:
    return _ansi("32", text)  # green


def _warn(text: str) -> str:
    return _ansi("33", text)  # yellow


def _log_progress(message: str) -> None:
    """Write a line to the optional log file when --log-file is active."""
    if _State.log_file is not None:
        _State.log_file.write(message + "\n")
        _State.log_file.flush()


def emit_agent_progress(payload: dict) -> None:
    def out(msg: str) -> None:
        print(msg, file=sys.stderr)
        _log_progress(msg)

    out("xanadAssistant")
    if payload["command"] == "inspect":
        out(_phase("Preflight"))
        out("  Package contracts loaded")
        out(f"  Install state: {payload['result']['installState']}")
        out(f"  Manifest entries: {payload['result']['manifestSummary']['declared']}")
        if payload.get("warnings"):
            out(_warn(f"  Warnings: {len(payload['warnings'])}"))
        return

    if payload["command"] == "check":
        out(_phase("Preflight"))
        check_status = payload["status"]
        out(f"  Check status: {_ok(check_status) if check_status == 'clean' else _warn(check_status)}")
        out(f"  Missing targets: {payload['result']['summary']['missing']}")
        return

    if payload["command"] == "interview":
        out(_phase("Interview"))
        out(f"  Questions emitted: {payload['result']['questionCount']}")
        return

    if payload["command"] == "plan":
        out(_phase("Preflight"))
        out(f"  Install state: {payload['result']['installState']}")
        out(_phase("Plan"))
        out(f"  Planned writes: {sum(payload['result']['writes'].values())}")
        if payload["result"]["conflicts"]:
            out(_warn(f"  Conflict classes: {len(payload['result']['conflicts'])}"))
        if payload["result"]["approvalRequired"]:
            out(_warn("  Waiting on Copilot"))
        out(_phase("Receipt"))
        out(f"  Status: {payload['status']}")
        return

    if payload["command"] in {"apply", "update", "repair", "factory-restore"}:
        out(_phase("Apply"))
        out(f"  Files added: {payload['result']['writes']['added']}")
        out(f"  Files replaced: {payload['result']['writes']['replaced']}")
        out(f"  Summary written: {payload['result']['summary']['path']}")
        if payload["result"].get("dryRun"):
            out(_warn("  Dry run: no files were written."))
        out(_phase("Validate"))
        validation_status = payload["result"]["validation"]["status"]
        out(f"  Validation: {_ok(validation_status) if validation_status == 'passed' else _warn(validation_status)}")
        out(_phase("Receipt"))
        out(f"  Status: {_ok(payload['status']) if payload['status'] == 'ok' else _warn(payload['status'])}")
        return

    out(_phase("Preflight"))


def emit_payload(payload: dict, ui_mode: str, use_json_lines: bool) -> None:
    if ui_mode == "agent":
        emit_agent_progress(payload)

    if use_json_lines:
        emit_json_lines(payload)
        return
    emit_json(payload)


def build_not_implemented_payload(command: str, workspace: Path, package_root: Path, mode: str | None = None) -> dict:
    return {
        "command": command,
        "mode": mode,
        "workspace": str(workspace),
        "source": build_source_summary(package_root),
        "status": "not-implemented",
        "warnings": [],
        "errors": [
            {
                "code": "not_implemented",
                "message": f"{command} is not implemented in the current lifecycle slice.",
                "details": {"mode": mode},
            }
        ],
        "result": {},
    }
