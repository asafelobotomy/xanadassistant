from __future__ import annotations

import json
from pathlib import Path


def scan_workspace_stack(workspace: Path) -> dict[str, str]:
    """Detect PRIMARY_LANGUAGE, PACKAGE_MANAGER, and TEST_COMMAND from workspace project files.

    Returns a dict containing only the tokens for which detection was confident.
    Absent keys should be treated as undetected; the consumer fills them in manually.
    """
    results: dict[str, str] = {}

    language = _detect_language(workspace)
    if language:
        results["{{PRIMARY_LANGUAGE}}"] = language

    pm = _detect_package_manager(workspace)
    if pm:
        results["{{PACKAGE_MANAGER}}"] = pm

    test_cmd = _detect_test_command(workspace)
    if test_cmd:
        results["{{TEST_COMMAND}}"] = test_cmd

    return results


# Priority-ordered language detection rules (first match wins).
_LANGUAGE_CHECKS: list[tuple[str, str]] = [
    ("pyproject.toml", "Python"),
    ("setup.py", "Python"),
    ("requirements.txt", "Python"),
    ("Cargo.toml", "Rust"),
    ("go.mod", "Go"),
    ("pom.xml", "Java"),
    ("build.gradle", "Java"),
    ("build.gradle.kts", "Java"),
    ("Gemfile", "Ruby"),
]


def _detect_language(workspace: Path) -> str | None:
    for filename, language in _LANGUAGE_CHECKS:
        if (workspace / filename).exists():
            return language
    pkg = workspace / "package.json"
    if pkg.exists():
        if (workspace / "tsconfig.json").exists():
            return "TypeScript"
        return "JavaScript"
    return None


def _detect_package_manager(workspace: Path) -> str | None:
    if (workspace / "yarn.lock").exists():
        return "yarn"
    if (workspace / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (workspace / "package-lock.json").exists():
        return "npm"
    if (workspace / "poetry.lock").exists():
        return "Poetry"
    pyproject = workspace / "pyproject.toml"
    if pyproject.exists():
        try:
            if "[tool.poetry]" in pyproject.read_text(encoding="utf-8"):
                return "Poetry"
        except OSError:
            pass
    if (workspace / "Pipfile").exists():
        return "pipenv"
    if (workspace / "Cargo.toml").exists():
        return "Cargo"
    if (workspace / "go.mod").exists():
        return "go modules"
    if (workspace / "requirements.txt").exists():
        return "pip"
    return None


def _detect_test_command(workspace: Path) -> str | None:
    pkg = workspace / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            test_script = (data.get("scripts") or {}).get("test")
            _NO_TEST = 'echo "Error: no test specified"'
            if isinstance(test_script, str) and test_script and test_script.strip() != _NO_TEST:
                return test_script
        except (OSError, json.JSONDecodeError):
            pass
    if (workspace / "go.mod").exists():
        return "go test ./..."
    if (workspace / "Cargo.toml").exists():
        return "cargo test"
    pyproject = workspace / "pyproject.toml"
    if pyproject.exists():
        try:
            text = pyproject.read_text(encoding="utf-8")
            if "pytest" in text or "[tool.pytest" in text:
                return "pytest"
        except OSError:
            pass
    makefile = workspace / "Makefile"
    if makefile.exists():
        try:
            text = makefile.read_text(encoding="utf-8")
            if "\ntest:" in text or text.startswith("test:"):
                return "make test"
        except OSError:
            pass
    return None
