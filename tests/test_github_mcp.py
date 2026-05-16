from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


def load_github_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[1]
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


SOURCE_GITHUB_MODULE = load_github_module("hooks/scripts/githubMcp.py", "test_githubMcp_source")
MANAGED_GITHUB_MODULE = load_github_module(".github/hooks/scripts/githubMcp.py", "test_githubMcp_managed")


class GitHubMcpTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()