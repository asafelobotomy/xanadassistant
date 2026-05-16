from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_git_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "hooks" / "scripts" / "gitMcp.py"
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("test_gitMcp", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load gitMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


GIT_MODULE = load_git_module()


class GitMcpTests(unittest.TestCase):
    def test_git_checkout_rejects_flag_like_branch_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "looks like a flag"):
            GIT_MODULE.git_checkout("/tmp", "-b")


if __name__ == "__main__":
    unittest.main()