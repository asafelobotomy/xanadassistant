from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class XanadEntrypointTests(unittest.TestCase):
    def test_top_level_xanad_assistant_reexports_main(self) -> None:
        module = _load_module("test_xanadAssistant_entry", REPO_ROOT / "xanadAssistant.py")

        self.assertTrue(callable(module.main))

    def test_bootstrap_helpers_build_safe_urls_and_commands(self) -> None:
        module = _load_module("test_xanadBootstrap_entry", REPO_ROOT / "xanadBootstrap.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            entry = package_root / "xanadAssistant.py"
            entry.write_text("# stub\n", encoding="utf-8")
            args = type("Args", (), {"command": "plan", "mode": "setup", "workspace": tmpdir})()
            command = module._build_cli_command(package_root, args, ["--json"])

        self.assertEqual(module._safe_slug("a/b:c"), "a-b-c")
        self.assertEqual(module._validate_source("github:owner/repo"), ("owner", "repo"))
        self.assertIn("refs/tags/v1.2.3.tar.gz", module._archive_url("owner", "repo", "v1.2.3"))
        self.assertIn("plan", command)
        self.assertIn("setup", command)
        self.assertIn("--json", command)

    def test_bootstrap_resolve_package_root_and_main_dispatch(self) -> None:
        module = _load_module("test_xanadBootstrap_main", REPO_ROOT / "xanadBootstrap.py")
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()
            self.assertEqual(
                module._resolve_package_root(str(package_root), "github:owner/repo", None, Path(tmpdir)),
                package_root.resolve(),
            )

            with self.assertRaises(SystemExit):
                module._resolve_package_root(str(package_root / "missing"), "github:owner/repo", None, Path(tmpdir))

            with mock.patch(
                "sys.argv",
                [
                    "xanadBootstrap.py",
                    "inspect",
                    "--workspace",
                    tmpdir,
                ],
            ), mock.patch.object(module, "_resolve_package_root", return_value=package_root), mock.patch.object(
                module,
                "_build_cli_command",
                return_value=["python3", "xanadAssistant.py", "inspect"],
            ), mock.patch.object(module.subprocess, "run", return_value=mock.Mock(returncode=0)), self.assertRaises(SystemExit) as excinfo:
                module.main()

        self.assertEqual(excinfo.exception.code, 0)


if __name__ == "__main__":
    unittest.main()