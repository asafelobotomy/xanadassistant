from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TEST_REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_SCRIPT_PATH = TEST_REPO_ROOT / "scripts" / "lifecycle" / "xanadAssistant.py"


def run_lifecycle_subprocess(
    command: str,
    *extra_args: str,
    workspace: Path | None = None,
    repo_root: Path = TEST_REPO_ROOT,
    package_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command_args = [sys.executable, str(repo_root / "scripts" / "lifecycle" / "xanadAssistant.py"), command]
    if command == "plan" and extra_args and not extra_args[0].startswith("-"):
        command_args.append(extra_args[0])
        extra_args = extra_args[1:]
    if workspace is not None:
        effective_pkg_root = package_root if package_root is not None else repo_root
        command_args.extend(["--workspace", str(workspace), "--package-root", str(effective_pkg_root)])
    command_args.extend(extra_args)
    return subprocess.run(
        command_args,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


class XanadTestBase(unittest.TestCase):
    REPO_ROOT = TEST_REPO_ROOT
    SCRIPT = TEST_SCRIPT_PATH

    def merge_nested_dicts(self, base: dict, overrides: dict) -> dict:
        merged = dict(base)
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self.merge_nested_dicts(merged[key], value)
            else:
                merged[key] = value
        return merged

    def remove_nested_keys(self, data: dict, remove_paths: tuple[str, ...]) -> dict:
        trimmed = dict(data)
        for path in remove_paths:
            parts = path.split(".")
            target = trimmed
            for part in parts[:-1]:
                next_target = target.get(part)
                if not isinstance(next_target, dict):
                    target = None
                    break
                target = next_target
            if isinstance(target, dict):
                target.pop(parts[-1], None)
        return trimmed

    def make_minimal_lockfile(self, *, remove_paths: tuple[str, ...] = (), **overrides: object) -> dict:
        base = {
            "schemaVersion": "0.1.0",
            "package": {"name": "xanadAssistant"},
            "manifest": {"schemaVersion": "0.1.0", "hash": "sha256:test"},
            "timestamps": {
                "appliedAt": "2026-05-07T00:00:00Z",
                "updatedAt": "2026-05-07T00:00:00Z",
            },
            "selectedPacks": [],
            "profile": "balanced",
            "ownershipBySurface": {},
            "files": [],
        }
        merged = self.merge_nested_dicts(base, overrides)
        return self.remove_nested_keys(merged, remove_paths)

    def render_setup_prompt(self, repo_root: Path, workspace: Path, profile: str = "balanced") -> str:
        return (
            (repo_root / "template" / "prompts" / "setup.md")
            .read_text(encoding="utf-8")
            .replace("{{WORKSPACE_NAME}}", workspace.name)
            .replace("{{XANAD_PROFILE}}", profile)
        )

    def render_update_prompt(self, repo_root: Path, workspace: Path, profile: str = "balanced") -> str:
        return (
            (repo_root / "template" / "prompts" / "update.md")
            .read_text(encoding="utf-8")
            .replace("{{WORKSPACE_NAME}}", workspace.name)
            .replace("{{XANAD_PROFILE}}", profile)
        )

    def render_copilot_instructions(self, repo_root: Path, workspace: Path) -> str:
        """Render copilot-instructions.md with default token values for an empty workspace."""
        return (
            (repo_root / "template" / "copilot-instructions.md")
            .read_text(encoding="utf-8")
            .replace("{{WORKSPACE_NAME}}", workspace.name)
            .replace("{{RESPONSE_STYLE}}", "Balanced — code with brief explanation.")
            .replace("{{AUTONOMY_LEVEL}}", "Ask first — always confirm before acting on ambiguity.")
            .replace("{{AGENT_PERSONA}}", "Professional — concise, neutral, precise.")
            .replace("{{TESTING_PHILOSOPHY}}", "Always — write tests alongside every code change.")
            .replace("{{PRIMARY_LANGUAGE}}", "(not detected)")
            .replace("{{PACKAGE_MANAGER}}", "(not detected)")
            .replace("{{TEST_COMMAND}}", "(not detected)")
        )

    def render_instructions_file(self, template_path: Path) -> str:
        """Render an instructions template file with default token values for an empty workspace."""
        return (
            template_path.read_text(encoding="utf-8")
            .replace("{{PRIMARY_LANGUAGE}}", "(not detected)")
            .replace("{{PACKAGE_MANAGER}}", "(not detected)")
            .replace("{{TEST_COMMAND}}", "(not detected)")
            .replace("{{TESTING_PHILOSOPHY}}", "Always \u2014 write tests alongside every code change.")
        )

    def _run(self, command: str, *extra_args: str, workspace: Path | None = None, package_root: Path | None = None) -> subprocess.CompletedProcess[str]:
        return run_lifecycle_subprocess(command, *extra_args, workspace=workspace, repo_root=self.REPO_ROOT, package_root=package_root)

    def run_command_in_workspace(self, workspace: Path, command: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return self._run(command, *extra_args, workspace=workspace)

    def run_command(self, command: str, *extra_args: str, workspace_setup=None) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            if workspace_setup is not None:
                workspace_setup(workspace, self.REPO_ROOT)
            return self.run_command_in_workspace(workspace, command, *extra_args)
