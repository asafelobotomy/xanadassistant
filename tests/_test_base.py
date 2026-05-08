from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TEST_REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_SCRIPT_PATH = TEST_REPO_ROOT / "scripts" / "lifecycle" / "xanad_assistant.py"


def run_lifecycle_subprocess(
    command: str,
    *extra_args: str,
    workspace: Path | None = None,
    repo_root: Path = TEST_REPO_ROOT,
) -> subprocess.CompletedProcess[str]:
    command_args = [sys.executable, str(repo_root / "scripts" / "lifecycle" / "xanad_assistant.py"), command]
    if command == "plan" and extra_args and not extra_args[0].startswith("-"):
        command_args.append(extra_args[0])
        extra_args = extra_args[1:]
    if workspace is not None:
        command_args.extend(["--workspace", str(workspace), "--package-root", str(repo_root)])
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
            "package": {"name": "xanad-assistant"},
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

    def _run(self, command: str, *extra_args: str, workspace: Path | None = None) -> subprocess.CompletedProcess[str]:
        return run_lifecycle_subprocess(command, *extra_args, workspace=workspace, repo_root=self.REPO_ROOT)

    def run_command_in_workspace(self, workspace: Path, command: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return self._run(command, *extra_args, workspace=workspace)

    def run_command(self, command: str, *extra_args: str, workspace_setup=None) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            if workspace_setup is not None:
                workspace_setup(workspace, self.REPO_ROOT)
            return self.run_command_in_workspace(workspace, command, *extra_args)
