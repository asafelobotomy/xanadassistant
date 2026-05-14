"""Control workspace templates for developer sandbox benchmarking.

Plain installs with no packs selected — used as the timing and state baseline
when comparing inspect/check results against agent/pack workspaces.
Import via sandbox.py; do not run directly.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_CLI = REPO_ROOT / "scripts" / "lifecycle" / "xanadAssistant.py"


def _apply_in_ws(workspace: Path, answers: dict | None = None) -> None:
    extra: list[str] = []
    if answers:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump(answers, fh)
            extra = ["--answers", fh.name]
    try:
        r = subprocess.run(
            [sys.executable, str(_CLI), "apply", "--non-interactive", "--json", *extra,
             "--workspace", str(workspace), "--package-root", str(REPO_ROOT)],
            capture_output=True, text=True, check=False,
        )
        if r.returncode not in (0, 9):
            print(f"  ! apply exited {r.returncode}: {r.stderr.strip()[:120]}", file=sys.stderr)
    finally:
        if extra:
            Path(extra[1]).unlink(missing_ok=True)


# ── Control workspaces ───────────────────────────────────────────────────────

def _control_default(ws: Path) -> None:
    """Plain install, no packs, no project files — pure timing baseline."""
    ws.mkdir(parents=True, exist_ok=True)
    _apply_in_ws(ws)


def _control_python(ws: Path) -> None:
    """Plain install + requirements.txt — baseline with Python scanner tokens resolved."""
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "requirements.txt").write_text("requests>=2.31.0\n", encoding="utf-8")
    _apply_in_ws(ws)


def _control_node(ws: Path) -> None:
    """Plain install + package.json — baseline with Node scanner tokens resolved."""
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "package.json").write_text(
        json.dumps({"name": "control-node", "version": "1.0.0",
                    "scripts": {"test": "jest"}}, indent=2) + "\n",
        encoding="utf-8",
    )
    _apply_in_ws(ws)


CONTROL_WORKSPACES: dict[str, dict] = {
    "control-default": {
        "desc": "Default install, no packs (timing baseline)",
        "fn": _control_default,
        "expected_state": "installed",
        "group": "control",
    },
    "control-python": {
        "desc": "Default install + requirements.txt, no packs (Python scanner baseline)",
        "fn": _control_python,
        "expected_state": "installed",
        "group": "control",
    },
    "control-node": {
        "desc": "Default install + package.json, no packs (Node scanner baseline)",
        "fn": _control_node,
        "expected_state": "installed",
        "group": "control",
    },
}
