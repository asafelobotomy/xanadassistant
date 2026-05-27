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
                    self.assertEqual(module.git_diff_unstaged_stat(self._repo_dir), "ok")
                    self.assertEqual(module.git_diff_staged_stat(self._repo_dir), "ok")
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
                    self.assertEqual(module.git_reset(self._repo_dir, files=["a.py"]), "ok")
                    commit_result = module.git_commit(self._repo_dir, "subject\n\nbody")
                    self.assertEqual(commit_result["status"], "ok")
                    self.assertEqual(commit_result["operation"], "git_commit")
                    self.assertEqual(commit_result["exitCode"], 0)
                    self.assertEqual(commit_result["message"], "subject\n\nbody")
                    self.assertEqual(commit_result["stdout"], "ok")
                    self.assertEqual(commit_result["stderr"], "")
                    self.assertEqual(module.git_stash(self._repo_dir, "wip"), "ok")
                    stash_apply_result = module.git_stash_apply(self._repo_dir)
                    self.assertEqual(stash_apply_result["status"], "ok")
                    self.assertEqual(stash_apply_result["operation"], "git_stash_apply")
                    self.assertEqual(stash_apply_result["exitCode"], 0)
                    self.assertEqual(stash_apply_result["stashRef"], "")
                    self.assertEqual(stash_apply_result["stdout"], "ok")
                    self.assertEqual(stash_apply_result["stderr"], "")
                    stash_apply_named_result = module.git_stash_apply(self._repo_dir, stash_ref="stash@{2}")
                    self.assertEqual(stash_apply_named_result["stashRef"], "stash@{2}")
                    self.assertEqual(module.git_stash_pop(self._repo_dir), "ok")
                    stash_drop_result = module.git_stash_drop(self._repo_dir)
                    self.assertEqual(stash_drop_result["status"], "ok")
                    self.assertEqual(stash_drop_result["operation"], "git_stash_drop")
                    self.assertEqual(stash_drop_result["exitCode"], 0)
                    self.assertEqual(stash_drop_result["stashRef"], "")
                    self.assertEqual(stash_drop_result["stdout"], "ok")
                    self.assertEqual(stash_drop_result["stderr"], "")
                    stash_drop_named_result = module.git_stash_drop(self._repo_dir, stash_ref="stash@{1}")
                    self.assertEqual(stash_drop_named_result["stashRef"], "stash@{1}")
                    self.assertEqual(module.git_stash_list(self._repo_dir), "ok")
                    self.assertEqual(module.git_tag(self._repo_dir, "v1.2.3", ref="main"), "ok")
                    self.assertEqual(module.git_tag(self._repo_dir, "v1.2.4", message="release", ref="main"), "ok")
                    self.assertEqual(module.git_tag_list(self._repo_dir), "ok")
                    self.assertEqual(module.git_push_tag(self._repo_dir, "v1.2.4"), "ok")
                    self.assertEqual(module.git_push_tag(self._repo_dir, "v1.2.4", remote="upstream"), "ok")
                    rebase_start_result = module.git_rebase(self._repo_dir, onto="main")
                    self.assertEqual(rebase_start_result["status"], "ok")
                    self.assertEqual(rebase_start_result["operation"], "git_rebase")
                    self.assertEqual(rebase_start_result["exitCode"], 0)
                    self.assertEqual(rebase_start_result["action"], "start")
                    self.assertEqual(rebase_start_result["onto"], "main")
                    self.assertEqual(rebase_start_result["stdout"], "ok")
                    self.assertEqual(rebase_start_result["stderr"], "")
                    rebase_continue_result = module.git_rebase(self._repo_dir, action="continue")
                    self.assertEqual(rebase_continue_result["action"], "continue")
                    self.assertEqual(rebase_continue_result["onto"], "")
                    merge_start_result = module.git_merge(self._repo_dir, branch="feature")
                    self.assertEqual(merge_start_result["status"], "ok")
                    self.assertEqual(merge_start_result["operation"], "git_merge")
                    self.assertEqual(merge_start_result["exitCode"], 0)
                    self.assertEqual(merge_start_result["action"], "start")
                    self.assertEqual(merge_start_result["branch"], "feature")
                    merge_noff_result = module.git_merge(self._repo_dir, branch="feature", no_ff=True, message="merge!")
                    self.assertEqual(merge_noff_result["action"], "start")
                    merge_continue_result = module.git_merge(self._repo_dir, action="continue")
                    self.assertEqual(merge_continue_result["action"], "continue")
                    self.assertEqual(merge_continue_result["branch"], "")
                    merge_continue_msg_result = module.git_merge(self._repo_dir, action="continue", message="resolved")
                    self.assertEqual(merge_continue_msg_result["action"], "continue")
                    merge_abort_result = module.git_merge(self._repo_dir, action="abort")
                    self.assertEqual(merge_abort_result["action"], "abort")
                    self.assertEqual(merge_abort_result["branch"], "")
                    self.assertEqual(module.git_fetch(self._repo_dir, remote="origin", prune=True), "ok")
                    # no-branch pull: should omit remote and use configured upstream
                    pull_no_branch = module.git_pull(self._repo_dir, remote="origin")
                    self.assertTrue(pull_no_branch["ok"])
                    self.assertEqual(pull_no_branch["branch"], "")
                    pull_no_branch_rebase = module.git_pull(self._repo_dir, remote="origin", rebase=True)
                    self.assertTrue(pull_no_branch_rebase["ok"])
                    self.assertTrue(pull_no_branch_rebase["rebase"])
                    pull_result = module.git_pull(self._repo_dir, remote="origin", branch="main", rebase=True)
                    self.assertTrue(pull_result["ok"])
                    self.assertEqual(pull_result["status"], "ok")
                    self.assertEqual(pull_result["operation"], "git_pull")
                    self.assertEqual(pull_result["exitCode"], 0)
                    self.assertEqual(pull_result["remote"], "origin")
                    self.assertEqual(pull_result["branch"], "main")
                    self.assertTrue(pull_result["rebase"])
                    self.assertEqual(pull_result["stdout"], "ok")
                    self.assertEqual(pull_result["stderr"], "")
                    push_result = module.git_push(
                        self._repo_dir,
                        remote="origin",
                        branch="main",
                        force_with_lease=True,
                        set_upstream=True,
                        tags=True,
                    )
                    self.assertEqual(push_result["status"], "ok")
                    self.assertEqual(push_result["operation"], "git_push")
                    self.assertEqual(push_result["exitCode"], 0)
                    self.assertEqual(push_result["remote"], "origin")
                    self.assertEqual(push_result["branch"], "main")
                    self.assertTrue(push_result["forceWithLease"])
                    self.assertTrue(push_result["setUpstream"])
                    self.assertTrue(push_result["tags"])
                    self.assertEqual(push_result["stdout"], "ok")
                    self.assertEqual(push_result["stderr"], "")

                commands = [call.kwargs["args"] if "args" in call.kwargs else call.args[0] for call in run_mock.call_args_list]
                self.assertIn(["git", "status", "--porcelain"], commands)
                self.assertIn(["git", "diff", "--stat"], commands)
                self.assertIn(["git", "diff", "--cached", "--stat"], commands)
                self.assertIn(["git", "reset", "HEAD", "--", "a.py"], commands)
                self.assertIn(["git", "diff", "-U4", "HEAD", "main"], commands)
                self.assertIn(["git", "pull"], commands)
                self.assertIn(["git", "pull", "--rebase"], commands)
                self.assertIn(["git", "diff", "-U5"], commands)
                self.assertIn(["git", "diff", "--cached", "-U2"], commands)
                self.assertIn(["git", "stash", "apply"], commands)
                self.assertIn(["git", "stash", "apply", "stash@{2}"], commands)
                self.assertIn(["git", "stash", "drop"], commands)
                self.assertIn(["git", "stash", "drop", "stash@{1}"], commands)
                self.assertIn(["git", "tag", "-a", "v1.2.4", "-m", "release", "main"], commands)
                self.assertIn(["git", "push", "origin", "refs/tags/v1.2.4:refs/tags/v1.2.4"], commands)
                self.assertIn(["git", "push", "upstream", "refs/tags/v1.2.4:refs/tags/v1.2.4"], commands)
                self.assertIn(["git", "push", "-u", "--force-with-lease", "--tags", "origin", "main"], commands)
                self.assertIn(["git", "merge", "feature"], commands)
                self.assertIn(["git", "merge", "--no-ff", "-m", "merge!", "feature"], commands)
                self.assertIn(["git", "merge", "--continue", "--no-edit"], commands)
                self.assertIn(["git", "merge", "--continue", "-m", "resolved"], commands)
                self.assertIn(["git", "merge", "--abort"], commands)

    def test_validation_and_error_paths(self) -> None:
        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "must not be empty"):
                    module.git_commit("/repo", "   ")
                with self.assertRaisesRegex(ValueError, "required when action='start'"):
                    module.git_rebase("/repo")
                with self.assertRaisesRegex(ValueError, "required when action='start'"):
                    module.git_merge(self._repo_dir)
                with mock.patch.object(
                    module.subprocess,
                    "run",
                    return_value=mock.Mock(returncode=1, stdout="stdout failure\n", stderr=""),
                ):
                    with self.assertRaisesRegex(RuntimeError, "stdout failure"):
                        module.git_status(self._repo_dir)

    def test_structured_mutation_tools_return_failed_envelopes(self) -> None:
        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(
                    module.subprocess,
                    "run",
                    return_value=mock.Mock(returncode=1, stdout="", stderr="fatal: could not apply\n"),
                ):
                    commit_result = module.git_commit(self._repo_dir, "subject")
                    rebase_result = module.git_rebase(self._repo_dir, onto="main")
                    merge_result = module.git_merge(self._repo_dir, branch="feature")
                    stash_apply_result = module.git_stash_apply(self._repo_dir, stash_ref="stash@{2}")
                    stash_drop_result = module.git_stash_drop(self._repo_dir, stash_ref="stash@{1}")

                self.assertEqual(commit_result["status"], "failed")
                self.assertEqual(commit_result["operation"], "git_commit")
                self.assertEqual(commit_result["exitCode"], 1)
                self.assertEqual(commit_result["stderr"], "fatal: could not apply")

                self.assertEqual(rebase_result["status"], "failed")
                self.assertEqual(rebase_result["operation"], "git_rebase")
                self.assertEqual(rebase_result["action"], "start")
                self.assertEqual(rebase_result["onto"], "main")

                self.assertEqual(merge_result["status"], "failed")
                self.assertEqual(merge_result["operation"], "git_merge")
                self.assertEqual(merge_result["action"], "start")
                self.assertEqual(merge_result["branch"], "feature")

                pull_result = module.git_pull(self._repo_dir, remote="origin", branch="main", rebase=True)
                self.assertEqual(pull_result["status"], "failed")
                self.assertEqual(pull_result["operation"], "git_pull")
                self.assertEqual(pull_result["remote"], "origin")
                self.assertEqual(pull_result["branch"], "main")
                self.assertTrue(pull_result["rebase"])

                self.assertEqual(stash_apply_result["status"], "failed")
                self.assertEqual(stash_apply_result["operation"], "git_stash_apply")
                self.assertEqual(stash_apply_result["stashRef"], "stash@{2}")

                self.assertEqual(stash_drop_result["status"], "failed")
                self.assertEqual(stash_drop_result["operation"], "git_stash_drop")
                self.assertEqual(stash_drop_result["stashRef"], "stash@{1}")

    def test_structured_mutation_tools_share_common_envelope_fields(self) -> None:
        required_fields = {
            "ok",
            "status",
            "operation",
            "command",
            "exitCode",
            "stdout",
            "stderr",
            "summary",
        }

        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                completed = mock.Mock(returncode=0, stdout="ok\n", stderr="")
                with mock.patch.object(module.subprocess, "run", return_value=completed):
                    results = [
                        module.git_commit(self._repo_dir, "subject"),
                        module.git_rebase(self._repo_dir, onto="main"),
                        module.git_merge(self._repo_dir, branch="feature"),
                        module.git_stash_apply(self._repo_dir),
                        module.git_stash_drop(self._repo_dir),
                        module.git_pull(self._repo_dir, remote="origin", branch="main", rebase=True),
                        module.git_push(self._repo_dir, remote="origin", branch="main"),
                    ]

                for result in results:
                    with self.subTest(operation=result["operation"]):
                        self.assertTrue(required_fields.issubset(result.keys()))
                        self.assertTrue(result["ok"])
                        self.assertEqual(result["status"], "ok")
                        self.assertIsInstance(result["command"], list)
                        self.assertIsInstance(result["summary"], str)
                        self.assertTrue(result["summary"])

    def test_git_push_returns_failed_envelope_on_rejected_push(self) -> None:
        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(
                    module.subprocess,
                    "run",
                    return_value=mock.Mock(returncode=1, stdout="", stderr="[rejected] main -> main\n"),
                ):
                    result = module.git_push(self._repo_dir, remote="origin", branch="main")

                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["operation"], "git_push")
                self.assertEqual(result["exitCode"], 1)
                self.assertEqual(result["remote"], "origin")
                self.assertEqual(result["branch"], "main")
                self.assertFalse(result["forceWithLease"])
                self.assertFalse(result["setUpstream"])
                self.assertFalse(result["tags"])
                self.assertEqual(result["stdout"], "")
                self.assertEqual(result["stderr"], "[rejected] main -> main")

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

    def test_git_push_tag_rejects_flag_like_tag_name(self) -> None:
        for module in (SOURCE_GIT_MODULE, MANAGED_GIT_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "looks like a flag"):
                    module.git_push_tag("/tmp", "--force")


if __name__ == "__main__":
    unittest.main()