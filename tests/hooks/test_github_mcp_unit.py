"""Unit tests for githubMcp.py hook."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import urllib.error
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks" / "scripts"

_MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


def _load(name: str):
    """Load a hook module from HOOKS_DIR by filename stem."""
    path = HOOKS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# githubMcp.py  (_token() — env var and gh CLI fallback)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class GitHubMcpTokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("githubMcp")

    def test_module_has_mcp(self):
        self.assertTrue(hasattr(self.mod, "mcp"))

    def test_token_missing_raises(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=False):
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("GH_TOKEN", None)
            with patch.object(self.mod, "_gh_cli_token", return_value=""):
                with self.assertRaises(RuntimeError) as ctx:
                    self.mod._token()
        self.assertIn("GITHUB_TOKEN", str(ctx.exception))

    def test_token_whitespace_only_raises(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "   ", "GH_TOKEN": ""}, clear=False):
            os.environ.pop("GH_TOKEN", None)
            with patch.object(self.mod, "_gh_cli_token", return_value=""):
                with self.assertRaises(RuntimeError):
                    self.mod._token()

    def test_token_returns_stripped(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "  mytoken  "}):
            result = self.mod._token()
        self.assertEqual("mytoken", result)

    def test_token_gh_token_fallback(self):
        """GH_TOKEN is used when GITHUB_TOKEN is absent."""
        with patch.dict(os.environ, {"GH_TOKEN": "  ghtoken  "}, clear=False):
            os.environ.pop("GITHUB_TOKEN", None)
            result = self.mod._token()
        self.assertEqual("ghtoken", result)

    def test_token_github_token_takes_precedence(self):
        """GITHUB_TOKEN is preferred over GH_TOKEN when both are set."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "primary", "GH_TOKEN": "fallback"}):
            result = self.mod._token()
        self.assertEqual("primary", result)

    def test_token_gh_cli_fallback(self):
        """_gh_cli_token() result is used when no env var is set."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=False):
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("GH_TOKEN", None)
            with patch.object(self.mod, "_gh_cli_token", return_value="cli-token"):
                result = self.mod._token()
        self.assertEqual("cli-token", result)

    def test_api_base_url(self):
        self.assertEqual("https://api.github.com", self.mod._API)


# ---------------------------------------------------------------------------
# githubMcp.py  — _gh_cli_token (subprocess)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class GitHubMcpGhCliTokenTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("githubMcp")

    def test_success_returns_stripped_token(self):
        mock_res = MagicMock(returncode=0, stdout="  token123\n")
        with patch("subprocess.run", return_value=mock_res):
            self.assertEqual("token123", self.mod._gh_cli_token())

    def test_nonzero_exit_returns_empty(self):
        mock_res = MagicMock(returncode=1, stdout="")
        with patch("subprocess.run", return_value=mock_res):
            self.assertEqual("", self.mod._gh_cli_token())

    def test_gh_not_installed_returns_empty(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual("", self.mod._gh_cli_token())

    def test_timeout_returns_empty(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["gh"], 5)):
            self.assertEqual("", self.mod._gh_cli_token())


# ---------------------------------------------------------------------------
# githubMcp.py  — functional (mock-based)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class GitHubMcpFunctionalTests(unittest.TestCase):
    """Mock-based functional tests for githubMcp tools."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("githubMcp")
        sys.modules["githubMcp"] = cls.mod

    # --- _validate_owner_repo ---

    def test_validate_owner_repo_valid(self):
        # Must not raise for well-formed names.
        self.mod._validate_owner_repo("octocat", "hello-world")

    def test_validate_owner_repo_invalid_owner(self):
        with self.assertRaises(ValueError):
            self.mod._validate_owner_repo("bad owner!", "repo")

    def test_validate_owner_repo_invalid_repo(self):
        with self.assertRaises(ValueError):
            self.mod._validate_owner_repo("owner", "bad/repo")

    # --- get_file_contents path-traversal guard ---

    def test_get_file_contents_dotdot_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.get_file_contents("owner", "repo", "../evil.txt")
        self.assertIn("..", str(ctx.exception))

    # --- get_repo happy path ---

    @staticmethod
    def _urlopen_mock(payload: dict) -> MagicMock:
        m = MagicMock()
        m.read.return_value = json.dumps(payload).encode()
        m.__enter__ = lambda s: s
        m.__exit__ = MagicMock(return_value=False)
        return m

    def test_get_repo_happy_path(self):
        payload = {
            "full_name": "owner/repo",
            "description": "Test",
            "default_branch": "main",
            "stargazers_count": 7,
            "forks_count": 1,
            "open_issues_count": 0,
            "license": None,
            "visibility": "public",
            "html_url": "https://github.com/owner/repo",
            "pushed_at": "2024-01-01T00:00:00Z",
        }
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-tok"}):
            with patch("urllib.request.urlopen", return_value=self._urlopen_mock(payload)):
                result = self.mod.get_repo("owner", "repo")
        data = json.loads(result)
        self.assertEqual("owner/repo", data["full_name"])
        self.assertEqual("public", data["visibility"])

    # --- list_issues happy path ---

    def test_list_issues_happy_path(self):
        issues = [
            {
                "number": 42, "title": "Bug report", "state": "open",
                "html_url": "https://github.com/owner/repo/issues/42",
                "user": {"login": "alice"},
                "labels": [{"name": "bug"}],
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-tok"}):
            with patch("urllib.request.urlopen", return_value=self._urlopen_mock(issues)):
                result = self.mod.list_issues("owner", "repo")
        self.assertIn("Bug report", result)
        self.assertIn("#42", result)

    def test_get_pull_request_happy_path(self):
        payload = {
            "number": 7,
            "title": "Improve diagnostics",
            "state": "open",
            "body": "Adds better messages.",
            "html_url": "https://github.com/owner/repo/pull/7",
            "draft": False,
            "head": {"ref": "feature"},
            "base": {"ref": "main"},
            "user": {"login": "alice"},
            "mergeable": True,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
        }
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-tok"}):
            with patch("urllib.request.urlopen", return_value=self._urlopen_mock(payload)):
                result = self.mod.get_pull_request("owner", "repo", 7)
        data = json.loads(result)
        self.assertEqual(7, data["number"])
        self.assertEqual("Improve diagnostics", data["title"])

    def test_create_pull_request_happy_path(self):
        payload = {
            "number": 8,
            "html_url": "https://github.com/owner/repo/pull/8",
        }
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-tok"}):
            with patch("urllib.request.urlopen", return_value=self._urlopen_mock(payload)):
                result = self.mod.create_pull_request(
                    "owner",
                    "repo",
                    "Add fix",
                    "feature",
                    "main",
                    body="Details",
                )
        self.assertIn("#8", result)
        self.assertIn(payload["html_url"], result)

    def test_list_workflow_runs_happy_path(self):
        payload = {
            "workflow_runs": [
                {
                    "id": 101,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "head_branch": "main",
                    "created_at": "2024-01-01T00:00:00Z",
                    "html_url": "https://github.com/owner/repo/actions/runs/101",
                }
            ]
        }
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-tok"}):
            with patch("urllib.request.urlopen", return_value=self._urlopen_mock(payload)):
                result = self.mod.list_workflow_runs("owner", "repo", workflow_id="ci.yml")
        self.assertIn("CI", result)
        self.assertIn("success", result)

    def test_validate_workflow_id_accepts_github_workflow_path(self):
        result = self.mod._validate_workflow_id(".github/workflows/pr.yml")
        self.assertEqual("pr.yml", result)

    def test_list_workflow_runs_accepts_github_workflow_path(self):
        captured = {}

        def _fake_urlopen(req, timeout=30):
            captured["url"] = req.full_url
            return self._urlopen_mock({"workflow_runs": []})

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-tok"}):
            with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
                result = self.mod.list_workflow_runs(
                    "owner",
                    "repo",
                    workflow_id=".github/workflows/pr.yml",
                    per_page=5,
                )
        self.assertEqual("No workflow runs found.", result)
        self.assertIn("/repos/owner/repo/actions/workflows/pr.yml/runs", captured["url"])

    def test_req_non_json_response_raises_runtimeerror(self):
        response = MagicMock()
        response.read.return_value = b"<html>not json</html>"
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-tok"}):
            with patch("urllib.request.urlopen", return_value=response):
                with self.assertRaises(RuntimeError) as ctx:
                    self.mod._req("GET", "/repos/owner/repo")
        self.assertIn("non-JSON", str(ctx.exception))

    def test_normalize_per_page_clamps_lower_and_upper_bounds(self):
        self.assertEqual(1, self.mod._normalize_per_page(0, 30))
        self.assertEqual(30, self.mod._normalize_per_page(100, 30))

    def test_validate_state_invalid_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._validate_state("merged")
        self.assertIn("Invalid state", str(ctx.exception))

    def test_validate_workflow_id_invalid_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._validate_workflow_id("../../releases")
        self.assertIn("workflow_id", str(ctx.exception))

    def test_get_file_contents_url_encodes_path(self):
        captured = {}

        def _fake_urlopen(req, timeout=30):
            captured["url"] = req.full_url
            return self._urlopen_mock({"encoding": "base64", "content": "aGVsbG8="})

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-tok"}):
            with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
                result = self.mod.get_file_contents("owner", "repo", "docs/My File.md")
        self.assertEqual("hello", result)
        self.assertIn("docs/My%20File.md", captured["url"])

    def test_get_file_contents_missing_base64_content_returns_placeholder(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-tok"}):
            with patch(
                "urllib.request.urlopen",
                return_value=self._urlopen_mock({"encoding": "base64"}),
            ):
                result = self.mod.get_file_contents("owner", "repo", "README.md")
        self.assertIn("content unavailable", result.lower())

    def test_get_pull_request_not_found_includes_issue_hint(self):
        err = urllib.error.HTTPError(
            url="https://api.github.com/repos/owner/repo/pulls/7",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(
                b'{"message":"Not Found","documentation_url":"https://docs.github.com/rest/pulls/pulls#get-a-pull-request","status":"404"}'
            ),
        )
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-tok"}):
            with patch("urllib.request.urlopen", side_effect=err):
                with self.assertRaises(RuntimeError) as ctx:
                    self.mod.get_pull_request("owner", "repo", 7)
        self.assertIn("get_issue", str(ctx.exception))

    def test_list_pull_requests_invalid_state_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.list_pull_requests("owner", "repo", state="merged")
        self.assertIn("Invalid state", str(ctx.exception))

    def test_list_workflow_runs_invalid_workflow_id_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.list_workflow_runs("owner", "repo", workflow_id="../../runs")
        self.assertIn("workflow_id", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
