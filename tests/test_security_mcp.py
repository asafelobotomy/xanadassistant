from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_security_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "hooks" / "scripts" / "securityMcp.py"
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location("test_securityMcp", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load securityMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SECURITY_MODULE = load_security_module()


class SecurityMcpTests(unittest.TestCase):
    def test_query_deps_rejects_unknown_ecosystem(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown ecosystem"):
            SECURITY_MODULE.query_deps("requests", "2.0.0", "apk")


if __name__ == "__main__":
    unittest.main()