from __future__ import annotations

import importlib.util
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock


def load_web_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load webMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SOURCE_WEB_MODULE = load_web_module("hooks/scripts/webMcp.py", "test_webMcp_source")
MANAGED_WEB_MODULE = load_web_module(".github/hooks/scripts/webMcp.py", "test_webMcp_managed")


class _FakeResponse:
    def __init__(self, location: str) -> None:
        self.is_redirect = True
        self.headers = {"location": location}


class WebMcpTests(unittest.TestCase):
    def test_guard_ssrf_rejects_reserved_ipv4_targets(self) -> None:
        reserved_results = [
            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.51.100.10", 0))],
            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 0))],
        ]

        for addrinfo in reserved_results:
            for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
                with self.subTest(module=module.__name__, addr=addrinfo[0][4][0]):
                    with mock.patch.object(module.socket, "getaddrinfo", return_value=addrinfo):
                        with self.assertRaisesRegex(ValueError, "not a public routable address"):
                            module._guard_ssrf("https://example.test/resource")

    def test_guard_ssrf_rejects_reserved_ipv6_targets(self) -> None:
        addrinfo = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fe80::1", 0, 0, 0))]

        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(module.socket, "getaddrinfo", return_value=addrinfo):
                    with self.assertRaisesRegex(ValueError, "not a public routable address"):
                        module._guard_ssrf("https://example.test/resource")

    def test_redirect_hook_rejects_redirects_to_reserved_targets(self) -> None:
        redirect_response = _FakeResponse("https://redirect.test/private")
        addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.55", 0))]

        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(module.socket, "getaddrinfo", return_value=addrinfo):
                    with self.assertRaisesRegex(ValueError, "not a public routable address"):
                        module._ssrf_redirect_hook(redirect_response)


if __name__ == "__main__":
    unittest.main()