"""Workspace health check — collect xanadAssistant lifecycle state for reporting.

Collects only fields that pertain to the xanadAssistant installation itself.
No workspace file contents, project names, git state, or absolute paths are
included.  Local package-root paths are redacted to 'local'.
"""
from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.lifecycle._xanad._check import build_check_result
from scripts.lifecycle._xanad._inspect import collect_context
from scripts.lifecycle._xanad._source import build_source_summary

HEALTH_CHECK_SCHEMA_VERSION = "1"
_SAFE_SOURCE_PREFIXES = ("github:", "pypi:")
_REDACTED_WORKSPACE = "redacted"
_LOCAL_PACKAGE_ROOT = "local"


def _sanitize_source(source_summary: dict) -> str:
    """Return a privacy-safe source string. Local package-root paths become 'local'."""
    kind = source_summary.get("kind", "")
    if kind == "package-root":
        return _LOCAL_PACKAGE_ROOT
    raw = source_summary.get("source", "") or ""
    if any(raw.startswith(p) for p in _SAFE_SOURCE_PREFIXES):
        return raw
    return "unknown"


def _sanitize_source_summary(source_summary: dict) -> dict:
    """Return a privacy-safe source summary without exposing local filesystem paths."""
    sanitized = dict(source_summary)
    if "packageRoot" in sanitized:
        sanitized["packageRoot"] = _LOCAL_PACKAGE_ROOT
    return sanitized


def _extract_install_metadata(lockfile_state: dict, install_state: str) -> dict:
    data = lockfile_state.get("data", {})
    pkg = data.get("package", {})
    meta = data.get("installMetadata", {})
    timestamps = data.get("timestamps", {})
    manifest_block = data.get("manifest", {})
    return {
        "state": install_state,
        "version": pkg.get("version") or lockfile_state.get("installedVersion"),
        "profile": meta.get("profile") or data.get("profile"),
        "packs": meta.get("packs") or data.get("selectedPacks", []),
        "mcpEnabled": meta.get("mcpEnabled"),
        "appliedAt": timestamps.get("appliedAt"),
        "updatedAt": timestamps.get("updatedAt"),
        "manifestHash": manifest_block.get("hash"),
        "resolvedTokenConflicts": data.get("resolvedTokenConflicts", {}),
        "consumerResolutionCount": len(data.get("consumerResolutions", {})),
    }


def _extract_check_data(check_result: dict) -> dict:
    result = check_result.get("result", {})
    entries = [
        {
            "surface": e.get("surface"),
            "target": e.get("target"),
            "status": e.get("status"),
        }
        for e in result.get("entries", [])
        if e.get("status") not in ("skipped",)
    ]
    return {
        "status": check_result.get("status"),
        "summary": result.get("summary", {}),
        "warnings": [w.get("code") for w in check_result.get("warnings", [])],
        "entries": entries,
    }


def _format_issue_body(report: dict) -> str:
    pkg = report.get("package", {})
    install = report.get("install", {})
    check = report.get("check", {})
    system = report.get("system", {})
    label = report.get("label")

    packs_str = ", ".join(install.get("packs") or []) or "none"
    warnings_str = ", ".join(check.get("warnings") or []) or "none"
    label_line = f"\n**Label:** `{label}`" if label else ""

    drift_entries = [
        e for e in check.get("entries", [])
        if e.get("status") not in ("clean", "skipped")
    ]
    drift_section = ""
    if drift_entries:
        rows = "\n".join(
            f"| `{e.get('target', '')}` | {e.get('surface', '') or '—'} | {e.get('status', '')} |"
            for e in drift_entries[:30]
        )
        drift_section = (
            "\n\n### Drift Details\n\n"
            "| File | Surface | Status |\n"
            "|---|---|---|\n"
            f"{rows}"
        )

    summary = check.get("summary", {})
    summary_str = "  ".join(f"{k}: {v}" for k, v in summary.items() if v)

    return (
        "## xanadAssistant Workspace Health Check Report\n\n"
        f"**Generated:** {report.get('generatedAt')}{label_line}\n\n"
        "### Package\n\n"
        "| Field | Value |\n|---|---|\n"
        f"| Version | `{pkg.get('version') or 'unknown'}` |\n"
        f"| Source | `{pkg.get('source') or 'unknown'}` |\n\n"
        "### Install State\n\n"
        "| Field | Value |\n|---|---|\n"
        f"| State | `{install.get('state') or 'unknown'}` |\n"
        f"| Profile | `{install.get('profile') or 'unknown'}` |\n"
        f"| Packs | `{packs_str}` |\n"
        f"| MCP Enabled | `{install.get('mcpEnabled')}` |\n"
        f"| Applied At | `{install.get('appliedAt') or 'unknown'}` |\n"
        f"| Updated At | `{install.get('updatedAt') or 'unknown'}` |\n"
        f"| Consumer Resolutions | `{install.get('consumerResolutionCount', 0)}` file(s) kept |\n\n"
        "### Check\n\n"
        "| Field | Value |\n|---|---|\n"
        f"| Status | `{check.get('status') or 'unknown'}` |\n"
        f"| Warnings | `{warnings_str}` |\n"
        f"| Summary | `{summary_str}` |\n"
        f"{drift_section}\n\n"
        "### System\n\n"
        "| Field | Value |\n|---|---|\n"
        f"| Platform | `{system.get('platform') or 'unknown'}` |\n"
        f"| Python | `{system.get('python') or 'unknown'}` |\n\n"
        "### Health Check Metadata\n\n"
        "| Field | Value |\n|---|---|\n"
        f"| Schema Version | `{report.get('healthCheckSchemaVersion')}` |\n"
        f"| Manifest Hash | `{install.get('manifestHash') or 'unknown'}` |\n"
    )


def build_health_check_report(workspace: Path, package_root: Path, label: str | None = None) -> dict:
    """Collect xanadAssistant lifecycle state for this workspace.

    Returns a dict suitable for JSON serialisation and GitHub issue submission.
    All fields pertain to the xanadAssistant installation only.  Workspace
    content, project names, absolute paths, and secrets are excluded.
    """
    context = collect_context(workspace, package_root)
    check_result = build_check_result(workspace, package_root, context=context)
    source_summary = build_source_summary(package_root)

    install_meta = _extract_install_metadata(context["lockfileState"], context["installState"])
    check_data = _extract_check_data(check_result)

    pkg_version = (
        install_meta.get("version")
        or (context.get("manifest") or {}).get("packageVersion")
        or "unknown"
    )

    report: dict = {
        "healthCheckSchemaVersion": HEALTH_CHECK_SCHEMA_VERSION,
        "generatedAt": (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        ),
        "label": label,
        "package": {
            "name": "xanadAssistant",
            "version": pkg_version,
            "source": _sanitize_source(source_summary),
        },
        "install": install_meta,
        "check": check_data,
        "system": {
            "platform": platform.system().lower(),
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
    }
    status = check_data.get("status") or "unknown"
    report["issueTitle"] = f"[Health Check] xanadAssistant {pkg_version} — {status}"
    report["issueBody"] = _format_issue_body(report)
    report["issueLabels"] = ["health-check-report"]
    return report


def build_health_check_result(workspace: Path, package_root: Path, label: str | None = None) -> dict:
    """Return a lifecycle-standard command payload for the health-report command."""
    report = build_health_check_report(workspace, package_root, label=label)
    return {
        "command": "health-report",
        "workspace": _REDACTED_WORKSPACE,
        "source": _sanitize_source_summary(build_source_summary(package_root)),
        "status": "ok",
        "warnings": [],
        "errors": [],
        "result": report,
    }
