from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from scripts.lifecycle._xanad._errors import DEFAULT_CACHE_ROOT, LifecycleCommandError, _State
from scripts.lifecycle._xanad._source_remote import resolve_github_release, resolve_github_ref  # noqa: F401 – re-exported


def resolve_workspace(path_value: str, *, create: bool = False) -> Path:
    workspace = Path(path_value).resolve()
    if create:
        workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def resolve_package_root(path_value: str) -> Path:
    package_root = Path(path_value).resolve()
    if not package_root.exists():
        raise LifecycleCommandError(
            "source_resolution_failure",
            f"Package root does not exist: {package_root}",
            3,
            {"path": str(package_root)},
        )
    return package_root


def get_cache_root() -> Path:
    """Return the package cache root, honouring the XANAD_PKG_CACHE env override."""
    env_cache = os.environ.get("XANAD_PKG_CACHE")
    if env_cache:
        return Path(env_cache).resolve()
    return DEFAULT_CACHE_ROOT


def parse_github_source(source: str) -> tuple[str, str]:
    """Parse 'github:owner/repo' into (owner, repo), raising on malformed input."""
    if not source.startswith("github:"):
        raise LifecycleCommandError(
            "source_resolution_failure",
            f"Unsupported source scheme: {source!r}. Expected format: 'github:owner/repo'.",
            3,
        )
    repo_part = source[len("github:"):]
    owner, sep, repo = repo_part.partition("/")
    if not sep or not owner or not repo or "/" in repo:
        raise LifecycleCommandError(
            "source_resolution_failure",
            f"Invalid GitHub source: {source!r}. Expected exactly 'github:owner/repo'.",
            3,
        )
    safe_pattern = re.compile(r"^[A-Za-z0-9._-]+$")
    if not safe_pattern.match(owner) or not safe_pattern.match(repo):
        raise LifecycleCommandError(
            "source_resolution_failure",
            f"GitHub owner or repo contains invalid characters in: {source!r}.",
            3,
        )
    return owner, repo


def _parse_github_remote_url(remote_url: str) -> str | None:
    remote_url = remote_url.strip()
    patterns = (
        r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
        r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, remote_url)
        if match is None:
            continue
        owner = match.group("owner")
        repo = match.group("repo")
        return f"github:{owner}/{repo}"
    return None


def _detect_git_source_info(package_root: Path) -> dict[str, str]:
    info: dict[str, str] = {}
    try:
        remote_result = subprocess.run(
            ["git", "-C", str(package_root), "remote", "get-url", "origin"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return info

    if remote_result.returncode != 0:
        return info

    source = _parse_github_remote_url(remote_result.stdout)
    if source is None:
        return info
    info["source"] = source

    try:
        branch_result = subprocess.run(
            ["git", "-C", str(package_root), "symbolic-ref", "--quiet", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return info

    if branch_result.returncode == 0 and branch_result.stdout.strip():
        info["ref"] = branch_result.stdout.strip()
    return info


def resolve_effective_package_root(
    package_root_arg: str | None,
    source_arg: str | None,
    version_arg: str | None,
    ref_arg: str | None,
) -> tuple[Path, dict]:
    """Resolve the effective package root from CLI args, returning (path, source_info)."""
    if package_root_arg is not None:
        pkg_root = resolve_package_root(package_root_arg)
        source_info = {"kind": "package-root", "packageRoot": str(pkg_root)}
        inferred_source_info = _detect_git_source_info(pkg_root)
        effective_source = source_arg or inferred_source_info.get("source")
        if effective_source is not None:
            parse_github_source(effective_source)
            source_info["source"] = effective_source
        if version_arg is not None:
            source_info["version"] = version_arg
        effective_ref = ref_arg
        if effective_ref is None and version_arg is None:
            effective_ref = inferred_source_info.get("ref")
        if effective_ref is not None and "source" in source_info:
            source_info["ref"] = effective_ref
        return pkg_root, source_info

    if source_arg is None:
        raise LifecycleCommandError(
            "source_resolution_failure",
            "Either --package-root or --source must be provided.",
            2,
        )

    owner, repo = parse_github_source(source_arg)
    cache_root = get_cache_root()

    if version_arg is not None:  # pragma: no cover
        pkg_root = resolve_github_release(owner, repo, version_arg, cache_root)
        return pkg_root, {
            "kind": "github-release",
            "source": source_arg,
            "version": version_arg,
            "packageRoot": str(pkg_root),
        }

    resolved_ref = ref_arg if ref_arg is not None else "main"  # pragma: no cover
    pkg_root = resolve_github_ref(owner, repo, resolved_ref, cache_root)  # pragma: no cover
    return pkg_root, {  # pragma: no cover
        "kind": "github-ref",
        "source": source_arg,
        "ref": resolved_ref,
        "packageRoot": str(pkg_root),
    }


def build_source_summary(package_root: Path) -> dict:
    if _State.session_source_info is not None:
        return dict(_State.session_source_info)
    return {
        "kind": "package-root",
        "packageRoot": str(package_root),
    }
