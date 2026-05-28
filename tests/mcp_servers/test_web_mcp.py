from __future__ import annotations

import socket
import unittest
from ipaddress import ip_address
from unittest import mock

from tests.mcp_servers._mcp_module_loader import load_mcp_script_pair

SOURCE_WEB_MODULE, MANAGED_WEB_MODULE = load_mcp_script_pair("webMcp.py", "test_webMcp")


class _FakeResponse:
    def __init__(self, location: str) -> None:
        self.is_redirect = True
        self.headers = {"location": location}


class _FakeHttpResponse:
    def __init__(self, *, text: str = "", headers: dict[str, str] | None = None, chunks: list[bytes] | None = None, status_code: int = 200) -> None:
        self.text = text
        self.headers = headers or {}
        self._chunks = chunks or []
        self.is_redirect = False
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise SOURCE_WEB_MODULE.httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=SOURCE_WEB_MODULE.httpx.Request("GET", "https://example.com"),
                response=SOURCE_WEB_MODULE.httpx.Response(self.status_code),
            )
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
    def __init__(self, *, post_response: _FakeHttpResponse | None = None, stream_response: _FakeHttpResponse | list[_FakeHttpResponse] | Exception | list[_FakeHttpResponse | Exception] | None = None, get_response: _FakeHttpResponse | None = None, **kwargs) -> None:
        del kwargs
        self._post_response = post_response
        self._stream_response = stream_response
        self._get_response = get_response
        self.stream_calls = 0
        self.get_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False

    def post(self, url: str, data: dict[str, str]):
        del url, data
        return self._post_response

    def get(self, url: str):
        del url
        self.get_calls += 1
        return self._get_response

    def stream(self, method: str, url: str):
        del method, url
        self.stream_calls += 1
        if isinstance(self._stream_response, list):
            response = self._stream_response.pop(0)
        else:
            response = self._stream_response
        if isinstance(response, Exception):
            raise response
        return response


