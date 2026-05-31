from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.mcp_servers._workspace_testing_mcp_support import WorkspaceTestingMcpTestCaseMixin


class WorkspaceTestingMcpTests(WorkspaceTestingMcpTestCaseMixin, unittest.TestCase):
    def test_exported_mcp_tools_have_descriptions(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                for tool_name in ("testing_show_key_commands", "testing_run_tests", "testing_parse_coverage"):
                    with self.subTest(tool=tool_name):
                        doc = getattr(module, tool_name).__doc__
                        self.assertIsNotNone(doc)
                        self.assertTrue(doc.strip())

    def test_testing_run_tests_returns_unavailable_for_placeholder_command(self) -> None:
        instructions = """## Key Commands

| Task | Command |
|---|---|
| Run tests | `(not detected)` |
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instructions_path = self._write_text_file(tmpdir, "copilot-instructions.md", instructions)
            for module in self.MODULES:
                with self.subTest(module=module.__name__):
                    with self._workspace_ready(module, instructions_path=instructions_path):
                        result = module.tool_testing_run_tests({"scope": "default", "extraArgs": []})
                    self.assertEqual(result["status"], "unavailable")
                    self.assertIn("No Run tests command is declared", result["summary"])

    def test_key_command_parsing_and_test_summary_helpers(self) -> None:
        instructions = """## Key Commands

| Task | Command |
|---|---|
| Run tests | `python3 -m unittest` |
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instructions_path = self._write_text_file(tmpdir, "copilot-instructions.md", instructions)
            for module in self.MODULES:
                with self.subTest(module=module.__name__):
                    commands = module.parse_key_commands(instructions_path)
                    self.assertEqual(commands[0]["label"], "Run tests")
                    self.assertEqual(module.resolve_key_command("missing"), None)
                    self.assertTrue(module.is_unresolved_command("(not detected)"))
                    self.assertIsNone(module.reject_shell_metacharacters("python3 -m unittest"))
                    self.assertIn("unsupported shell syntax", module.reject_shell_metacharacters("echo hi | cat"))
                    self.assertEqual(module.parse_test_summary("Ran 2 tests in 0.1s\n\nOK")["passed"], 2)
                    self.assertEqual(module.parse_test_summary("FAILED tests/test_a.py::test_x - AssertionError: no\n1 failed, 2 passed")["failed"], 1)

    def test_run_tests_argument_validation_and_full_scope_rules(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module):
                    invalid_args = module.tool_testing_run_tests({"scope": "default", "extraArgs": "--bad"})
                    invalid_targets = module.tool_testing_run_tests({"scope": "default", "targetFiles": "tests/test_a.py"})
                    full_scope = module.tool_testing_run_tests({"scope": "full", "extraArgs": ["-k", "needle"]})

                self.assertEqual(invalid_args["status"], "unavailable")
                self.assertEqual(invalid_targets["status"], "unavailable")
                self.assertEqual(full_scope["status"], "unavailable")
                self.assertIn("scope=full", full_scope["summary"])

    def test_show_key_commands_and_run_tests_execution_paths(self) -> None:
        instructions = """## Key Commands

| Task | Command |
|---|---|
| Run tests | `python3 -m unittest` |
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            instructions_path = self._write_text_file(tmpdir, "copilot-instructions.md", instructions)
            for module in self.MODULES:
                with self.subTest(module=module.__name__):
                    with self._workspace_ready(module, instructions_path=instructions_path), mock.patch.object(
                        module, "WORKSPACE_ROOT", workspace
                    ), mock.patch.object(module, "run_argv", return_value={"status": "ok", "summary": "ran"}) as run_argv:
                        shown = module.tool_testing_show_key_commands({})
                        tests_result = module.tool_testing_run_tests({"scope": "default", "extraArgs": ["-k", "needle"], "targetFiles": ["tests/test_a.py"], "testNames": ["TestClass.test_one"]})

                    self.assertEqual(shown["status"], "ok")
                    self.assertEqual(tests_result["status"], "ok")
                    self.assertEqual(run_argv.call_args.args[0], ["python3", "-m", "unittest", "-k", "needle", "tests/test_a.py", "TestClass.test_one"])

    def test_python_commands_prefer_workspace_venv_and_reject_shell_syntax(self) -> None:
        instructions = """## Key Commands

| Task | Command |
|---|---|
| Run tests | `python3 -m unittest` |
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            instructions_path = self._write_text_file(tmpdir, "copilot-instructions.md", instructions)
            venv_python = workspace / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True)
            venv_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            for module in self.MODULES:
                with self.subTest(module=module.__name__):
                    with self._workspace_ready(module, instructions_path=instructions_path), mock.patch.object(
                        module, "WORKSPACE_ROOT", workspace
                    ), mock.patch.object(module, "run_argv", return_value={"status": "ok", "summary": "ran"}) as run_argv:
                        result = module.tool_testing_run_tests({"scope": "default", "extraArgs": []})
                    self.assertEqual(result["status"], "ok")
                    self.assertEqual(run_argv.call_args.args[0], [str(venv_python), "-m", "unittest"])

                with self.subTest(module=f"{module.__name__}-shell-guard"):
                    bad_instructions = self._write_text_file(
                        tmpdir,
                        f"bad-{module.__name__}.md",
                        "## Key Commands\n\n| Task | Command |\n|---|---|\n| Run tests | `python3 -m unittest | cat` |\n",
                    )
                    with self._workspace_ready(module, instructions_path=bad_instructions):
                        guarded = module.tool_testing_run_tests({"scope": "default", "extraArgs": []})
                    self.assertEqual(guarded["status"], "unavailable")

    def test_run_tests_rejects_non_allowlisted_executables(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, resolve_key_command="bash scripts/run_tests.sh"):
                    result = module.tool_testing_run_tests({"scope": "default", "extraArgs": []})
                self.assertEqual(result["status"], "unavailable")
                self.assertIn("allowlist", result["summary"])

    def test_testing_parse_coverage_returns_structured_summary(self) -> None:
        coverage = """<?xml version="1.0" ?>
<coverage line-rate="0.75" lines-valid="4" lines-covered="3">
  <packages><package><classes>
    <class filename="covered.py" line-rate="1" />
    <class filename="missing.py" line-rate="0" />
  </classes></package></packages>
</coverage>
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            coverage_path = workspace / "coverage.xml"
            coverage_path.write_text(coverage, encoding="utf-8")
            outside_path = Path(tmpdir).parent / f"outside-{workspace.name}.xml"
            outside_path.write_text(coverage, encoding="utf-8")
            try:
                for module in self.MODULES:
                    with self.subTest(module=module.__name__):
                        with self._workspace_ready(module), mock.patch.object(module, "WORKSPACE_ROOT", workspace):
                            parsed = module.tool_testing_parse_coverage({"coveragePath": "coverage.xml"})
                            rejected = module.tool_testing_parse_coverage({"coveragePath": str(outside_path)})
                        self.assertEqual(parsed["status"], "ok")
                        self.assertEqual(parsed["percentCovered"], 75.0)
                        self.assertEqual(parsed["zeroCoverageFiles"], ["missing.py"])
                        self.assertEqual(rejected["status"], "unavailable")
            finally:
                outside_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
