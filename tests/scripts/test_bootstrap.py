from __future__ import annotations

import importlib.util
import tempfile
import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_bootstrap():
    spec = importlib.util.spec_from_file_location("xanadBootstrap", _REPO_ROOT / "xanadBootstrap.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load xanadBootstrap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_bootstrap = _load_bootstrap()


class CacheKeyTests(unittest.TestCase):
    def test_cache_key_avoids_collision_between_slash_and_hyphen_ref(self) -> None:
        key_slash = _bootstrap._cache_key("feature/x")
        key_hyphen = _bootstrap._cache_key("feature-x")
        self.assertNotEqual(key_slash, key_hyphen)

    def test_cache_key_produces_readable_slug_prefix(self) -> None:
        key = _bootstrap._cache_key("feature/my-branch")
        # Slug must not start with a digest-only string; human-readable prefix expected
        self.assertTrue(key.startswith("feature-my-branch-"))

    def test_cache_key_appends_twelve_char_hex_digest(self) -> None:
        key = _bootstrap._cache_key("main")
        parts = key.rsplit("-", 1)
        self.assertEqual(len(parts), 2)
        digest = parts[1]
        self.assertEqual(len(digest), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in digest))

    def test_cache_key_is_deterministic(self) -> None:
        self.assertEqual(_bootstrap._cache_key("v1.0.0"), _bootstrap._cache_key("v1.0.0"))

    def test_cache_key_sanitises_special_characters(self) -> None:
        key = _bootstrap._cache_key("refs/heads/feat@2024")
        # No raw slashes or @ characters in the key
        self.assertNotIn("/", key)
        self.assertNotIn("@", key)


class BootstrapCommandTests(unittest.TestCase):
    def test_build_cli_command_accepts_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir)
            entry = package_root / "xanadAssistant.py"
            entry.write_text("# stub\n", encoding="utf-8")
            args = type("Args", (), {"command": "setup", "mode": None, "workspace": tmpdir})()

            command = _bootstrap._build_cli_command(package_root, args, ["--plan", "plan.json"])

        self.assertEqual(command[:3], [sys.executable, str(entry), "setup"])
        self.assertIn("--plan", command)
        self.assertIn("plan.json", command)

    def test_main_accepts_setup_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            package_root = Path(tmpdir) / "package"
            package_root.mkdir()

            with mock.patch(
                "sys.argv",
                [
                    "xanadBootstrap.py",
                    "setup",
                    "--workspace",
                    tmpdir,
                    "--plan",
                    "plan.json",
                ],
            ), mock.patch.object(_bootstrap, "_resolve_package_root", return_value=package_root), mock.patch.object(
                _bootstrap,
                "_build_cli_command",
                return_value=["python3", "xanadAssistant.py", "setup", "--plan", "plan.json"],
            ) as build_command, mock.patch.object(
                _bootstrap.subprocess,
                "run",
                return_value=mock.Mock(returncode=0),
            ), self.assertRaises(SystemExit) as excinfo:
                _bootstrap.main()

        self.assertEqual(excinfo.exception.code, 0)
        self.assertEqual(build_command.call_args.args[0], package_root)
        self.assertEqual(build_command.call_args.args[1].command, "setup")

    def test_main_rejects_retired_apply_command_at_parse_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch(
            "sys.argv",
            [
                "xanadBootstrap.py",
                "apply",
                "--workspace",
                tmpdir,
            ],
        ), self.assertRaises(SystemExit) as excinfo:
            _bootstrap.main()

        self.assertEqual(excinfo.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
