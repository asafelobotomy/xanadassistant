#!/usr/bin/env python3
"""DevOps environment-check MCP server — scan for secret exposure and config hygiene.

Tools
-----
scan_for_secrets   : Detect probable secrets in a file or directory tree.
check_gitignore    : Report sensitive file patterns missing from .gitignore.
list_env_vars      : List environment variable names (not values) set in a process env file.

Transport: stdio  |  Run: uvx --from "mcp[cli]" mcp run <this-file>
"""
from __future__ import annotations

import re
import sys
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

mcp = FastMCP("devopsEnvCheck")

# Patterns that suggest a secret is hardcoded — match the value, not the key
_SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"AKIA[0-9A-Z]{16}", "AWS access key ID"),
    (r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{6,}['\"]", "Hardcoded password"),
    (r"(?i)(secret|token|api_?key)\s*=\s*['\"][^'\"]{8,}['\"]", "Hardcoded secret/token"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "Private key material"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub personal access token"),
    (r"sk-[A-Za-z0-9]{32,}", "OpenAI-style API key"),
]

_COMPILED = [(re.compile(p), label) for p, label in _SECRET_PATTERNS]

# Sensitive file patterns that should appear in .gitignore
_SENSITIVE_PATTERNS = [
    "*.env",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "terraform.tfstate",
    "terraform.tfstate.backup",
    "*.tfvars",
    ".terraform/",
]

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".whl", ".pyc",
    ".exe", ".dll", ".so", ".dylib",
}


def _is_binary(path: Path) -> bool:
    return path.suffix.lower() in _BINARY_EXTENSIONS


@mcp.tool()
def scan_for_secrets(path: str, max_findings: int = 50) -> dict:
    """Scan a file or directory tree for probable hardcoded secrets.

    Args:
        path: File or directory to scan.
        max_findings: Stop after this many findings. Defaults to 50.

    Returns:
        {"path": str, "findings": [{"file": str, "line": int, "pattern": str, "label": str}],
         "truncated": bool}
    """
    root = Path(path)
    if not root.exists():
        return {"path": str(root), "error": f"Not found: {path}", "findings": [], "truncated": False}

    targets = [root] if root.is_file() else sorted(root.rglob("*"))
    findings: list[dict] = []
    truncated = False

    for target in targets:
        if not target.is_file() or _is_binary(target):
            continue
        # Skip common non-secret dirs
        parts = target.parts
        if any(p in parts for p in (".git", "node_modules", "__pycache__", ".venv")):
            continue
        try:
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for pattern, label in _COMPILED:
                if pattern.search(line):
                    findings.append({
                        "file": str(target),
                        "line": lineno,
                        "pattern": pattern.pattern,
                        "label": label,
                    })
                    if len(findings) >= max_findings:
                        truncated = True
                        break
            if truncated:
                break
        if truncated:
            break

    return {"path": str(root), "findings": findings, "truncated": truncated}


@mcp.tool()
def check_gitignore(repo_path: str = ".") -> dict:
    """Report sensitive file patterns missing from .gitignore.

    Args:
        repo_path: Path to the repository root. Defaults to current directory.

    Returns:
        {"repo_path": str, "missing_patterns": [str], "present_patterns": [str]}
    """
    gitignore = Path(repo_path) / ".gitignore"
    if not gitignore.exists():
        return {
            "repo_path": str(repo_path),
            "error": ".gitignore not found",
            "missing_patterns": _SENSITIVE_PATTERNS,
            "present_patterns": [],
        }

    content = gitignore.read_text(encoding="utf-8", errors="replace")
    lines = {line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")}

    missing = [p for p in _SENSITIVE_PATTERNS if p not in lines]
    present = [p for p in _SENSITIVE_PATTERNS if p in lines]

    return {"repo_path": str(repo_path), "missing_patterns": missing, "present_patterns": present}


@mcp.tool()
def list_env_vars(env_file: str) -> dict:
    """List variable names (not values) defined in a .env file.

    Args:
        env_file: Path to the .env file.

    Returns:
        {"file": str, "variable_names": [str], "line_count": int}
    """
    path = Path(env_file)
    if not path.exists():
        return {"file": str(path), "error": f"File not found: {env_file}", "variable_names": []}

    names: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            name = stripped.split("=", 1)[0].strip()
            if name:
                names.append(name)

    return {"file": str(path), "variable_names": names, "line_count": len(lines)}


if __name__ == "__main__":
    mcp.run()
