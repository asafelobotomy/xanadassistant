from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from tests.mcp_servers._mcp_module_loader import load_mcp_script_module


def load_mcp_module(relative_path: str, module_name: str):
    return load_mcp_script_module(relative_path, module_name, "xanadWorkspaceMcp.py")


SOURCE_MCP_MODULE = load_mcp_module("mcp/scripts/xanadWorkspaceMcp.py", "test_xanadWorkspaceMcp_source")
MANAGED_MCP_MODULE = load_mcp_module(
    ".github/mcp/scripts/xanadWorkspaceMcp.py", "test_xanadWorkspaceMcp_managed"
)


class XanadWorkspaceMcpTestCaseMixin:
    MODULES = (SOURCE_MCP_MODULE, MANAGED_MCP_MODULE)
    _UNSET = object()

    def _write_text_file(self, tmpdir: str, name: str, contents: str) -> Path:
        path = Path(tmpdir) / name
        path.write_text(contents, encoding="utf-8")
        return path

    def _workspace_ready(
        self,
        module,
        *,
        instructions_path: Path | object = _UNSET,
        lockfile_path: Path | object = _UNSET,
        read_lockfile: object = _UNSET,
        resolve_key_command: object = _UNSET,
    ) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(mock.patch.object(module, "workspace_root_valid", return_value=True))
        if instructions_path is not self._UNSET:
            stack.enter_context(mock.patch.object(module, "WORKSPACE_INSTRUCTIONS_PATH", instructions_path))
        if lockfile_path is not self._UNSET:
            stack.enter_context(mock.patch.object(module, "WORKSPACE_LOCKFILE_PATH", lockfile_path))
        if read_lockfile is not self._UNSET:
            stack.enter_context(mock.patch.object(module, "read_lockfile", return_value=read_lockfile))
        if resolve_key_command is not self._UNSET:
            stack.enter_context(mock.patch.object(module, "resolve_key_command", return_value=resolve_key_command))
        return stack