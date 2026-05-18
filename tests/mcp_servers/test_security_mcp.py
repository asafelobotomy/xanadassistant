from __future__ import annotations

import unittest
from unittest import mock

from tests.mcp_servers._mcp_module_loader import load_mcp_script_module

SOURCE_SECURITY_MODULE = load_mcp_script_module("mcp/scripts/securityMcp.py", "test_securityMcp_source", "securityMcp.py")
MANAGED_SECURITY_MODULE = load_mcp_script_module(".github/mcp/scripts/securityMcp.py", "test_securityMcp_managed", "securityMcp.py")


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