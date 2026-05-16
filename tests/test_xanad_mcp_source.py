from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def load_source_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "hooks" / "scripts" / "_xanad_mcp_source.py"
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("test_xanad_mcp_source", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load _xanad_mcp_source.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SOURCE_MODULE = load_source_module()


class XanadMcpSourceTests(unittest.TestCase):
    def test_parse_github_source_rejects_invalid_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported source scheme"):
            SOURCE_MODULE.parse_github_source("gitlab:owner/repo")

    def test_resolve_github_ref_rejects_invalid_ref_before_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "invalid characters"):
                SOURCE_MODULE.resolve_github_ref("owner", "repo", "bad ref^", Path(tmpdir))


if __name__ == "__main__":
    unittest.main()