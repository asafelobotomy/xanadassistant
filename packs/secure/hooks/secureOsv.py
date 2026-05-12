#!/usr/bin/env python3
"""Secure OSV MCP server — dependency vulnerability lookups via OSV.dev.

Tools
-----
query_package_vulnerabilities : Query OSV.dev for a single package version.
batch_query_lockfile          : Parse a lockfile and bulk-query all dependencies.

Uses the public OSV.dev API (https://api.osv.dev/v1/query) — no auth required.

Transport: stdio  |  Run: uvx --from "mcp[cli]" mcp run <this-file>
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as _exc:  # pragma: no cover
    sys.stderr.write(
        "ERROR: the 'mcp' package is required but not installed.\n"
        "Install it with: pip install 'mcp[cli]'\n"
        f"Details: {_exc}\n"
    )
    sys.exit(1)

mcp = FastMCP("secureOsv")

_OSV_API = "https://api.osv.dev/v1/query"
_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _osv_query(ecosystem: str, name: str, version: str) -> list[dict]:
    """Call OSV.dev for one package version; return list of vulnerability summaries."""
    payload = json.dumps({
        "version": version,
        "package": {"name": name, "ecosystem": ecosystem},
    }).encode()
    req = urllib.request.Request(
        _OSV_API,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        return [{"error": f"Network error: {exc}"}]
    except json.JSONDecodeError as exc:
        return [{"error": f"Malformed OSV response: {exc}"}]

    vulns = []
    for vuln in data.get("vulns", []):
        sev = vuln.get("database_specific", {}).get("severity") or ""
        cvss = ""
        for s in vuln.get("severity", []):
            if s.get("type") == "CVSS_V3":
                cvss = s.get("score", "")
                break
        fixed_in = []
        for affected in vuln.get("affected", []):
            for rng in affected.get("ranges", []):
                for ev in rng.get("events", []):
                    if "fixed" in ev:
                        fixed_in.append(ev["fixed"])
        vulns.append({
            "id": vuln.get("id", ""),
            "summary": vuln.get("summary", ""),
            "severity": sev,
            "cvss_v3": cvss,
            "fixed_in": sorted(set(fixed_in)),
        })
    return vulns


def _parse_requirements_txt(path: Path) -> list[tuple[str, str]]:
    """Parse pinned deps from requirements.txt; returns [(name, version), ...]."""
    deps = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        m = re.match(r"^([A-Za-z0-9_\-\.]+)==([^\s;]+)", line)
        if m:
            deps.append((m.group(1), m.group(2)))
    return deps


def _parse_package_json(path: Path) -> list[tuple[str, str]]:
    """Parse pinned deps from package.json; returns [(name, version), ...]."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    deps = []
    for section in ("dependencies", "devDependencies"):
        for name, ver in data.get(section, {}).items():
            clean = ver.lstrip("^~>=<")
            if re.match(r"^\d+\.\d+", clean):
                deps.append((name, clean))
    return deps


def _parse_cargo_toml(path: Path) -> list[tuple[str, str]]:
    """Parse pinned deps from Cargo.toml; returns [(name, version), ...]."""
    deps = []
    in_dep_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if re.match(r"^\[.*dependencies.*\]", stripped):
            in_dep_section = True
            continue
        if stripped.startswith("[") and in_dep_section:
            in_dep_section = False
        if in_dep_section:
            m = re.match(r'^([A-Za-z0-9_\-]+)\s*=\s*["\']([^"\']+)["\']', stripped)
            if m:
                ver = m.group(2).lstrip("^~>=< ")
                if re.match(r"^\d+\.\d+", ver):
                    deps.append((m.group(1), ver))
    return deps


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def query_package_vulnerabilities(ecosystem: str, name: str, version: str) -> dict:
    """Query OSV.dev for known vulnerabilities for a single package version.

    Returns a dict with:
      - package:         {ecosystem, name, version}
      - vulnerability_count: number of known CVEs
      - vulnerabilities: list of {id, summary, severity, cvss_v3, fixed_in}
      - note:            data sourced from OSV.dev; results are point-in-time

    Args:
        ecosystem: Package ecosystem — PyPI, npm, crates.io, Go, Maven, etc.
        name:      Exact package name as it appears in the lockfile.
        version:   Exact installed version string.
    """
    vulns = _osv_query(ecosystem, name, version)
    return {
        "package": {"ecosystem": ecosystem, "name": name, "version": version},
        "vulnerability_count": len([v for v in vulns if "error" not in v]),
        "vulnerabilities": vulns,
        "note": "Results sourced from OSV.dev. Query is point-in-time.",
    }


@mcp.tool()
def batch_query_lockfile(lockfile_path: str) -> dict:
    """Parse a lockfile and query OSV.dev for all pinned dependencies.

    Supports: requirements.txt, package.json, Cargo.toml.

    Returns a dict with:
      - lockfile:        path that was parsed
      - format:          detected format
      - packages_checked: count of packages queried
      - vulnerable:      list of packages with at least one known CVE
      - clean:           list of package names with no known CVEs
      - errors:          any parse or network errors

    Args:
        lockfile_path: Absolute or relative path to the lockfile to scan.
    """
    path = Path(lockfile_path).resolve()
    if not path.exists():
        return {"error": f"File not found: {lockfile_path}"}

    name = path.name.lower()
    if name == "requirements.txt":
        fmt = "requirements.txt"
        ecosystem = "PyPI"
        deps = _parse_requirements_txt(path)
    elif name == "package.json":
        fmt = "package.json"
        ecosystem = "npm"
        deps = _parse_package_json(path)
    elif name == "cargo.toml":
        fmt = "Cargo.toml"
        ecosystem = "crates.io"
        deps = _parse_cargo_toml(path)
    else:
        return {"error": f"Unsupported lockfile format: {path.name}. Supported: requirements.txt, package.json, Cargo.toml"}

    vulnerable = []
    clean = []
    errors = []
    for pkg_name, version in deps:
        vulns = _osv_query(ecosystem, pkg_name, version)
        net_errors = [v for v in vulns if "error" in v]
        real_vulns = [v for v in vulns if "error" not in v]
        if net_errors:
            errors.append({"package": pkg_name, "error": net_errors[0]["error"]})
        if real_vulns:
            vulnerable.append({
                "name": pkg_name,
                "version": version,
                "vulnerability_count": len(real_vulns),
                "vulnerabilities": real_vulns,
            })
        elif not net_errors:
            clean.append(f"{pkg_name}=={version}")

    return {
        "lockfile": str(path),
        "format": fmt,
        "packages_checked": len(deps),
        "vulnerable": vulnerable,
        "clean": clean,
        "errors": errors,
        "note": "Results sourced from OSV.dev. Query is point-in-time.",
    }


@mcp.tool()
def list_supported_ecosystems() -> dict:
    """Return the package ecosystems supported by OSV.dev and this hook.

    Returns:
        {"osv_supported": list[str], "batch_query_supported": list[str]}
    """
    return {
        "osv_supported": [
            "Go", "npm", "OSS-Fuzz", "PyPI", "RubyGems", "crates.io",
            "Packagist", "Maven", "NuGet", "Linux", "Debian", "Alpine",
            "Hex", "Android", "GitHub Actions", "Pub",
        ],
        "batch_query_supported": ["requirements.txt", "package.json", "Cargo.toml"],
        "note": "batch_query_lockfile currently supports requirements.txt, package.json, and Cargo.toml.",
    }


if __name__ == "__main__":
    mcp.run()
