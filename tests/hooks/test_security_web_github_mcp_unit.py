"""Unit tests for securityMcp.py and webMcp.py hooks."""
from __future__ import annotations

import concurrent.futures
import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks" / "scripts"
REPO_ROOT = Path(__file__).resolve().parents[2]

_MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


def _load(name: str):
    """Load a hook module from HOOKS_DIR by filename stem."""
    path = HOOKS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_hyphen(filename: str):
    """Load a hook module with a hyphen in its filename."""
    path = HOOKS_DIR / filename
    mod_name = filename.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class SecurityMcpImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("securityMcp")

    def test_module_has_mcp(self):
        self.assertTrue(hasattr(self.mod, "mcp"))

    def test_headers_dict_present(self):
        self.assertIn("Content-Type", self.mod._HEADERS)

    def test_server_name(self):
        self.assertEqual("xanadSecurity", self.mod.mcp.name)


# ---------------------------------------------------------------------------
# webMcp.py  (_guard_ssrf, _ssrf_redirect_hook, _RateLimiter, _to_markdown)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class WebMcpSsrfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load("webMcp")

    def test_guard_ssrf_loopback_blocked(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._guard_ssrf("http://127.0.0.1/anything")
        self.assertIn("blocked", str(ctx.exception))

    def test_guard_ssrf_rfc1918_blocked(self):
        with self.assertRaises(ValueError):
            self.mod._guard_ssrf("http://192.168.1.1/anything")

    def test_guard_ssrf_link_local_blocked(self):
        with self.assertRaises(ValueError):
            self.mod._guard_ssrf("http://169.254.169.254/metadata")

    def test_guard_ssrf_bad_url_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._guard_ssrf("not-a-url")
        self.assertIn("Cannot parse hostname", str(ctx.exception))

    def test_guard_ssrf_unresolvable_host_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._guard_ssrf("http://this.host.does.not.exist.xyzabc123/")
        self.assertIn("Cannot resolve", str(ctx.exception))

    def test_guard_ssrf_zero_network_blocked(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._guard_ssrf("http://0.0.0.1/anything")
        self.assertIn("blocked", str(ctx.exception))

    def test_guard_ssrf_ipv6_loopback_blocked(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod._guard_ssrf("http://[::1]/")
        self.assertIn("blocked", str(ctx.exception))

    def test_guard_ssrf_ipv4_mapped_ipv6_blocked(self):
        # ::ffff:127.0.0.1 is IPv4-mapped IPv6 loopback — must be in _BLOCKED
        with patch("socket.getaddrinfo",
                   return_value=[(None, None, None, None, ("::ffff:127.0.0.1", 0, 0, 0))]):
            with self.assertRaises(ValueError) as ctx:
                self.mod._guard_ssrf("http://mapped.example.com/")
        self.assertIn("blocked", str(ctx.exception))

    def test_guard_ssrf_dns_timeout(self):
        future_mock = MagicMock()
        future_mock.result.side_effect = concurrent.futures.TimeoutError()
        ex_mock = MagicMock()
        ex_mock.submit.return_value = future_mock
        with patch("concurrent.futures.ThreadPoolExecutor", return_value=ex_mock):
            with self.assertRaises(ValueError) as ctx:
                self.mod._guard_ssrf("http://slow.example.com/")
        self.assertIn("DNS timeout", str(ctx.exception))

    def test_ssrf_redirect_hook_non_redirect_noop(self):
        resp = MagicMock()
        resp.is_redirect = False
        # Should not raise
        self.mod._ssrf_redirect_hook(resp)

    def test_ssrf_redirect_hook_blocked_redirect_raises(self):
        resp = MagicMock()
        resp.is_redirect = True
        resp.headers = {"location": "http://127.0.0.1/evil"}
        with self.assertRaises(ValueError):
            self.mod._ssrf_redirect_hook(resp)

    def test_ssrf_redirect_hook_empty_location_noop(self):
        resp = MagicMock()
        resp.is_redirect = True
        resp.headers = {"location": ""}
        # Empty location should not raise
        self.mod._ssrf_redirect_hook(resp)

    def test_ssrf_redirect_hook_relative_location_noop(self):
        # Relative redirects have no hostname — no SSRF risk, must not raise.
        resp = MagicMock()
        resp.is_redirect = True
        resp.headers = {"location": "/specification/2025-06-18/basic/transports"}
        self.mod._ssrf_redirect_hook(resp)  # Should not raise

    def test_ssrf_redirect_hook_protocol_relative_loopback_blocked(self):
        resp = MagicMock()
        resp.is_redirect = True
        resp.headers = {"location": "//127.0.0.1/evil"}
        with self.assertRaises(ValueError):
            self.mod._ssrf_redirect_hook(resp)

    def test_ssrf_redirect_hook_rfc1918_blocked(self):
        resp = MagicMock()
        resp.is_redirect = True
        resp.headers = {"location": "http://10.0.0.1/"}
        with self.assertRaises(ValueError):
            self.mod._ssrf_redirect_hook(resp)

    def test_ssrf_redirect_hook_link_local_blocked(self):
        resp = MagicMock()
        resp.is_redirect = True
        resp.headers = {"location": "http://169.254.169.254/"}
        with self.assertRaises(ValueError):
            self.mod._ssrf_redirect_hook(resp)

    def test_ssrf_redirect_hook_cgnat_blocked(self):
        resp = MagicMock()
        resp.is_redirect = True
        resp.headers = {"location": "http://100.64.0.1/"}
        with self.assertRaises(ValueError):
            self.mod._ssrf_redirect_hook(resp)

    def test_ssrf_redirect_hook_ftp_scheme_rejected(self):
        resp = MagicMock()
        resp.is_redirect = True
        resp.headers = {"location": "ftp://files.example.com/file.txt"}
        with self.assertRaises(ValueError) as ctx:
            self.mod._ssrf_redirect_hook(resp)
        self.assertIn("unsupported scheme", str(ctx.exception).lower())

    def test_rate_limiter_allows_within_limit(self):
        limiter = self.mod._RateLimiter(calls=5, period=60.0)
        for _ in range(5):
            limiter.check()  # Should not raise

    def test_rate_limiter_raises_when_exceeded(self):
        limiter = self.mod._RateLimiter(calls=2, period=60.0)
        limiter.check()
        limiter.check()
        with self.assertRaises(RuntimeError) as ctx:
            limiter.check()
        self.assertIn("Rate limit", str(ctx.exception))

    def test_to_markdown_strips_scripts(self):
        html = "<html><body><script>alert(1)</script><p>Hello</p></body></html>"
        result = self.mod._to_markdown(html)
        self.assertNotIn("alert", result)
        self.assertIn("Hello", result)

    def test_module_has_blocked_list(self):
        self.assertGreater(len(self.mod._BLOCKED), 5)


# ---------------------------------------------------------------------------
# securityMcp.py  — functional (mock-based)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class SecurityMcpFunctionalTests(unittest.TestCase):
    """Mock-based functional tests for securityMcp tools."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("securityMcp")
        sys.modules["securityMcp"] = cls.mod

    @staticmethod
    def _urlopen_mock(payload: dict) -> MagicMock:
        m = MagicMock()
        m.read.return_value = json.dumps(payload).encode()
        m.__enter__ = lambda s: s
        m.__exit__ = MagicMock(return_value=False)
        return m

    def test_query_deps_invalid_system_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.query_deps("requests", "2.28.0", "invalid_ecosystem")
        self.assertIn("Unknown ecosystem", str(ctx.exception))

    def test_query_osv_no_vulns(self):
        with patch("urllib.request.urlopen", return_value=self._urlopen_mock({"vulns": []})):
            result = self.mod.query_osv("requests", "2.28.0", "PyPI")
        self.assertIn("No known vulnerabilities", result)
        self.assertIn("PyPI/requests@2.28.0", result)

    def test_query_osv_with_vulns(self):
        vulns = [
            {"id": "GHSA-test-1234", "summary": "Prototype pollution", "severity": [], "aliases": []},
        ]
        with patch("urllib.request.urlopen", return_value=self._urlopen_mock({"vulns": vulns})):
            result = self.mod.query_osv("lodash", "4.17.0", "npm")
        self.assertIn("1 vulnerability", result)
        self.assertIn("GHSA-test-1234", result)
        self.assertIn("Prototype pollution", result)


# ---------------------------------------------------------------------------
# webMcp.py  — functional (mock-based)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_MCP_AVAILABLE, "mcp package not available — install with: pip install 'mcp[cli]'")
class WebMcpFunctionalTests(unittest.TestCase):
    """Mock-based functional tests for webMcp tools."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load("webMcp")
        sys.modules["webMcp"] = cls.mod

    def test_fetch_non_http_scheme_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.mod.fetch("ftp://example.com/file.txt")
        self.assertIn("http", str(ctx.exception).lower())

    def test_fetch_happy_path_returns_markdown(self):
        html_bytes = b"<html><body><h1>Hello</h1><p>World content</p></body></html>"
        resp_mock = MagicMock()
        resp_mock.raise_for_status = MagicMock()
        resp_mock.headers = {"content-type": "text/html; charset=utf-8"}
        resp_mock.iter_bytes.return_value = [html_bytes]

        stream_ctx = MagicMock()
        stream_ctx.__enter__ = lambda s: resp_mock
        stream_ctx.__exit__ = MagicMock(return_value=False)

        client_ctx = MagicMock()
        client_ctx.__enter__ = lambda s: s
        client_ctx.__exit__ = MagicMock(return_value=False)
        client_ctx.stream.return_value = stream_ctx

        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            with patch("httpx.Client", return_value=client_ctx):
                result = self.mod.fetch("https://example.com/")
        self.assertIn("Hello", result)
        self.assertIn("World content", result)

    def test_fetch_raw_skips_markdown_conversion(self):
        html_bytes = b"<html><body><p>Raw</p></body></html>"
        resp_mock = MagicMock()
        resp_mock.raise_for_status = MagicMock()
        resp_mock.headers = {"content-type": "text/html"}
        resp_mock.iter_bytes.return_value = [html_bytes]

        stream_ctx = MagicMock()
        stream_ctx.__enter__ = lambda s: resp_mock
        stream_ctx.__exit__ = MagicMock(return_value=False)

        client_ctx = MagicMock()
        client_ctx.__enter__ = lambda s: s
        client_ctx.__exit__ = MagicMock(return_value=False)
        client_ctx.stream.return_value = stream_ctx

        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            with patch("httpx.Client", return_value=client_ctx):
                result = self.mod.fetch("https://example.com/", raw=True)
        # Raw mode: HTML tags are preserved
        self.assertIn("<p>Raw</p>", result)

    def _make_stream_mock(self, html_bytes: bytes, content_type: str = "text/html; charset=utf-8"):
        resp_mock = MagicMock()
        resp_mock.raise_for_status = MagicMock()
        resp_mock.headers = {"content-type": content_type}
        resp_mock.iter_bytes.return_value = [html_bytes]
        stream_ctx = MagicMock()
        stream_ctx.__enter__ = lambda s: resp_mock
        stream_ctx.__exit__ = MagicMock(return_value=False)
        client_ctx = MagicMock()
        client_ctx.__enter__ = lambda s: s
        client_ctx.__exit__ = MagicMock(return_value=False)
        client_ctx.stream.return_value = stream_ctx
        return client_ctx

    def test_fetch_negative_start_index_clamped(self):
        html_bytes = b"<html><body><p>Content here</p></body></html>"
        client_ctx = self._make_stream_mock(html_bytes)
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            with patch("httpx.Client", return_value=client_ctx):
                result = self.mod.fetch("https://example.com/", start_index=-100)
        # Negative start_index must be clamped to 0 — content starts from the beginning
        self.assertIn("Content here", result)
        self.assertGreater(len(result), 0)

    def test_fetch_truncation_uses_structured_comment(self):
        long_text = "word " * 4000  # ~20 000 chars
        html_bytes = f"<html><body><p>{long_text}</p></body></html>".encode()
        client_ctx = self._make_stream_mock(html_bytes)
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            with patch("httpx.Client", return_value=client_ctx):
                result = self.mod.fetch("https://example.com/", max_length=5000)
        self.assertIn("<!-- xanad:truncation", result)
        self.assertIn("next_start_index=", result)
        self.assertNotIn("[Truncated —", result)

    def test_extract_ddg_url_unwraps_ddg_redirect(self):
        from bs4 import BeautifulSoup as _BS
        soup = _BS(
            '<div class="result">'
            '<h2 class="result__title">'
            '<a href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2F">Title</a>'
            '</h2><span class="result__url">example.com</span></div>',
            "html.parser",
        )
        el = soup.select_one(".result")
        url = self.mod._extract_ddg_url(el)
        self.assertEqual("https://example.com/", url)

    def test_extract_ddg_url_returns_direct_href(self):
        from bs4 import BeautifulSoup as _BS
        soup = _BS(
            '<div class="result">'
            '<h2 class="result__title"><a href="https://example.com/page">Title</a></h2>'
            '</div>',
            "html.parser",
        )
        el = soup.select_one(".result")
        url = self.mod._extract_ddg_url(el)
        self.assertEqual("https://example.com/page", url)

    def test_extract_ddg_url_falls_back_to_display_text(self):
        from bs4 import BeautifulSoup as _BS
        soup = _BS(
            '<div class="result"><span class="result__url">example.com</span></div>',
            "html.parser",
        )
        el = soup.select_one(".result")
        url = self.mod._extract_ddg_url(el)
        self.assertEqual("example.com", url)


# ---------------------------------------------------------------------------
# xanadWorkspaceMcp.py  (utility functions and handle_request)
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

