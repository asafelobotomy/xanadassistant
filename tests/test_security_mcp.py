from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


def load_security_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load securityMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SOURCE_SECURITY_MODULE = load_security_module("hooks/scripts/securityMcp.py", "test_securityMcp_source")
MANAGED_SECURITY_MODULE = load_security_module(".github/hooks/scripts/securityMcp.py", "test_securityMcp_managed")


class SecurityMcpTests(unittest.TestCase):
    def test_query_deps_rejects_unknown_ecosystem(self) -> None:
        for module in (SOURCE_SECURITY_MODULE, MANAGED_SECURITY_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "Unknown ecosystem"):
                    module.query_deps("requests", "2.0.0", "apk")

    def test_query_deps_normalizes_system_for_url_and_summary(self) -> None:
        for module in (SOURCE_SECURITY_MODULE, MANAGED_SECURITY_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(module, "_get", return_value={"vulnerabilityCount": 0}) as get_mock:
                    summary = module.query_deps("requests", "2.0.0", "PyPI")

                self.assertEqual(
                    get_mock.call_args.args[0],
                    "https://api.deps.dev/v3alpha/systems/pypi/packages/requests/versions/2.0.0",
                )
                self.assertIn("deps.dev report for pypi/requests@2.0.0:", summary)


if __name__ == "__main__":
    unittest.main()