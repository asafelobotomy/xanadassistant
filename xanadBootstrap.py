#!/usr/bin/env python3
"""xanadBootstrap.py — cold-start installer for xanadAssistant.

Download this single file and run it to install xanadAssistant into a workspace
without needing a local checkout. Requires Python 3.10+ and stdlib only.

Usage:
    python3 xanadBootstrap.py inspect  --workspace <path> [options]
    python3 xanadBootstrap.py interview --workspace <path> [--mode setup] [options]
    python3 xanadBootstrap.py plan setup --workspace <path> [--answers <file>] --plan-out <file> [options]
    python3 xanadBootstrap.py apply     --workspace <path> --plan <file> [options]

Source options:
    --package-root <path>       Use a local xanadAssistant checkout (dev / CI).
    --source github:owner/repo  GitHub source (default: github:asafelobotomy/xanadassistant).
    --version <tag>             Pin to a release tag (e.g. v1.0.0). Defaults to main.

All other flags are forwarded verbatim to the underlying xanadAssistant CLI.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

_DEFAULT_SOURCE = "github:asafelobotomy/xanadassistant"
_DEFAULT_CACHE_ROOT = Path.home() / ".xanadAssistant" / "pkg-cache"
_VERSION = "0.1.1"
_SUPPORTED_COMMANDS = ("inspect", "interview", "plan", "apply")


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------

def _safe_slug(value: str) -> str:
    """Sanitise a string for use in a filesystem path component."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", value)


def _validate_source(source: str) -> tuple[str, str]:
    """Parse 'github:owner/repo' → (owner, repo). Exits on malformed input."""
    if not source.startswith("github:"):
        sys.exit(
            f"[xanadBootstrap] Unsupported source scheme: {source!r}. "
            "Expected format: github:owner/repo"
        )
    repo_part = source[len("github:"):]
    owner, sep, repo = repo_part.partition("/")
    if not sep or not owner or not repo or "/" in repo:
        sys.exit(
            f"[xanadBootstrap] Invalid GitHub source: {source!r}. "
            "Expected exactly github:owner/repo"
        )
    safe = re.compile(r"^[A-Za-z0-9._-]+$")
    if not safe.match(owner) or not safe.match(repo):
        sys.exit(
            f"[xanadBootstrap] Invalid characters in GitHub source: {source!r}"
        )
    return owner, repo


# ---------------------------------------------------------------------------
# Package resolution
# ---------------------------------------------------------------------------

def _archive_url(owner: str, repo: str, ref: str) -> str:
    """Return the GitHub tarball URL for a branch or tag ref."""
    if re.match(r"^v\d", ref):
        return f"https://github.com/{owner}/{repo}/archive/refs/tags/{ref}.tar.gz"
    return f"https://github.com/{owner}/{repo}/archive/refs/heads/{ref}.tar.gz"


def _download_archive(owner: str, repo: str, ref: str, cache_root: Path) -> Path:
    """Download a GitHub archive for *ref* into the cache and return the extracted root."""
    cache_dir = cache_root / "github" / f"{owner}-{repo}" / f"ref-{_safe_slug(ref)}"
    sentinel = cache_dir / ".complete"
    if sentinel.exists():
        return cache_dir

    url = _archive_url(owner, repo, ref)
    print(f"[xanadBootstrap] Downloading {url} …", file=sys.stderr)
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".tar.gz", delete=False, dir=cache_dir
        ) as tmp:
            tmp_path = Path(tmp.name)
        req = urllib.request.Request(url, headers={"User-Agent": f"xanadBootstrap/{_VERSION}"})
        with urllib.request.urlopen(req, timeout=60) as response:
            tmp_path.write_bytes(response.read())
        with tarfile.open(tmp_path, "r:gz") as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if len(parts) < 2:
                    continue
                rel_path = Path(*parts[1:])
                # Prevent path-traversal attacks in tarballs.
                if ".." in rel_path.parts or rel_path.is_absolute():
                    continue
                dest = cache_dir / rel_path
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    file_obj = tar.extractfile(member)
                    if file_obj is not None:
                        dest.write_bytes(file_obj.read())
        sentinel.write_text("ok\n", encoding="utf-8")
    except Exception as exc:
        sys.exit(f"[xanadBootstrap] Download failed: {exc}")
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
    return cache_dir


def _resolve_package_root(
    package_root_arg: str | None,
    source: str,
    version: str | None,
    cache_root: Path,
) -> Path:
    """Return the effective package root, downloading from GitHub if necessary."""
    if package_root_arg is not None:
        pkg = Path(package_root_arg).expanduser().resolve()
        if not pkg.exists():
            sys.exit(f"[xanadBootstrap] Package root not found: {pkg}")
        return pkg
    owner, repo = _validate_source(source)
    ref = version if version else "main"
    return _download_archive(owner, repo, ref, cache_root)


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------

def _build_cli_command(
    pkg_root: Path,
    args: argparse.Namespace,
    remaining: list[str],
) -> list[str]:
    """Build the xanadAssistant CLI invocation from parsed and remaining args."""
    entry = pkg_root / "xanadAssistant.py"
    if not entry.exists():
        sys.exit(
            f"[xanadBootstrap] xanadAssistant.py not found in package root: {pkg_root}"
        )
    cmd = [sys.executable, str(entry), args.command]
    if args.command == "plan":
        if not args.mode:
            sys.exit(
                "[xanadBootstrap] 'plan' requires a sub-mode, e.g. 'plan setup'."
            )
        cmd.append(args.mode)
    cmd += [
        "--workspace", str(Path(args.workspace).resolve()),
        "--package-root", str(pkg_root),
    ]
    cmd += remaining
    return cmd


def main() -> None:
    parser = argparse.ArgumentParser(
        description="xanadBootstrap — cold-start installer for xanadAssistant.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("command", choices=_SUPPORTED_COMMANDS, help="Lifecycle command.")
    parser.add_argument(
        "mode", nargs="?", default=None,
        help="Plan sub-mode, required when command is 'plan' (e.g. setup).",
    )
    parser.add_argument("--workspace", required=True, help="Target workspace path.")
    parser.add_argument(
        "--source", default=_DEFAULT_SOURCE,
        help="GitHub source identifier (github:owner/repo).",
    )
    parser.add_argument(
        "--version", default=None,
        help="Release tag to pin (e.g. v1.0.0). Defaults to the main branch.",
    )
    parser.add_argument(
        "--package-root", default=None,
        help="Local xanadAssistant checkout (overrides --source and --version).",
    )
    parser.add_argument(
        "--cache-root", default=None,
        help="Override the default package cache directory (~/.xanadAssistant/pkg-cache).",
    )
    args, remaining = parser.parse_known_args()

    cache_root = (
        Path(args.cache_root).expanduser().resolve()
        if args.cache_root
        else _DEFAULT_CACHE_ROOT
    )
    pkg_root = _resolve_package_root(
        args.package_root, args.source, args.version, cache_root
    )
    cli_cmd = _build_cli_command(pkg_root, args, remaining)
    result = subprocess.run(cli_cmd, check=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
