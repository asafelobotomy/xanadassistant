from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.mcp_servers._xanad_workspace_mcp_support import (
    MANAGED_MCP_MODULE,
    SOURCE_MCP_MODULE,
    XanadWorkspaceMcpTestCaseMixin,
)


class XanadWorkspaceMcpDiscoveryTests(XanadWorkspaceMcpTestCaseMixin, unittest.TestCase):

    def test_source_and_managed_modules_resolve_repo_workspace_root(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]

        self.assertEqual(SOURCE_MCP_MODULE.WORKSPACE_ROOT, repo_root)
        self.assertEqual(MANAGED_MCP_MODULE.WORKSPACE_ROOT, repo_root)

    def test_workspace_root_discovery_and_lockfile_reader_fallbacks(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    workspace = Path(tmpdir)
                    nested = workspace / "hooks" / "scripts" / "xanadWorkspaceMcp.py"
                    nested.parent.mkdir(parents=True)
                    (workspace / ".github").mkdir()
                    nested.write_text("# stub\n", encoding="utf-8")
                    self.assertEqual(module.discover_workspace_root(nested), workspace)

                fake_script = Path("/tmp/a/b/c/xanadWorkspaceMcp.py").resolve()
                expected = fake_script.parents[min(3, len(fake_script.parents) - 1)]
                self.assertEqual(module.discover_workspace_root(fake_script), expected)

                with tempfile.TemporaryDirectory() as tmpdir:
                    lockfile = Path(tmpdir) / "lock.json"
                    lockfile.write_text("{bad", encoding="utf-8")
                    with mock.patch.object(module, "WORKSPACE_LOCKFILE_PATH", lockfile):
                        self.assertIsNone(module.read_lockfile())

    def test_resolve_lifecycle_package_root_validates_strings_and_lockfile_package_root(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                package_root, reason = module.resolve_lifecycle_package_root(123)
                self.assertIsNone(package_root)
                self.assertIn("packageRoot must be a non-empty string", reason)

                with tempfile.TemporaryDirectory() as tmpdir:
                    pkg = Path(tmpdir) / "pkg"
                    pkg.mkdir()
                    with mock.patch.object(module, "read_lockfile", return_value={"package": {"packageRoot": str(pkg)}}):
                        package_root, reason = module.resolve_lifecycle_package_root(None)
                    self.assertEqual(package_root, pkg.resolve())
                    self.assertIsNone(reason)

                with mock.patch.object(module, "read_lockfile", return_value={"package": {"source": "github:owner/repo"}}):
                    package_root, reason = module.resolve_lifecycle_package_root(None, source_arg="github:owner/repo", version_arg="", ref_arg=None)
                self.assertIsNone(package_root)
                self.assertIn("version must be a non-empty string", reason)

    def test_remote_resolution_and_cli_lookup_failure_paths(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir, mock.patch.object(
                    module,
                    "read_lockfile",
                    return_value={"package": {}},
                ), mock.patch.object(
                    module,
                    "parse_github_source",
                    return_value=("owner", "repo"),
                ), mock.patch.object(
                    module,
                    "resolve_github_ref",
                    side_effect=OSError("cache failed"),
                ):
                    package_root, reason = module.resolve_lifecycle_package_root(None, source_arg="github:owner/repo")
                self.assertIsNone(package_root)
                self.assertIn("Failed to resolve remote lifecycle source", reason)

                with tempfile.TemporaryDirectory() as tmpdir:
                    package_root = Path(tmpdir)
                    cli, reason = module.resolve_lifecycle_cli(package_root)
                self.assertIsNone(cli)
                self.assertIn("No xanadAssistant CLI entrypoint", reason)

    def test_explicit_invalid_package_root_does_not_fall_back(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        missing_root = str(repo_root / "missing-package-root-do-not-create")

        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with mock.patch.object(
                    module,
                    "read_lockfile",
                    return_value={"package": {"source": "github:owner/repo", "ref": "main"}},
                ), mock.patch.object(
                    module,
                    "parse_github_source",
                    side_effect=AssertionError("should not resolve a fallback source"),
                ):
                    package_root, reason = module.resolve_lifecycle_package_root(missing_root)

                self.assertIsNone(package_root)
                self.assertIn("does not exist", reason)


if __name__ == "__main__":
    unittest.main()