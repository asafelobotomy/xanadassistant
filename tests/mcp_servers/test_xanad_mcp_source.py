from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_source_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load _xanad_mcp_source.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SOURCE_MODULE = load_source_module("mcp/scripts/_xanad_mcp_source.py", "test_xanad_mcp_source_source")
MANAGED_MODULE = load_source_module(".github/mcp/scripts/_xanad_mcp_source.py", "test_xanad_mcp_source_managed")


class XanadMcpSourceTests(unittest.TestCase):
    def test_parse_github_source_rejects_invalid_source(self) -> None:
        for module in (SOURCE_MODULE, MANAGED_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "Unsupported source scheme"):
                    module.parse_github_source("gitlab:owner/repo")
                with self.assertRaisesRegex(ValueError, "Invalid GitHub source"):
                    module.parse_github_source("github:owner/repo/extra")
                with self.assertRaisesRegex(ValueError, "invalid characters"):
                    module.parse_github_source("github:bad owner/repo")

    def test_resolve_github_ref_rejects_invalid_ref_before_git(self) -> None:
        for module in (SOURCE_MODULE, MANAGED_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    with self.assertRaisesRegex(ValueError, "invalid characters"):
                        module.resolve_github_ref("owner", "repo", "bad ref^", Path(tmpdir))

    def test_parse_github_source_accepts_valid_input(self) -> None:
        for module in (SOURCE_MODULE, MANAGED_MODULE):
            with self.subTest(module=module.__name__):
                self.assertEqual(module.parse_github_source("github:owner/repo"), ("owner", "repo"))

    def test_resolve_github_release_returns_cached_directory_when_complete(self) -> None:
        for module in (SOURCE_MODULE, MANAGED_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    cache_root = Path(tmpdir)
                    cache_dir = cache_root / "github" / "owner-repo" / "release-v1.0.0"
                    cache_dir.mkdir(parents=True)
                    (cache_dir / ".complete").write_text("ok\n", encoding="utf-8")

                    result = module.resolve_github_release("owner", "repo", "v1.0.0", cache_root)

                self.assertEqual(result, cache_dir)

    def test_resolve_github_ref_covers_cached_fetch_and_clone_paths(self) -> None:
        for module in (SOURCE_MODULE, MANAGED_MODULE):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    cache_root = Path(tmpdir)
                    cache_dir = cache_root / "github" / "owner-repo" / "ref-main"
                    (cache_dir / ".git").mkdir(parents=True)

                    with mock.patch.object(module.subprocess, "run") as run_mock:
                        result = module.resolve_github_ref("owner", "repo", "main", cache_root)

                    self.assertEqual(result, cache_dir)
                    self.assertEqual(
                        [call.args[0] for call in run_mock.call_args_list],
                        [
                            ["git", "-C", str(cache_dir), "fetch", "--depth", "1", "origin", "main"],
                            ["git", "-C", str(cache_dir), "checkout", "FETCH_HEAD"],
                        ],
                    )

                with tempfile.TemporaryDirectory() as tmpdir:
                    cache_root = Path(tmpdir)
                    cache_dir = cache_root / "github" / "owner-repo" / "ref-feature-test"
                    with mock.patch.object(module.subprocess, "run") as run_mock:
                        result = module.resolve_github_ref("owner", "repo", "feature/test", cache_root)

                    self.assertEqual(result, cache_dir)
                    self.assertEqual(
                        run_mock.call_args.args[0],
                        ["git", "clone", "--depth", "1", "--branch", "feature/test", "https://github.com/owner/repo.git", str(cache_dir)],
                    )


if __name__ == "__main__":
    unittest.main()