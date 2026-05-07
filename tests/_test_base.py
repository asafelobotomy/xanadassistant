from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class XanadTestBase(unittest.TestCase):
    def render_setup_prompt(self, repo_root: Path, workspace: Path, profile: str = "balanced") -> str:
        return (
            (repo_root / "template" / "prompts" / "setup.md")
            .read_text(encoding="utf-8")
            .replace("{{WORKSPACE_NAME}}", workspace.name)
            .replace("{{XANAD_PROFILE}}", profile)
        )

    def run_command_in_workspace(self, workspace: Path, command: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts/lifecycle/xanad_assistant.py"
        command_args = [
            sys.executable,
            str(script_path),
            command,
        ]
        if command == "plan" and extra_args:
            command_args.extend([extra_args[0], "--workspace", str(workspace), "--package-root", str(repo_root), *extra_args[1:]])
        else:
            command_args.extend(
                [
                    "--workspace",
                    str(workspace),
                    "--package-root",
                    str(repo_root),
                    *extra_args,
                ]
            )
        return subprocess.run(
            command_args,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

    def run_command(self, command: str, *extra_args: str, workspace_setup=None) -> subprocess.CompletedProcess[str]:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            if workspace_setup is not None:
                workspace_setup(workspace, repo_root)
            return self.run_command_in_workspace(workspace, command, *extra_args)
