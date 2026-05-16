from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_git_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[1]
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


SOURCE_GIT_MODULE = load_git_module("hooks/scripts/gitMcp.py", "test_gitMcp_source")
MANAGED_GIT_MODULE = load_git_module(".github/hooks/scripts/gitMcp.py", "test_gitMcp_managed")


class GitMcpTests(unittest.TestCase):
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