from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


def load_git_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load gitMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SOURCE_GIT_MODULE = load_git_module("mcp/scripts/gitMcp.py", "test_gitMcp_source")
MANAGED_GIT_MODULE = load_git_module(".github/mcp/scripts/gitMcp.py", "test_gitMcp_managed")


class GitMcpTests(unittest.TestCase):
    def test_public_commands_build_expected_git_argv(self) -> None:
        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                completed = mock.Mock(returncode=0, stdout="ok\n", stderr="")
                with mock.patch.object(module.subprocess, "run", return_value=completed) as run_mock:
                    self.assertEqual(module.git_status("/repo"), "ok")
                    self.assertEqual(module.git_diff_unstaged("/repo", context_lines=5), "ok")
                    self.assertEqual(module.git_diff_staged("/repo", context_lines=2), "ok")
                    self.assertEqual(module.git_diff("/repo", "main", context_lines=4), "ok")
                    self.assertEqual(module.git_log("/repo", max_count=7, branch="main"), "ok")
                    self.assertEqual(module.git_show("/repo", "HEAD"), "ok")
                    self.assertEqual(module.git_branch_list("/repo", scope="remote"), "ok")
                    self.assertEqual(module.git_create_branch("/repo", "feature/demo", "main"), "ok")
                    self.assertEqual(module.git_delete_branch("/repo", "feature/demo", force=True), "ok")
                    self.assertEqual(module.git_add("/repo", ["a.py", "b.py"]), "ok")
                    self.assertEqual(module.git_reset("/repo"), "ok")
                    self.assertEqual(module.git_commit("/repo", "subject\n\nbody"), "ok")
                    self.assertEqual(module.git_stash("/repo", "wip"), "ok")
                    self.assertEqual(module.git_stash_pop("/repo"), "ok")
                    self.assertEqual(module.git_stash_list("/repo"), "ok")
                    self.assertEqual(module.git_tag("/repo", "v1.2.3", ref="main"), "ok")
                    self.assertEqual(module.git_tag("/repo", "v1.2.4", message="release", ref="main"), "ok")
                    self.assertEqual(module.git_tag_list("/repo"), "ok")
                    self.assertEqual(module.git_rebase("/repo", onto="main"), "ok")
                    self.assertEqual(module.git_rebase("/repo", action="continue"), "ok")
                    self.assertEqual(module.git_fetch("/repo", remote="origin", prune=True), "ok")
                    self.assertEqual(module.git_pull("/repo", remote="origin", branch="main", rebase=True), "ok")
                    self.assertEqual(
                        module.git_push(
                            "/repo",
                            remote="origin",
                            branch="main",
                            force_with_lease=True,
                            set_upstream=True,
                            tags=True,
                        ),
                        "ok",
                    )

                commands = [call.kwargs["args"] if "args" in call.kwargs else call.args[0] for call in run_mock.call_args_list]
                self.assertIn(["git", "status", "--porcelain"], commands)
                self.assertIn(["git", "diff", "-U5"], commands)
                self.assertIn(["git", "diff", "--cached", "-U2"], commands)
                self.assertIn(["git", "tag", "-a", "v1.2.4", "-m", "release", "main"], commands)
                self.assertIn(["git", "push", "-u", "--force-with-lease", "--tags", "origin", "main"], commands)

    def test_validation_and_error_paths(self) -> None:
        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "must not be empty"):
                    module.git_commit("/repo", "   ")
                with self.assertRaisesRegex(ValueError, "required when action='start'"):
                    module.git_rebase("/repo")
                with mock.patch.object(
                    module.subprocess,
                    "run",
                    return_value=mock.Mock(returncode=1, stdout="stdout failure\n", stderr=""),
                ):
                    with self.assertRaisesRegex(RuntimeError, "stdout failure"):
                        module.git_status("/repo")

    def test_git_checkout_rejects_flag_like_branch_name(self) -> None:
        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "looks like a flag"):
                    module.git_checkout("/tmp", "-b")

    def test_git_tag_rejects_flag_like_name_for_annotated_tag(self) -> None:
        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "looks like a flag"):
                    module.git_tag("/tmp", "--help", message="annotated")


if __name__ == "__main__":
    unittest.main()