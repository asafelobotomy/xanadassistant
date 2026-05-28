from __future__ import annotations

from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import re
import sys
from types import ModuleType
from unittest import mock


class _FakeFastMCP:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def tool(self, *decorator_args, **decorator_kwargs):
        del decorator_kwargs
        if decorator_args and callable(decorator_args[0]) and len(decorator_args) == 1:
            return decorator_args[0]

        def decorator(func):
            return func

        return decorator

    def run(self, *args, **kwargs) -> None:
        del args, kwargs


class _FakeContext:
    async def info(self, message: str) -> None:
        del message

    async def error(self, message: str) -> None:
        del message


class _FakeHttpError(Exception):
    pass


class _FakeTimeoutException(_FakeHttpError):
    pass


class _FakeRequest:
    def __init__(self, method: str, url: str) -> None:
        self.method = method
        self.url = url


class _FakeResponse:
    def __init__(self, status_code: int, url: str = "") -> None:
        self.status_code = status_code
        self.url = url


class _FakeHTTPStatusError(_FakeHttpError):
    def __init__(self, message: str, *, request: _FakeRequest | None = None, response: _FakeResponse | None = None) -> None:
        super().__init__(message)
        self.request = request
        self.response = response


class _UnexpectedHttpClientUse:
    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs

    def __enter__(self):
        raise RuntimeError("Test must patch httpx client usage explicitly.")

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False

    async def __aenter__(self):
        raise RuntimeError("Test must patch httpx client usage explicitly.")

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


class _FakeSoupNode:
    def __init__(self, tag: str | None, attrs: dict[str, str] | None = None, parent: "_FakeSoupNode | None" = None) -> None:
        self.tag = tag
        self.attrs = attrs or {}
        self.parent = parent
        self.children: list[_FakeSoupNode | str] = []

    def append_text(self, text: str) -> None:
        if text:
            self.children.append(text)

    def append_child(self, child: "_FakeSoupNode") -> None:
        self.children.append(child)

    def decompose(self) -> None:
        if self.parent is None:
            return
        self.parent.children = [child for child in self.parent.children if child is not self]

    def get(self, name: str, default=None):
        return self.attrs.get(name, default)

    def _iter_descendants(self):
        for child in self.children:
            if isinstance(child, _FakeSoupNode):
                yield child
                yield from child._iter_descendants()

    def _matches(self, part: str) -> bool:
        if part.startswith("."):
            classes = self.attrs.get("class", "").split()
            return part[1:] in classes
        return self.tag == part

    def select(self, selector: str) -> list["_FakeSoupNode"]:
        parts = [part for part in selector.split() if part]
        current = [self]
        for part in parts:
            next_nodes: list[_FakeSoupNode] = []
            for node in current:
                next_nodes.extend(candidate for candidate in node._iter_descendants() if candidate._matches(part))
            current = next_nodes
        seen: set[int] = set()
        ordered: list[_FakeSoupNode] = []
        for node in current:
            marker = id(node)
            if marker not in seen:
                seen.add(marker)
                ordered.append(node)
        return ordered

    def select_one(self, selector: str) -> "_FakeSoupNode | None":
        matches = self.select(selector)
        return matches[0] if matches else None

    def get_text(self, separator: str = "", strip: bool = False) -> str:
        parts: list[str] = []
        for child in self.children:
            if isinstance(child, _FakeSoupNode):
                text = child.get_text(separator, strip=False)
            else:
                text = child
            if text:
                parts.append(text)
        text = separator.join(parts)
        return re.sub(r"\s+", " ", text).strip() if strip else text

    def _render(self) -> str:
        if self.tag is None:
            return "".join(child._render() if isinstance(child, _FakeSoupNode) else child for child in self.children)
        attrs = "".join(f' {name}="{value}"' for name, value in self.attrs.items() if value)
        body = "".join(child._render() if isinstance(child, _FakeSoupNode) else child for child in self.children)
        return f"<{self.tag}{attrs}>{body}</{self.tag}>"


class _FakeSoupParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root = _FakeSoupNode(None)
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _FakeSoupNode(tag, {name: value or "" for name, value in attrs}, self._stack[-1])
        self._stack[-1].append_child(node)
        self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        while len(self._stack) > 1:
            node = self._stack.pop()
            if node.tag == tag:
                break

    def handle_data(self, data: str) -> None:
        self._stack[-1].append_text(data)


