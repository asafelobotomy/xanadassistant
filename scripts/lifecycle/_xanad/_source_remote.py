from __future__ import annotations

"""Remote GitHub source resolution (network-accessing, pragma: no cover).

Factored out of _source.py to keep that module under the 250-line warning threshold.
All functions here require network access and are excluded from coverage.
"""

import re
import subprocess
from pathlib import Path

from scripts.lifecycle._xanad._errors import LifecycleCommandError


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
        req = _urllib_request.Request(url, headers={"User-Agent": "xanadAssistant/0.1"})
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
