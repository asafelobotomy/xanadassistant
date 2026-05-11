from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from scripts.lifecycle._xanad._errors import DEFAULT_CACHE_ROOT, LifecycleCommandError, _State


def resolve_workspace(path_value: str, *, create: bool = False) -> Path:
    workspace = Path(path_value).resolve()
    if create:
        workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def resolve_package_root(path_value: str) -> Path:
    package_root = Path(path_value).resolve()
    if not package_root.exists():
        raise FileNotFoundError(f"Package root does not exist: {package_root}")
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
            5,
        )
    repo_part = source[len("github:"):]
    owner, sep, repo = repo_part.partition("/")
    if not sep or not owner or not repo or "/" in repo:
        raise LifecycleCommandError(
            "source_resolution_failure",
            f"Invalid GitHub source: {source!r}. Expected exactly 'github:owner/repo'.",
            5,
        )
    safe_pattern = re.compile(r"^[A-Za-z0-9._-]+$")
    if not safe_pattern.match(owner) or not safe_pattern.match(repo):
        raise LifecycleCommandError(
            "source_resolution_failure",
            f"GitHub owner or repo contains invalid characters in: {source!r}.",
            5,
        )
    return owner, repo


def resolve_github_release(owner: str, repo: str, version: str, cache_root: Path) -> Path:  # pragma: no cover
    """Download a GitHub release tarball to the cache and return the extracted path."""
    import tarfile as _tarfile
    import tempfile as _tempfile
    import urllib.request as _urllib_request

    safe_version = re.sub(r"[^A-Za-z0-9._-]", "-", version)
    cache_dir = cache_root / "github" / f"{owner}-{repo}" / f"release-{safe_version}"
    sentinel = cache_dir / ".complete"
    if sentinel.exists():
        return cache_dir

    url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{version}.tar.gz"
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with _tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        req = _urllib_request.Request(url, headers={"User-Agent": "xanad-assistant/0.1"})
        with _urllib_request.urlopen(req, timeout=60) as response:
            tmp_path.write_bytes(response.read())
        with _tarfile.open(tmp_path, "r:gz") as tar:
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
    except LifecycleCommandError:
        raise
    except Exception as exc:
        raise LifecycleCommandError(
            "source_resolution_failure",
            f"Failed to download GitHub release {owner}/{repo}@{version}: {exc}",
            5,
            {"url": url, "version": version, "error": str(exc)},
        ) from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return cache_dir


def resolve_github_ref(owner: str, repo: str, ref: str, cache_root: Path) -> Path:  # pragma: no cover
    """Clone or update a GitHub repo at a specific ref to the cache and return the path."""
    safe_ref = re.sub(r"[^A-Za-z0-9._-]", "-", ref)
    cache_dir = cache_root / "github" / f"{owner}-{repo}" / f"ref-{safe_ref}"
    clone_url = f"https://github.com/{owner}/{repo}.git"
    try:
        if (cache_dir / ".git").exists():
            subprocess.run(
                ["git", "-C", str(cache_dir), "fetch", "--depth", "1", "origin", ref],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(cache_dir), "checkout", "FETCH_HEAD"],
                check=True,
                capture_output=True,
            )
        else:
            cache_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", ref, clone_url, str(cache_dir)],
                check=True,
                capture_output=True,
            )
    except subprocess.CalledProcessError as exc:
        stderr_text = exc.stderr.decode(errors="replace").strip() if exc.stderr else ""
        raise LifecycleCommandError(
            "source_resolution_failure",
            f"Failed to resolve GitHub ref {owner}/{repo}@{ref}: {stderr_text}",
            5,
            {"url": clone_url, "ref": ref},
        ) from exc
    return cache_dir


def resolve_effective_package_root(
    package_root_arg: str | None,
    source_arg: str | None,
    version_arg: str | None,
    ref_arg: str | None,
) -> tuple[Path, dict]:
    """Resolve the effective package root from CLI args, returning (path, source_info)."""
    if package_root_arg is not None:
        pkg_root = resolve_package_root(package_root_arg)
        return pkg_root, {"kind": "package-root", "packageRoot": str(pkg_root)}

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