class _FakeBeautifulSoup(_FakeSoupNode):
    def __init__(self, html: str, parser: str) -> None:
        del parser
        parser_impl = _FakeSoupParser()
        parser_impl.feed(html)
        self.tag = None
        self.attrs = {}
        self.parent = None
        self.children = parser_impl.root.children

    def __call__(self, tag_names: list[str]) -> list[_FakeSoupNode]:
        allowed = set(tag_names)
        return [node for node in self._iter_descendants() if node.tag in allowed]

    def __str__(self) -> str:
        return self._render()


def _fake_markdownify(html: str, heading_style: str = "ATX") -> str:
    del heading_style
    soup = _FakeBeautifulSoup(html, "html.parser")
    blocks: list[str] = []
    heading_tags = {f"h{level}": "#" * level for level in range(1, 7)}

    def visit(node: _FakeSoupNode) -> None:
        if node.tag in heading_tags:
            text = node.get_text(" ", strip=True)
            if text:
                blocks.append(f"{heading_tags[node.tag]} {text}")
            return
        if node.tag in {"p", "div", "li", "pre", "code"}:
            text = node.get_text(" ", strip=True)
            if text:
                blocks.append(text)
            return
        for child in node.children:
            if isinstance(child, _FakeSoupNode):
                visit(child)

    visit(soup)
    return "\n\n".join(blocks).strip()


class _FakeBaseModel:
    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def model_validate(cls, payload: dict):
        return cls(**payload)


def _fake_config_dict(**kwargs):
    return dict(kwargs)


def load_mcp_script_module(relative_path: str, module_name: str, failure_label: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    fake_mcp = ModuleType("mcp")
    fake_server = ModuleType("mcp.server")
    fake_fastmcp = ModuleType("mcp.server.fastmcp")
    fake_fastmcp.FastMCP = _FakeFastMCP
    fake_fastmcp.Context = _FakeContext
    fake_mcp.server = fake_server
    fake_server.fastmcp = fake_fastmcp
    fake_httpx = ModuleType("httpx")
    fake_httpx.HTTPError = _FakeHttpError
    fake_httpx.TimeoutException = _FakeTimeoutException
    fake_httpx.HTTPStatusError = _FakeHTTPStatusError
    fake_httpx.Request = _FakeRequest
    fake_httpx.Response = _FakeResponse
    fake_httpx.AsyncClient = _UnexpectedHttpClientUse
    fake_httpx.Client = _UnexpectedHttpClientUse
    fake_bs4 = ModuleType("bs4")
    fake_bs4.BeautifulSoup = _FakeBeautifulSoup
    fake_markdownify = ModuleType("markdownify")
    fake_markdownify.markdownify = _fake_markdownify
    fake_pydantic = ModuleType("pydantic")
    fake_pydantic.BaseModel = _FakeBaseModel
    fake_pydantic.ConfigDict = _fake_config_dict
    sys.path.insert(0, str(scripts_dir))
    try:
        with mock.patch.dict(
            sys.modules,
            {
                "mcp": fake_mcp,
                "mcp.server": fake_server,
                "mcp.server.fastmcp": fake_fastmcp,
                "httpx": fake_httpx,
                "bs4": fake_bs4,
                "markdownify": fake_markdownify,
                "pydantic": fake_pydantic,
            },
            clear=False,
        ):
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Failed to load {failure_label}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    finally:
        sys.path.pop(0)


def load_mcp_script_pair(script_name: str, module_prefix: str, failure_label: str | None = None):
    """Load both source and managed copies of an MCP script.

    Returns ``(source_module, managed_module)``.  *module_prefix* is used as the
    base for the per-copy module names (e.g. ``"test_myMcp"`` yields
    ``"test_myMcp_source"`` and ``"test_myMcp_managed"``).
    """
    label = failure_label or script_name
    source = load_mcp_script_module(
        f"mcp/scripts/{script_name}",
        f"{module_prefix}_source",
        label,
    )
    managed = load_mcp_script_module(
        f".github/mcp/scripts/{script_name}",
        f"{module_prefix}_managed",
        label,
    )
    return source, managed