class WebMcpTests(unittest.TestCase):
    def test_fetch_respects_robots_txt_disallow_rules(self) -> None:
        robots_text = "User-agent: *\nDisallow: /private\n"
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                client = _FakeHttpClient(
                    get_response=_FakeHttpResponse(text=robots_text, headers={"content-type": "text/plain"}),
                    stream_response=_FakeHttpResponse(headers={"content-type": "text/plain"}, chunks=[b"ignored"]),
                )
                with mock.patch.object(module, "_guard_ssrf", return_value=None), mock.patch.object(module, "_ROBOTS_CACHE", {}, create=True), mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=client,
                ):
                    content = module.fetch("https://example.com/private/page")

                self.assertIn("Fetch disallowed by robots.txt.", content)
                self.assertIn("https://example.com/robots.txt", content)
                self.assertEqual(client.stream_calls, 0)

    def test_fetch_classifies_challenge_pages_instead_of_returning_html(self) -> None:
        challenge_html = "<html><title>Attention Required!</title><body>Verify you are human</body></html>"
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                client = _FakeHttpClient(
                    get_response=_FakeHttpResponse(status_code=404),
                    stream_response=_FakeHttpResponse(
                        text=challenge_html,
                        headers={"content-type": "text/html", "server": "cloudflare", "cf-ray": "abc"},
                        chunks=[challenge_html.encode("utf-8")],
                        status_code=403,
                    ),
                )
                with mock.patch.object(module, "_guard_ssrf", return_value=None), mock.patch.object(module, "_ROBOTS_CACHE", {}, create=True), mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=client,
                ):
                    content = module.fetch("https://example.com/protected")

                self.assertIn("Fetch blocked by remote site.", content)
                self.assertIn("Category: blocked_by_waf", content)
                self.assertIn("HTTP status: 403", content)

    def test_fetch_retries_transient_failures_before_succeeding(self) -> None:
        html_bytes = [b"<html><body><p>Recovered</p></body></html>"]
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                client = _FakeHttpClient(
                    get_response=_FakeHttpResponse(status_code=404),
                    stream_response=[
                        _FakeHttpResponse(headers={"content-type": "text/html"}, status_code=503, chunks=[b"busy"]),
                        _FakeHttpResponse(headers={"content-type": "text/html; charset=utf-8"}, chunks=html_bytes),
                    ],
                )
                with mock.patch.object(module, "_guard_ssrf", return_value=None), mock.patch.object(module, "_ROBOTS_CACHE", {}, create=True), mock.patch.object(
                    module,
                    "_to_markdown",
                    return_value="Recovered markdown",
                ), mock.patch.object(module, "_sleep_before_retry", return_value=None, create=True) as sleep_mock, mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=client,
                ):
                    content = module.fetch("https://example.com/retry", max_length=40)

                self.assertEqual(content, "Recovered markdown")
                sleep_mock.assert_called_once_with(1)
                self.assertEqual(client.stream_calls, 2)

    def test_fetch_binary_responses_return_metadata_summary(self) -> None:
        binary_bytes = [b"\x89PNG\r\n\x1a\n", b"rest"]
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(module, "_guard_ssrf", return_value=None), mock.patch.object(
                    module,
                    "_ROBOTS_CACHE",
                    {},
                    create=True,
                ), mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(
                        get_response=_FakeHttpResponse(status_code=404),
                        stream_response=_FakeHttpResponse(
                            headers={"content-type": "image/png"},
                            chunks=binary_bytes,
                        )
                    ),
                ):
                    content = module.fetch("https://example.com/image.png")

                self.assertEqual(
                    content,
                    "Non-text content fetched; returning metadata only.\n"
                    "URL: https://example.com/image.png\n"
                    "Content-Type: image/png\n"
                    "Downloaded bytes: 12",
                )

    def test_search_result_formatting_collapses_whitespace_and_omits_empty_snippets(self) -> None:
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                formatted = module._format_search_result(2, "  Example\n Title  ", "https://example.com", "  ")
                self.assertEqual(formatted, "2. Example Title\n   https://example.com")
                with_snippet = module._format_search_result(3, "Example", "https://example.com/docs", "  one\n two  ")
                self.assertEqual(with_snippet, "3. Example\n   https://example.com/docs\n   one two")

    def test_textual_content_type_helper_distinguishes_binary_and_text_payloads(self) -> None:
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                self.assertTrue(module._is_textual_content_type("text/plain; charset=utf-8"))
                self.assertTrue(module._is_textual_content_type("application/json"))
                self.assertFalse(module._is_textual_content_type("image/png"))
                self.assertFalse(module._is_textual_content_type("application/pdf"))

    def test_fetch_url_normalization_accepts_bare_domains_and_scheme_relative_urls(self) -> None:
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                self.assertEqual(module._normalize_fetch_url("example.com/docs"), "https://example.com/docs")
                self.assertEqual(module._normalize_fetch_url("//example.com/docs"), "https://example.com/docs")
                with self.assertRaisesRegex(ValueError, "must not be empty"):
                    module._normalize_fetch_url("   ")

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

    def test_web_search_omits_blank_snippet_lines_and_normalizes_whitespace(self) -> None:
        html = """
        <div class=\"result\">
          <div class=\"result__title\"><a href=\"https://example.com/a\">Example\n          A</a></div>
          <div class=\"result__snippet\">   </div>
        </div>
        """
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(module, "_limiter") as limiter_mock, mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(post_response=_FakeHttpResponse(text=html)),
                ):
                    result = module.web_search("needle", max_results=1)

                limiter_mock.check.assert_called_once_with()
                self.assertIn("1. Example A\n   https://example.com/a", result)
                self.assertNotIn("\n   \n", result)

    def test_fetch_supports_markdown_raw_and_truncation_paths(self) -> None:
        html_bytes = [b"<html><body><h1>Title</h1><p>Paragraph</p></body></html>"]
        raw_bytes = [b"abcdefghi"]
        for module in (SOURCE_WEB_MODULE, MANAGED_WEB_MODULE):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(ValueError, "Only http and https"):
                    module.fetch("file:///tmp/test")

                with mock.patch.object(module, "_guard_ssrf", return_value=None), mock.patch.object(
                    module,
                    "_ROBOTS_CACHE",
                    {},
                    create=True,
                ), mock.patch.object(
                    module,
                    "_to_markdown",
                    return_value="Converted markdown body",
                ), mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(
                        get_response=_FakeHttpResponse(status_code=404),
                        stream_response=_FakeHttpResponse(
                            headers={"content-type": "text/html; charset=utf-8"},
                            chunks=html_bytes,
                        )
                    ),
                ):
                    converted = module.fetch("https://example.com/page", max_length=10)

                self.assertIn("Converted ", converted)
                self.assertIn("Continue with start_index=10 to read the next 13 character(s).", converted)
                self.assertIn("next_start_index=10", converted)

                with mock.patch.object(module, "_guard_ssrf", return_value=None) as guard_mock, mock.patch.object(
                    module,
                    "_ROBOTS_CACHE",
                    {},
                    create=True,
                ), mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(
                        get_response=_FakeHttpResponse(status_code=404),
                        stream_response=_FakeHttpResponse(
                            headers={"content-type": "text/plain; charset=utf-8"},
                            chunks=raw_bytes,
                        )
                    ),
                ):
                    bare = module.fetch("example.com/raw", max_length=4, raw=True)

                guard_mock.assert_called_once_with("https://example.com/raw")
                self.assertEqual(
                    bare,
                    "abcd\n\nContinue with start_index=4 to read the next 5 character(s).\n<!-- xanad:truncation remaining=5 next_start_index=4 -->",
                )

                with mock.patch.object(module, "_guard_ssrf", return_value=None), mock.patch.object(
                    module,
                    "_ROBOTS_CACHE",
                    {},
                    create=True,
                ), mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(
                        get_response=_FakeHttpResponse(status_code=404),
                        stream_response=_FakeHttpResponse(
                            headers={"content-type": "text/plain; charset=utf-8"},
                            chunks=raw_bytes,
                        )
                    ),
                ):
                    raw = module.fetch("https://example.com/raw", max_length=4, start_index=2, raw=True)

                self.assertEqual(
                    raw,
                    "cdef\n\nContinue with start_index=6 to read the next 3 character(s).\n<!-- xanad:truncation remaining=3 next_start_index=6 -->",
                )

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
                    "_ROBOTS_CACHE",
                    {},
                    create=True,
                ), mock.patch.object(
                    module,
                    "_to_markdown",
                    return_value="Doc markdown",
                ), mock.patch.object(
                    module.httpx,
                    "Client",
                    return_value=_FakeHttpClient(
                        get_response=_FakeHttpResponse(status_code=404),
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