"""Direct unit tests for scripts/lifecycle/_xanad/_workspace_scan.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._workspace_scan import (
    _detect_language,
    _detect_package_manager,
    _detect_test_command,
    scan_workspace_stack,
)


class DetectLanguageTests(unittest.TestCase):
    def test_detects_python_from_pyproject_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "pyproject.toml").write_text("[build-system]\n", encoding="utf-8")
            self.assertEqual("Python", _detect_language(ws))

    def test_detects_python_from_setup_py(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "setup.py").write_text("from setuptools import setup\n", encoding="utf-8")
            self.assertEqual("Python", _detect_language(ws))

    def test_detects_python_from_requirements_txt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "requirements.txt").write_text("requests\n", encoding="utf-8")
            self.assertEqual("Python", _detect_language(ws))

    def test_detects_rust(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "Cargo.toml").write_text("[package]\nname = \"app\"\n", encoding="utf-8")
            self.assertEqual("Rust", _detect_language(ws))

    def test_detects_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "go.mod").write_text("module example.com/app\n", encoding="utf-8")
            self.assertEqual("Go", _detect_language(ws))

    def test_detects_java_from_pom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "pom.xml").write_text("<project/>\n", encoding="utf-8")
            self.assertEqual("Java", _detect_language(ws))

    def test_detects_java_from_gradle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "build.gradle").write_text("plugins {}\n", encoding="utf-8")
            self.assertEqual("Java", _detect_language(ws))

    def test_detects_java_from_gradle_kts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")
            self.assertEqual("Java", _detect_language(ws))

    def test_detects_ruby(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
            self.assertEqual("Ruby", _detect_language(ws))

    def test_detects_typescript_from_package_json_and_tsconfig(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "package.json").write_text('{"name": "app"}\n', encoding="utf-8")
            (ws / "tsconfig.json").write_text("{}\n", encoding="utf-8")
            self.assertEqual("TypeScript", _detect_language(ws))

    def test_detects_javascript_from_package_json_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "package.json").write_text('{"name": "app"}\n', encoding="utf-8")
            self.assertEqual("JavaScript", _detect_language(ws))

    def test_returns_none_for_empty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(_detect_language(Path(tmp)))


class DetectPackageManagerTests(unittest.TestCase):
    def test_detects_yarn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "yarn.lock").write_text("# yarn\n", encoding="utf-8")
            self.assertEqual("yarn", _detect_package_manager(ws))

    def test_detects_pnpm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "pnpm-lock.yaml").write_text("lockfileVersion: 6.0\n", encoding="utf-8")
            self.assertEqual("pnpm", _detect_package_manager(ws))

    def test_detects_npm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "package-lock.json").write_text('{"lockfileVersion": 2}\n', encoding="utf-8")
            self.assertEqual("npm", _detect_package_manager(ws))

    def test_detects_poetry_from_poetry_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "poetry.lock").write_text("[metadata]\n", encoding="utf-8")
            self.assertEqual("Poetry", _detect_package_manager(ws))

    def test_detects_poetry_from_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "pyproject.toml").write_text("[tool.poetry]\nname = \"app\"\n", encoding="utf-8")
            self.assertEqual("Poetry", _detect_package_manager(ws))

    def test_detects_pipenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "Pipfile").write_text("[[source]]\n", encoding="utf-8")
            self.assertEqual("pipenv", _detect_package_manager(ws))

    def test_detects_cargo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
            self.assertEqual("Cargo", _detect_package_manager(ws))

    def test_detects_go_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "go.mod").write_text("module x\n", encoding="utf-8")
            self.assertEqual("go modules", _detect_package_manager(ws))

    def test_detects_pip_from_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "requirements.txt").write_text("requests\n", encoding="utf-8")
            self.assertEqual("pip", _detect_package_manager(ws))

    def test_returns_none_for_empty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(_detect_package_manager(Path(tmp)))

    def test_returns_none_for_pyproject_without_poetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "pyproject.toml").write_text("[build-system]\n", encoding="utf-8")
            result = _detect_package_manager(ws)
            # No poetry marker, no lock files → None
            self.assertIsNone(result)


class DetectTestCommandTests(unittest.TestCase):
    def test_detects_from_package_json_test_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            pkg = {"scripts": {"test": "jest --coverage"}}
            (ws / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
            self.assertEqual("jest --coverage", _detect_test_command(ws))

    def test_ignores_echo_no_test_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            pkg = {"scripts": {"test": 'echo "Error: no test specified"'}}
            (ws / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
            self.assertIsNone(_detect_test_command(ws))

    def test_detects_go_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "go.mod").write_text("module x\n", encoding="utf-8")
            self.assertEqual("go test ./...", _detect_test_command(ws))

    def test_detects_cargo_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
            self.assertEqual("cargo test", _detect_test_command(ws))

    def test_detects_pytest_from_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
            self.assertEqual("pytest", _detect_test_command(ws))

    def test_detects_make_test_from_makefile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "Makefile").write_text("test:\n\techo run\n", encoding="utf-8")
            self.assertEqual("make test", _detect_test_command(ws))

    def test_returns_none_for_empty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(_detect_test_command(Path(tmp)))


class ScanWorkspaceStackTests(unittest.TestCase):
    def test_returns_all_tokens_for_python_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "pyproject.toml").write_text("[tool.pytest.ini_options]\n[tool.poetry]\nname = \"app\"\n", encoding="utf-8")
            (ws / "poetry.lock").write_text("[metadata]\n", encoding="utf-8")
            result = scan_workspace_stack(ws)
            self.assertEqual("Python", result.get("{{PRIMARY_LANGUAGE}}"))
            self.assertEqual("Poetry", result.get("{{PACKAGE_MANAGER}}"))
            self.assertEqual("pytest", result.get("{{TEST_COMMAND}}"))

    def test_returns_empty_dict_for_empty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = scan_workspace_stack(Path(tmp))
            self.assertEqual({}, result)

    def test_keys_use_double_brace_token_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "go.mod").write_text("module x\n", encoding="utf-8")
            result = scan_workspace_stack(ws)
            for key in result:
                self.assertTrue(key.startswith("{{") and key.endswith("}}"), f"Key {key!r} lacks token delimiters")
