from __future__ import annotations

import importlib.util
from pathlib import Path
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


def load_mcp_script_module(relative_path: str, module_name: str, failure_label: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    fake_mcp = ModuleType("mcp")
    fake_server = ModuleType("mcp.server")
    fake_fastmcp = ModuleType("mcp.server.fastmcp")
    fake_fastmcp.FastMCP = _FakeFastMCP
    fake_mcp.server = fake_server
    fake_server.fastmcp = fake_fastmcp
    sys.path.insert(0, str(scripts_dir))
    try:
        with mock.patch.dict(
            sys.modules,
            {
                "mcp": fake_mcp,
                "mcp.server": fake_server,
                "mcp.server.fastmcp": fake_fastmcp,
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