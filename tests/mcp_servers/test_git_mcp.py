from __future__ import annotations

import shutil
import tempfile
import unittest
from unittest import mock

from tests.mcp_servers._mcp_module_loader import load_mcp_script_module

SOURCE_GIT_MODULE = load_mcp_script_module("mcp/scripts/gitMcp.py", "test_gitMcp_source", "gitMcp.py")
MANAGED_GIT_MODULE = load_mcp_script_module(".github/mcp/scripts/gitMcp.py", "test_gitMcp_managed", "gitMcp.py")


class GitMcpTests(unittest.TestCase):
    def setUp(self) -> None:
        self._repo_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self._repo_dir, ignore_errors=True)

    def test_public_commands_build_expected_git_argv(self) -> None:
        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                completed = mock.Mock(returncode=0, stdout="ok\n", stderr="")
                with mock.patch.object(module.subprocess, "run", return_value=completed) as run_mock:
                    self.assertEqual(module.git_status(self._repo_dir), "ok")
                    self.assertEqual(module.git_diff_unstaged(self._repo_dir, context_lines=5), "ok")
                    self.assertEqual(module.git_diff_staged(self._repo_dir, context_lines=2), "ok")
                    self.assertEqual(module.git_diff(self._repo_dir, "main", context_lines=4), "ok")
                    self.assertEqual(module.git_log(self._repo_dir, max_count=7, branch="main"), "ok")
                    self.assertEqual(module.git_show(self._repo_dir, "HEAD"), "ok")
                    self.assertEqual(module.git_branch_list(self._repo_dir, scope="remote"), "ok")
                    self.assertEqual(module.git_create_branch(self._repo_dir, "feature/demo", "main"), "ok")
                    self.assertEqual(module.git_delete_branch(self._repo_dir, "feature/demo", force=True), "ok")
                    self.assertEqual(module.git_add(self._repo_dir, ["a.py", "b.py"]), "ok")
                    self.assertEqual(module.git_reset(self._repo_dir), "ok")
                    self.assertEqual(module.git_commit(self._repo_dir, "subject\n\nbody"), "ok")
                    self.assertEqual(module.git_stash(self._repo_dir, "wip"), "ok")
                    self.assertEqual(module.git_stash_pop(self._repo_dir), "ok")
                    self.assertEqual(module.git_stash_list(self._repo_dir), "ok")
                    self.assertEqual(module.git_tag(self._repo_dir, "v1.2.3", ref="main"), "ok")
                    self.assertEqual(module.git_tag(self._repo_dir, "v1.2.4", message="release", ref="main"), "ok")
                    self.assertEqual(module.git_tag_list(self._repo_dir), "ok")
                    self.assertEqual(module.git_rebase(self._repo_dir, onto="main"), "ok")
                    self.assertEqual(module.git_rebase(self._repo_dir, action="continue"), "ok")
                    self.assertEqual(module.git_fetch(self._repo_dir, remote="origin", prune=True), "ok")
                    self.assertEqual(module.git_pull(self._repo_dir, remote="origin", branch="main", rebase=True), "ok")
                    self.assertEqual(
                        module.git_push(
                            self._repo_dir,
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
                        module.git_status(self._repo_dir)

    def test_validate_repo_path_rejects_invalid_paths(self) -> None:
        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "must not be empty"):
                    module._validate_repo_path("")
                with self.assertRaisesRegex(ValueError, "must not be empty"):
                    module._validate_repo_path("   ")
                with self.assertRaisesRegex(ValueError, "does not exist or is not a directory"):
                    module._validate_repo_path("/this/path/does/not/exist")
                with tempfile.NamedTemporaryFile() as f:
                    with self.assertRaisesRegex(ValueError, "does not exist or is not a directory"):
                        module._validate_repo_path(f.name)

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