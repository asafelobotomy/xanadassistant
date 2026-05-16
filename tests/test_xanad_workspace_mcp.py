from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_mcp_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / relative_path
    scripts_dir = module_path.parent
    sys.path.insert(0, str(scripts_dir))
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Failed to load xanadWorkspaceMcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


SOURCE_MCP_MODULE = load_mcp_module("hooks/scripts/xanadWorkspaceMcp.py", "test_xanadWorkspaceMcp_source")
MANAGED_MCP_MODULE = load_mcp_module(
    ".github/hooks/scripts/xanadWorkspaceMcp.py", "test_xanadWorkspaceMcp_managed"
)


class XanadWorkspaceMcpTests(unittest.TestCase):
    def test_workspace_run_tests_returns_unavailable_for_placeholder_command(self) -> None:
        instructions = """## Key Commands

| Task | Command |
|---|---|
| Run tests | `(not detected)` |
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            instructions_path = Path(tmpdir) / "copilot-instructions.md"
            instructions_path.write_text(instructions, encoding="utf-8")

            for module in (SOURCE_MCP_MODULE, MANAGED_MCP_MODULE):
                with self.subTest(module=module.__name__):
                    with mock.patch.object(module, "workspace_root_valid", return_value=True), mock.patch.object(
                        module, "WORKSPACE_INSTRUCTIONS_PATH", instructions_path
                    ):
                        result = module.tool_workspace_run_tests({"scope": "default", "extraArgs": []})

                    self.assertEqual(result["status"], "unavailable")
                    self.assertIn("No Run tests command is declared", result["summary"])

    def test_workspace_show_install_state_uses_check_status_for_drift(self) -> None:
        lifecycle_result = {
            "status": "ok",
            "summary": "Lifecycle command check completed.",
            "payload": {
                "status": "drift",
                "result": {
                    "installState": "installed",
                    "summary": {"missing": 1},
                },
            },
        }

        for module in (SOURCE_MCP_MODULE, MANAGED_MCP_MODULE):
            with self.subTest(module=module.__name__):
                with mock.patch.object(module, "workspace_root_valid", return_value=True), mock.patch.object(
                    module, "run_lifecycle_command", return_value=lifecycle_result
                ):
                    result = module.tool_workspace_show_install_state({})

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["installState"], "installed")
                self.assertEqual(result["drift"], "drift")


if __name__ == "__main__":
    unittest.main()