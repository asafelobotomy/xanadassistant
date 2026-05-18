from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.mcp_servers._xanad_workspace_mcp_support import XanadWorkspaceMcpTestCaseMixin


class XanadWorkspaceMcpToolTests(XanadWorkspaceMcpTestCaseMixin, unittest.TestCase):
    def test_exported_mcp_tools_have_descriptions(self) -> None:
        tool_names = [
            "workspace_show_key_commands",
            "workspace_run_tests",
            "workspace_run_check_loc",
            "workspace_validate_lockfile",
            "workspace_show_install_state",
            "lifecycle_inspect",
            "lifecycle_check",
            "lifecycle_interview",
            "lifecycle_plan_setup",
            "lifecycle_setup",
            "lifecycle_apply",
            "lifecycle_update",
            "lifecycle_repair",
            "lifecycle_factory_restore",
        ]

        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                for tool_name in tool_names:
                    with self.subTest(tool=tool_name):
                        doc = getattr(module, tool_name).__doc__
                        self.assertIsNotNone(doc)
                        self.assertTrue(doc.strip())

    def test_workspace_run_tests_returns_unavailable_for_placeholder_command(self) -> None:
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
                        result = module.tool_workspace_run_tests({"scope": "default", "extraArgs": []})

                    self.assertEqual(result["status"], "unavailable")
                    self.assertIn("No Run tests command is declared", result["summary"])

    def test_key_command_parsing_and_shell_guard_helpers(self) -> None:
        instructions = """## Key Commands

| Task | Command |
|---|---|
| Run tests | `python3 -m unittest` |
| LOC gate | `python3 scripts/check_loc.py` |
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
                    self.assertEqual(module.tail_text("a\nb\nc", max_lines=2), "b\nc")
                    self.assertEqual(module.build_tool_result(status="ok", summary="done", stdout="a\nb", stderr="")["stdoutTail"], "a\nb")

    def test_validate_lockfile_and_run_tests_argument_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            lockfile = workspace / ".github" / "xanadAssistant-lock.json"
            lockfile.parent.mkdir(parents=True)
            lockfile.write_text('{"schemaVersion":1,"package":{},"manifest":{},"timestamps":{},"files":[]}', encoding="utf-8")

            for module in self.MODULES:
                with self.subTest(module=module.__name__):
                    with self._workspace_ready(module, lockfile_path=lockfile):
                        result = module.tool_workspace_validate_lockfile({})

                    self.assertEqual(result["status"], "ok")

                    with self._workspace_ready(module):
                        invalid = module.tool_workspace_run_tests({"scope": "default", "extraArgs": "--bad"})

                    self.assertEqual(invalid["status"], "unavailable")

    def test_show_key_commands_and_run_tests_full_scope_rules(self) -> None:
        instructions = """## Key Commands

