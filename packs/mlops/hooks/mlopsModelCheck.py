#!/usr/bin/env python3
"""MLOps model-check MCP server — surface large model artefacts, data leakage patterns, and hardcoded paths.

Tools
-----
check_model_files        : Find large model artefact files that should not be committed to git.
scan_for_leakage_patterns: Detect common data leakage code patterns in Python files.
find_hardcoded_paths     : Report hardcoded absolute paths in source files and notebooks.
diff_requirements        : Compare two requirements files and report package drift.

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

mcp = FastMCP("mlopsModelCheck")

# File extensions that indicate model artefacts or large data files
_MODEL_EXTENSIONS = {
    ".pkl", ".pickle", ".pt", ".pth", ".h5", ".hdf5",
    ".onnx", ".pb", ".tflite", ".joblib", ".safetensors",
}

_DATA_EXTENSIONS = {".csv", ".parquet", ".feather", ".arrow", ".jsonl", ".npy", ".npz"}

# Size threshold in bytes above which a file is flagged (1 MB default)
_DEFAULT_SIZE_THRESHOLD = 1_048_576

# Patterns that suggest train/test leakage in Python source
_LEAKAGE_PATTERNS: list[tuple[str, str]] = [
    (
        r"\.fit\s*\(\s*(?:X|data|df|features)[^)]*\)\s*\n[^\n]*train_test_split",
        "Transformer fitted before train_test_split (possible leakage)",
    ),
    (
        r"train_test_split[^)]*\)\s*\n[^\n]*\.fit\s*\(\s*(?:X|data|df|features)\s*\)",
        "Transformer fitted on full dataset after split variable assigned",
    ),
    (
        r"fillna\s*\([^)]*\.mean\s*\(\s*\)[^)]*\)(?![^#\n]*#[^\n]*ok)",
        "fillna with global mean before split (may leak test statistics)",
    ),
    (
        r"\.fit_transform\s*\(\s*(?:X|data|df|X_test|test)[^)]*\)",
        "fit_transform called — ensure this is on training data only",
    ),
]

_COMPILED_LEAKAGE = [(re.compile(p, re.MULTILINE), label) for p, label in _LEAKAGE_PATTERNS]

# Patterns for hardcoded absolute paths
_PATH_PATTERNS: list[tuple[str, str]] = [
    (r"/home/[A-Za-z0-9_.-]+/", "Unix home path (/home/user/...)"),
    (r"/Users/[A-Za-z0-9_.-]+/", "macOS home path (/Users/user/...)"),
    (r"[A-Z]:\\\\[A-Za-z0-9_. -]+\\\\", "Windows absolute path (C:\\...)"),
    (r"/root/", "Root user path"),
]

_COMPILED_PATHS = [(re.compile(p), label) for p, label in _PATH_PATTERNS]

_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll", ".so", ".dylib",
}


def _is_binary(path: Path) -> bool:
    return path.suffix.lower() in _BINARY_EXTENSIONS


@mcp.tool()
def check_model_files(directory: str, size_threshold_mb: float = 1.0) -> dict:
    """Find model artefact and large data files that should not be committed to git.

    Args:
        directory: Directory to scan.
        size_threshold_mb: Report files larger than this many MB. Defaults to 1.0.

    Returns:
        {"directory": str, "files": [{"path": str, "extension": str, "size_mb": float}],
         "count": int}
    """
    root = Path(directory)
    if not root.exists():
        return {"directory": str(root), "error": f"Not found: {directory}", "files": [], "count": 0}

    threshold = int(size_threshold_mb * _DEFAULT_SIZE_THRESHOLD)
    found: list[dict] = []

    for target in sorted(root.rglob("*")):
        if not target.is_file():
            continue
        parts = target.parts
        if any(p in parts for p in (".git", "node_modules", "__pycache__", ".venv")):
            continue
        ext = target.suffix.lower()
        if ext in _MODEL_EXTENSIONS or ext in _DATA_EXTENSIONS:
            try:
                size = target.stat().st_size
            except OSError:
                continue
            if size >= threshold:
                found.append({
                    "path": str(target),
                    "extension": ext,
                    "size_mb": round(size / _DEFAULT_SIZE_THRESHOLD, 2),
                })

    return {"directory": str(root), "files": found, "count": len(found)}


@mcp.tool()
def scan_for_leakage_patterns(directory: str) -> dict:
    """Detect common data leakage code patterns in Python source files and notebooks.

    Args:
        directory: Directory to scan (searches *.py and *.ipynb files).

    Returns:
        {"directory": str, "findings": [{"file": str, "line": int, "label": str}], "count": int}
    """
    root = Path(directory)
    if not root.exists():
        return {"directory": str(root), "error": f"Not found: {directory}", "findings": [], "count": 0}

    findings: list[dict] = []

    for target in sorted(root.rglob("*")):
        if not target.is_file():
            continue
        if target.suffix.lower() not in {".py", ".ipynb"}:
            continue
        parts = target.parts
        if any(p in parts for p in (".git", "__pycache__", ".venv")):
            continue
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = content.splitlines()
        for pattern, label in _COMPILED_LEAKAGE:
            for match in pattern.finditer(content):
                lineno = content[: match.start()].count("\n") + 1
                findings.append({"file": str(target), "line": lineno, "label": label})

    return {"directory": str(root), "findings": findings, "count": len(findings)}


@mcp.tool()
def find_hardcoded_paths(directory: str) -> dict:
    """Report hardcoded absolute paths in Python source files and notebooks.

    Args:
        directory: Directory to scan.

    Returns:
        {"directory": str, "findings": [{"file": str, "line": int, "match": str, "label": str}],
         "count": int}
    """
    root = Path(directory)
    if not root.exists():
        return {"directory": str(root), "error": f"Not found: {directory}", "findings": [], "count": 0}

    findings: list[dict] = []

    for target in sorted(root.rglob("*")):
        if not target.is_file() or _is_binary(target):
            continue
        parts = target.parts
        if any(p in parts for p in (".git", "__pycache__", ".venv", "node_modules")):
            continue
        try:
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            for pattern, label in _COMPILED_PATHS:
                m = pattern.search(line)
                if m:
                    findings.append({
                        "file": str(target),
                        "line": lineno,
                        "match": m.group(0),
                        "label": label,
                    })
                    break  # one finding per line

    return {"directory": str(root), "findings": findings, "count": len(findings)}


_VER_SPLIT = re.compile(r"([A-Za-z0-9_.\-]+)\s*([>=<!~^].+)?")


@mcp.tool()
def diff_requirements(path_a: str, path_b: str) -> dict:
    """Compare two requirements files and report added, removed, and version-changed packages.

    Supports requirements.txt and similar formats. Blank lines and comments are ignored.

    Args:
        path_a: Baseline requirements file (e.g., training environment).
        path_b: Comparison requirements file (e.g., serving environment).

    Returns:
        {"added": list[str], "removed": list[str],
         "changed": list[{"name": str, "from": str, "to": str}]}
    """
    def _parse(fpath: str) -> dict[str, str]:
        result: dict[str, str] = {}
        try:
            for raw in Path(fpath).read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw.strip().split("#")[0].strip()
                if not line or line.startswith("-"):
                    continue
                m = _VER_SPLIT.match(line)
                if m:
                    result[m.group(1).lower().replace("-", "_")] = (m.group(2) or "").strip()
        except OSError:
            pass
        return result

    a, b = _parse(path_a), _parse(path_b)
    added = sorted(k for k in b if k not in a)
    removed = sorted(k for k in a if k not in b)
    changed = sorted(
        [{"name": k, "from": a[k], "to": b[k]} for k in a if k in b and a[k] != b[k]],
        key=lambda x: x["name"],
    )
    return {
        "added": [f"{k}{b[k]}" if b[k] else k for k in added],
        "removed": [f"{k}{a[k]}" if a[k] else k for k in removed],
        "changed": changed,
    }


if __name__ == "__main__":  # pragma: no cover
    mcp.run(transport="stdio")
