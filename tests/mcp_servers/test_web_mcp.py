from __future__ import annotations

import importlib.util
import socket
import sys
import unittest
from ipaddress import ip_address
from pathlib import Path
from unittest import mock


def load_web_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
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


SOURCE_WEB_MODULE = load_web_module("mcp/scripts/webMcp.py", "test_webMcp_source")
MANAGED_WEB_MODULE = load_web_module(".github/mcp/scripts/webMcp.py", "test_webMcp_managed")


class _FakeResponse:
    def __init__(self, location: str) -> None:
        self.is_redirect = True
        self.headers = {"location": location}


class _FakeHttpResponse:
    def __init__(self, *, text: str = "", headers: dict[str, str] | None = None, chunks: list[bytes] | None = None) -> None:
        self.text = text
        self.headers = headers or {}
        self._chunks = chunks or []
        self.is_redirect = False

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self, chunk_size: int = 65536):
        del chunk_size
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


class _FakeHttpClient:
    def __init__(self, *, post_response: _FakeHttpResponse | None = None, stream_response: _FakeHttpResponse | None = None, **kwargs) -> None:
        del kwargs
        self._post_response = post_response
        self._stream_response = stream_response

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False

    def post(self, url: str, data: dict[str, str]):
        del url, data
        return self._post_response

    def stream(self, method: str, url: str):
        del method, url
        return self._stream_response


class WebMcpTests(unittest.TestCase):
    def test_helper_branches_cover_url_unwrap_and_redirect_rules(self) -> None:
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                self.assertEqual(module._normalize_ip(ip_address("::ffff:192.0.2.1")), ip_address("192.0.2.1"))
                self.assertFalse(module._is_public_address(ip_address("192.0.2.10")))

                result_el = mock.Mock()
                anchor = mock.Mock()
                anchor.get.return_value = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage"
                fallback = mock.Mock()
                fallback.get_text.return_value = "example.com"
                result_el.select_one.side_effect = lambda selector: anchor if selector == ".result__title a" else fallback
                self.assertEqual(module._extract_ddg_url(result_el), "https://example.com/page")

                relative = _FakeResponse("/docs")
                module._ssrf_redirect_hook(relative)
                with self.assertRaisesRegex(ValueError, "unsupported scheme"):
                    module._ssrf_redirect_hook(_FakeResponse("ftp://example.com/file"))

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

    def test_web_search_formats_results_and_validates_empty_query(self) -> None:
        html = """
        <div class=\"result\">
          <div class=\"result__title\"><a href=\"https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa\">Example A</a></div>
          <div class=\"result__snippet\">Snippet A</div>
        </div>
        <div class=\"result\">
          <div class=\"result__title\"><a href=\"https://example.com/b\">Example B</a></div>
          <div class=\"result__snippet\">Snippet B</div>
        </div>
        """
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "must not be empty"):
                    module.web_search("   ")
                with mock.patch.object(module, "_limiter") as limiter_mock, mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(post_response=_FakeHttpResponse(text=html)),
                ):
                    result = module.web_search("needle", max_results=2, region="us-en")

                limiter_mock.check.assert_called_once_with()
                self.assertIn("Found 2 result(s)", result)
                self.assertIn("https://example.com/a", result)
                self.assertIn("Snippet B", result)

    def test_fetch_supports_markdown_raw_and_truncation_paths(self) -> None:
        html_bytes = [b"<html><body><h1>Title</h1><p>Paragraph</p></body></html>"]
        raw_bytes = [b"abcdefghi"]
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "Only http and https"):
                    module.fetch("file:///tmp/test")

                with mock.patch.object(module, "_guard_ssrf", return_value=None), mock.patch.object(
                    module,
                    "_to_markdown",
                    return_value="Converted markdown body",
                ), mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(
                        stream_response=_FakeHttpResponse(
                            headers={"content-type": "text/html; charset=utf-8"},
                            chunks=html_bytes,
                        )
                    ),
                ):
                    converted = module.fetch("https://example.com/page", max_length=10)

                self.assertIn("Converted ", converted)
                self.assertIn("next_start_index=10", converted)

                with mock.patch.object(module, "_guard_ssrf", return_value=None), mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(
                        stream_response=_FakeHttpResponse(
                            headers={"content-type": "text/plain; charset=utf-8"},
                            chunks=raw_bytes,
                        )
                    ),
                ):
                    raw = module.fetch("https://example.com/raw", max_length=4, start_index=2, raw=True)

                self.assertEqual(raw, "cdef\n<!-- xanad:truncation remaining=3 next_start_index=6 -->")

    def test_dns_and_rate_limit_helper_branches(self) -> None:
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                future = mock.Mock()
                future.result.side_effect = module.concurrent.futures.TimeoutError()
                executor = mock.Mock()
                executor.submit.return_value = future
                with mock.patch.object(module.concurrent.futures, "ThreadPoolExecutor", return_value=executor):
                    with self.assertRaisesRegex(ValueError, "DNS timeout"):
                        module._guard_ssrf("https://example.test")

                future = mock.Mock()
                future.result.side_effect = socket.gaierror("no host")
                executor = mock.Mock()
                executor.submit.return_value = future
                with mock.patch.object(module.concurrent.futures, "ThreadPoolExecutor", return_value=executor):
                    with self.assertRaisesRegex(ValueError, "Cannot resolve hostname"):
                        module._guard_ssrf("https://example.test")

                limiter = module._RateLimiter(calls=1, period=60.0)
                limiter.check()
                with self.assertRaisesRegex(RuntimeError, "Rate limit reached"):
                    limiter.check()

    def test_to_markdown_no_results_and_fetch_html_detection_fallbacks(self) -> None:
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                markdown = module._to_markdown("<html><body><nav>skip</nav><h1>Title</h1><script>x</script></body></html>")
                self.assertIn("# Title", markdown)
                self.assertNotIn("skip", markdown)

                empty_html = "<html><body><div>No match</div></body></html>"
                with mock.patch.object(module, "_limiter") as limiter_mock, mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(post_response=_FakeHttpResponse(text=empty_html)),
                ):
                    no_results = module.web_search("none", max_results=3)
                limiter_mock.check.assert_called_once_with()
                self.assertIn("No results found", no_results)

                with mock.patch.object(module, "_guard_ssrf", return_value=None), mock.patch.object(
                    module,
                    "_to_markdown",
                    return_value="Doc markdown",
                ), mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(
                        stream_response=_FakeHttpResponse(
                            headers={"content-type": "text/plain"},
                            chunks=[b"<!DOCTYPE html><html><body>Doc</body></html>"],
                        )
                    ),
                ):
                    content = module.fetch("https://example.com/doc", max_length=50)

                self.assertEqual(content, "Doc markdown")


if __name__ == "__main__":
    unittest.main()