| Task | Command |
|---|---|
| Run tests | `python3 -m unittest` |
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            instructions_path = self._write_text_file(tmpdir, "copilot-instructions.md", instructions)

            for module in self.MODULES:
                with self.subTest(module=module.__name__):
                    with self._workspace_ready(module, instructions_path=instructions_path):
                        shown = module.tool_workspace_show_key_commands({})
                        full_scope = module.tool_workspace_run_tests({"scope": "full", "extraArgs": ["-k", "needle"]})

                    self.assertEqual(shown["status"], "ok")
                    self.assertEqual(shown["commands"][0]["label"], "Run tests")
                    self.assertEqual(full_scope["status"], "unavailable")
                    self.assertIn("scope=full", full_scope["summary"])

    def test_lockfile_and_key_command_unavailable_paths(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, lockfile_path=Path("/tmp/definitely-missing-lockfile.json")):
                    missing_lock = module.tool_workspace_validate_lockfile({})

                self.assertEqual(missing_lock["status"], "unavailable")

                with mock.patch.object(module, "workspace_root_valid", return_value=False):
                    unavailable = module.tool_workspace_show_key_commands({})

                self.assertEqual(unavailable["status"], "unavailable")

    def test_run_tests_and_check_loc_cover_shell_guard_and_execution_paths(self) -> None:
        instructions = """## Key Commands

| Task | Command |
|---|---|
| Run tests | `python3 -m unittest` |
| LOC gate | `python3 scripts/check_loc.py` |
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            instructions_path = self._write_text_file(tmpdir, "copilot-instructions.md", instructions)

            for module in self.MODULES:
                with self.subTest(module=module.__name__):
                    with self._workspace_ready(module, instructions_path=instructions_path), mock.patch.object(
                        module, "WORKSPACE_ROOT", workspace
                    ), mock.patch.object(
                        module, "run_argv", return_value={"status": "ok", "summary": "ran"}
                    ) as run_argv:
                        tests_result = module.tool_workspace_run_tests({"scope": "default", "extraArgs": ["-k", "needle"]})
                        loc_result = module.tool_workspace_run_check_loc({})

                    self.assertEqual(tests_result["status"], "ok")
                    self.assertEqual(loc_result["status"], "ok")
                    self.assertEqual(run_argv.call_args_list[0].args[0], ["python3", "-m", "unittest", "-k", "needle"])

    def test_check_loc_falls_back_to_default_command_when_missing_from_instructions(self) -> None:
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
                    ), mock.patch.object(
                        module, "run_argv", return_value={"status": "ok", "summary": "ran"}
                    ) as run_argv:
                        result = module.tool_workspace_run_check_loc({})

                    self.assertEqual(result["status"], "ok")
                    self.assertEqual(run_argv.call_args.args[0], ["python3", "scripts/check_loc.py"])

    def test_python_commands_prefer_workspace_venv_when_available(self) -> None:
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
                        result = module.tool_workspace_run_tests({"scope": "default", "extraArgs": []})

                    self.assertEqual(result["status"], "ok")
                    self.assertEqual(run_argv.call_args.args[0], [str(venv_python), "-m", "unittest"])

                with self.subTest(module=f"{module.__name__}-shell-guard"):
                    bad_instructions = self._write_text_file(
                        tmpdir,
                        f"bad-{module.__name__}.md",
                        "## Key Commands\n\n| Task | Command |\n|---|---|\n| Run tests | `python3 -m unittest | cat` |\n",
                    )
                    with self._workspace_ready(module, instructions_path=bad_instructions):
                        guarded = module.tool_workspace_run_tests({"scope": "default", "extraArgs": []})
                    self.assertEqual(guarded["status"], "unavailable")

    def test_validate_lockfile_missing_keys_and_check_loc_unavailable(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, read_lockfile={"schemaVersion": 1}):
                    failed = module.tool_workspace_validate_lockfile({})
                self.assertEqual(failed["status"], "failed")
                self.assertIn("missing required keys", failed["summary"])

                with self._workspace_ready(module, resolve_key_command=None), mock.patch.object(module, "DEFAULT_KEY_COMMANDS", {}, create=True):
                    unavailable = module.tool_workspace_run_check_loc({})
                self.assertEqual(unavailable["status"], "unavailable")

    def test_run_tests_and_check_loc_reject_non_allowlisted_executables(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, resolve_key_command="bash scripts/run_tests.sh"):
                    tests_result = module.tool_workspace_run_tests({"scope": "default", "extraArgs": []})
                self.assertEqual(tests_result["status"], "unavailable")
                self.assertIn("allowlist", tests_result["summary"])

                with self._workspace_ready(module, resolve_key_command="curl http://example.com/script.sh"):
                    loc_result = module.tool_workspace_run_check_loc({})
                self.assertEqual(loc_result["status"], "unavailable")
                self.assertIn("allowlist", loc_result["summary"])

    def test_check_loc_also_guards_shell_metacharacters(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, resolve_key_command="python3 scripts/check_loc.py | cat"):
                    result = module.tool_workspace_run_check_loc({})
                self.assertEqual(result["status"], "unavailable")
                self.assertIn("unsupported shell syntax", result["summary"])


if __name__ == "__main__":
    unittest.main()