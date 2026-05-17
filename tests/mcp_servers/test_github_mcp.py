from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


def load_github_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load githubMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SOURCE_GITHUB_MODULE = load_github_module("mcp/scripts/githubMcp.py", "test_githubMcp_source")
MANAGED_GITHUB_MODULE = load_github_module(".github/mcp/scripts/githubMcp.py", "test_githubMcp_managed")


class GitHubMcpTests(unittest.TestCase):
    def test_helper_validation_and_decode_branches(self) -> None:
        for module in (SOURCE_GITHUB_MODULE, MANAGED_GITHUB_MODULE):
            with self.subTest(module=module.__name__):
                self.assertEqual(module._normalize_per_page(0, 30), 1)
                self.assertEqual(module._normalize_per_page(99, 30), 30)
                self.assertEqual(module._validate_workflow_id(".github/workflows/test.yml"), "test.yml")
                self.assertEqual(module._decode_json_response(b'{"ok": true}', "/repos/o/r"), {"ok": True})
                with self.assertRaisesRegex(ValueError, "Invalid state"):
                    module._validate_state("pending")
                with self.assertRaisesRegex(ValueError, "Invalid workflow_id"):
                    module._validate_workflow_id("bad/name?.yml")
                with self.assertRaisesRegex(RuntimeError, "empty response"):
                    module._decode_json_response(b"", "/repos/o/r")
                with self.assertRaisesRegex(RuntimeError, "non-JSON response"):
                    module._decode_json_response(b"<html>oops</html>", "/repos/o/r")

    def test_token_raises_clear_error_when_no_auth_is_available(self) -> None:
        for module in (SOURCE_GITHUB_MODULE, MANAGED_GITHUB_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=False), mock.patch.object(
                    module, "_gh_cli_token", return_value=""
                ):
                    with self.assertRaisesRegex(RuntimeError, "No GitHub token found"):
                        module._token()

    def test_format_http_error_adds_pull_request_404_hint(self) -> None:
        for module in (SOURCE_GITHUB_MODULE, MANAGED_GITHUB_MODULE):
            with self.subTest(module=module.__name__):
                message = module._format_http_error("/repos/o/r/pulls/123", 404, "not found")

                self.assertIn("use get_issue instead", message)

    def test_get_file_contents_rejects_parent_traversal_and_decodes_base64(self) -> None:
        for module in (SOURCE_GITHUB_MODULE, MANAGED_GITHUB_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "must not contain '..'"):
                    module.get_file_contents("owner", "repo", "../secret.txt")

                encoded = {"encoding": "base64", "content": "aGVsbG8K"}
                with mock.patch.object(module, "_get", return_value=encoded):
                    content = module.get_file_contents("owner", "repo", "docs/readme.md", ref="main")

                self.assertEqual(content, "hello\n")

    def test_search_code_formats_empty_and_non_empty_results(self) -> None:
        for module in (SOURCE_GITHUB_MODULE, MANAGED_GITHUB_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(module, "_get", return_value={"items": [], "total_count": 0}):
                    empty = module.search_code("repo:owner/repo needle")
                with mock.patch.object(
                    module,
                    "_get",
                    return_value={
                        "total_count": 1,
                        "items": [
                            {
                                "repository": {"full_name": "owner/repo"},
                                "path": "src/app.py",
                                "html_url": "https://github.com/owner/repo/blob/main/src/app.py",
                            }
                        ],
                    },
                ):
                    found = module.search_code("repo:owner/repo needle")

                self.assertIn("No code results", empty)
                self.assertIn("owner/repo: src/app.py", found)

    def test_issue_pull_release_and_workflow_formatters(self) -> None:
        for module in (SOURCE_GITHUB_MODULE, MANAGED_GITHUB_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(
                    module,
                    "_get",
                    side_effect=[
                        [
                            {"number": 1, "state": "open", "title": "Issue", "html_url": "https://x", "pull_request": {}},
                            {"number": 2, "state": "open", "title": "Bug", "html_url": "https://y"},
                        ],
                        {"number": 2, "title": "Bug", "state": "open", "body": "desc", "html_url": "https://y"},
                        [
                            {
                                "number": 3,
                                "state": "open",
                                "title": "PR",
                                "head": {"ref": "feature"},
                                "base": {"ref": "main"},
                                "html_url": "https://pr",
                            }
                        ],
                        {"number": 3, "title": "PR", "state": "open", "body": "desc", "html_url": "https://pr"},
                        [{"tag_name": "v1.0.0", "name": "First", "draft": False, "prerelease": False, "published_at": "2026-01-01"}],
                        {"workflow_runs": [{"id": 9, "name": "CI", "status": "completed", "conclusion": "success", "head_branch": "main", "created_at": "2026-01-01", "html_url": "https://run"}]},
                    ],
                ), mock.patch.object(module, "_post", side_effect=[{"html_url": "https://comment"}, {"number": 7, "html_url": "https://pull"}]):
                    issues = module.list_issues("owner", "repo")
                    issue = module.get_issue("owner", "repo", 2)
                    comment = module.create_issue_comment("owner", "repo", 2, "hello")
                    pulls = module.list_pull_requests("owner", "repo")
                    pull = module.get_pull_request("owner", "repo", 3)
                    created = module.create_pull_request("owner", "repo", "Title", "feature", "main", draft=True)
                    releases = module.list_releases("owner", "repo")
                    runs = module.list_workflow_runs("owner", "repo", ".github/workflows/ci.yml", status="completed")

                self.assertIn("#2 [open] Bug", issues)
                self.assertEqual(json.loads(issue)["number"], 2)
                self.assertIn("Comment created", comment)
                self.assertIn("#3 [open] PR", pulls)
                self.assertEqual(json.loads(pull)["number"], 3)
                self.assertIn("Pull request created: #7", created)
                self.assertIn("v1.0.0", releases)
                self.assertIn("#9 CI [completed/success]", runs)

    def test_validation_and_empty_formatter_branches(self) -> None:
        for module in (SOURCE_GITHUB_MODULE, MANAGED_GITHUB_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "Invalid owner name"):
                    module.get_repo("bad owner", "repo")
                with self.assertRaisesRegex(ValueError, "Invalid repo name"):
                    module.get_repo("owner", "bad/repo")

                self.assertIn("request failed", module._format_http_error("/other", 500, ""))

                with mock.patch.object(module, "_gh_cli_token", return_value="cli-token"), mock.patch.dict(
                    os.environ,
                    {"GITHUB_TOKEN": "", "GH_TOKEN": ""},
                    clear=False,
                ):
                    self.assertEqual(module._token(), "cli-token")

                with mock.patch.object(module, "_get", side_effect=[[], [], [], {"workflow_runs": []}]):
                    issues = module.list_issues("owner", "repo", state="closed")
                    pulls = module.list_pull_requests("owner", "repo", state="all")
                    releases = module.list_releases("owner", "repo")
                    runs = module.list_workflow_runs("owner", "repo")

                self.assertIn("No closed issues", issues)
                self.assertIn("No all pull requests", pulls)
                self.assertIn("No releases found", releases)
                self.assertEqual(runs, "No workflow runs found.")

    def test_get_repo_and_get_file_contents_fallback_paths(self) -> None:
        for module in (SOURCE_GITHUB_MODULE, MANAGED_GITHUB_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(
                    module,
                    "_get",
                    side_effect=[
                        {
                            "full_name": "owner/repo",
                            "description": "demo",
                            "default_branch": "main",
                            "stargazers_count": 1,
                            "forks_count": 2,
                            "open_issues_count": 3,
                            "license": None,
                            "visibility": "public",
                            "html_url": "https://github.com/owner/repo",
                            "pushed_at": "2026-01-01",
                        },
                        {"encoding": "base64", "content": ""},
                        {"encoding": "plain", "content": "raw text"},
                    ],
                ):
                    repo = json.loads(module.get_repo("owner", "repo"))
                    unavailable = module.get_file_contents("owner", "repo", "docs/file.txt")
                    plain = module.get_file_contents("owner", "repo", "docs/file.txt")

                self.assertEqual(repo["full_name"], "owner/repo")
                self.assertEqual(unavailable, "(content unavailable)")
                self.assertEqual(plain, "raw text")


if __name__ == "__main__":
    unittest.main()