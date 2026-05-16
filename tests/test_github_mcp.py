from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


def load_github_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "hooks" / "scripts" / "githubMcp.py"
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("test_githubMcp", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load githubMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


GITHUB_MODULE = load_github_module()


class GitHubMcpTests(unittest.TestCase):
    def test_token_raises_clear_error_when_no_auth_is_available(self) -> None:
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "", "GH_TOKEN": ""}, clear=False), mock.patch.object(
            GITHUB_MODULE, "_gh_cli_token", return_value=""
        ):
            with self.assertRaisesRegex(RuntimeError, "No GitHub token found"):
                GITHUB_MODULE._token()

    def test_format_http_error_adds_pull_request_404_hint(self) -> None:
        message = GITHUB_MODULE._format_http_error("/repos/o/r/pulls/123", 404, "not found")

        self.assertIn("use get_issue instead", message)


if __name__ == "__main__":
    unittest.main()