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
                for tool_name in ("testing_show_key_commands", "testing_show_capabilities", "testing_list_tests", "testing_run_tests", "testing_parse_coverage"):
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
                    self.assertEqual(module.detect_test_runner(["uv", "run", "pytest", "-q"]), "pytest")
                    self.assertEqual(module.detect_test_runner(["poetry", "run", "python3", "-m", "unittest"]), "unittest")
                    self.assertEqual(module.detect_test_runner(["pnpm", "exec", "pytest", "-q"]), "pytest")
                    self.assertEqual(module.detect_test_runner(["yarn", "exec", "pytest", "-q"]), "pytest")
                    self.assertEqual(module.detect_test_runner(["npm", "exec", "--", "pytest", "-q"]), "pytest")
                    self.assertEqual(module.detect_test_runner(["npx", "pytest", "-q"]), "pytest")
                    self.assertEqual(module.parse_discovered_test_ids("tests/test_a.py::test_one\nwarning: noisy output\ntests/test_a.py::Suite::test_two\n", "pytest"), ["tests/test_a.py::test_one", "tests/test_a.py::Suite::test_two"])
                    self.assertEqual(module.parse_test_summary("Ran 2 tests in 0.1s\n\nOK")["passed"], 2)
                    skipped_summary = module.parse_test_summary("Ran 3 tests in 0.1s\n\nOK (skipped=1)")
                    self.assertEqual(skipped_summary["passed"], 2)
                    self.assertEqual(skipped_summary["total"], 3)
                    self.assertEqual(module.parse_test_summary("FAILED tests/test_a.py::test_x - AssertionError: no\n1 failed, 2 passed")["failed"], 1)

    def test_run_tests_argument_validation_and_full_scope_rules(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module):
                    invalid_args = module.tool_testing_run_tests({"scope": "default", "extraArgs": "--bad"})
                    invalid_targets = module.tool_testing_run_tests({"scope": "default", "targetFiles": "tests/test_a.py"})
                    invalid_scope = module.tool_testing_run_tests({"scope": "bogus", "extraArgs": []})
                    full_scope = module.tool_testing_run_tests({"scope": "full", "extraArgs": ["-k", "needle"]})

                self.assertEqual(invalid_args["status"], "unavailable")
                self.assertEqual(invalid_targets["status"], "unavailable")
                self.assertEqual(invalid_scope["status"], "unavailable")
                self.assertIn("scope must be one of", invalid_scope["summary"])
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

    def test_run_tests_rejects_typed_targets_for_opaque_runners(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, resolve_key_command="npm test"):
                    result = module.tool_testing_run_tests({"scope": "default", "targetFiles": ["tests/test_a.py"], "testNames": ["test_one"]})

                self.assertEqual(result["status"], "unavailable")
                self.assertIn("does not support typed targetFiles or testNames", result["summary"])

    def test_run_tests_rejects_typed_targets_for_unittest_discover(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, resolve_key_command="python3 -m unittest discover -s tests -p 'test_*.py'"):
                    result = module.tool_testing_run_tests({"scope": "default", "targetFiles": ["tests/test_a.py"], "testNames": ["tests.test_a.TestCase.test_one"]})

                self.assertEqual(result["status"], "unavailable")
                self.assertIn("does not support typed targetFiles or testNames", result["summary"])

    def test_run_tests_allows_typed_targets_for_supported_wrappers(self) -> None:
        cases = [("pnpm exec pytest -q", ["pnpm", "exec", "pytest", "-q", "tests/test_a.py", "tests/test_a.py::test_one"]), ("npm exec -- pytest -q", ["npm", "exec", "--", "pytest", "-q", "tests/test_a.py", "tests/test_a.py::test_one"]), ("npx pytest -q", ["npx", "pytest", "-q", "tests/test_a.py", "tests/test_a.py::test_one"])]
        for module in self.MODULES:
            for command, expected_argv in cases:
                with self.subTest(module=module.__name__, command=command):
                    with self._workspace_ready(module, resolve_key_command=command), mock.patch.object(
                        module, "run_argv", return_value={"status": "ok", "summary": "ran"}
                    ) as run_argv:
                        result = module.tool_testing_run_tests(
                            {"scope": "default", "targetFiles": ["tests/test_a.py"], "testNames": ["tests/test_a.py::test_one"]}
                        )

                    self.assertEqual(result["status"], "ok")
                    self.assertEqual(run_argv.call_args.args[0], expected_argv)

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

    def test_run_argv_reports_timeout_as_failed(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                timeout_seconds = getattr(module, "RUN_TIMEOUT_SECONDS", 300)
                with mock.patch.object(module.subprocess, "run", side_effect=module.subprocess.TimeoutExpired(cmd=["python3"], timeout=timeout_seconds, output="partial out", stderr="partial err")):
                    result = module.run_argv(["python3", "-m", "unittest"])

                self.assertEqual(result["status"], "failed")
                self.assertIn("timed out", result["summary"])
                self.assertEqual(result["stdoutTail"], "partial out")
                self.assertEqual(result["stderrTail"], "partial err")
                self.assertEqual(result["runnerExitReason"], "timeout")

    def test_run_argv_classifies_runner_exit_reasons(self) -> None:
        cases = [
            (["pytest", "-q"], 5, "no tests ran in 0.01s\n", "", "no_tests_collected"),
            (["pytest", "-q"], 4, "", "ERROR: usage\n", "usage_error"),
            (["python3", "-m", "unittest"], 1, "Ran 2 tests in 0.1s\n\nFAILED (failures=1)\n", "", "tests_failed"),
        ]
        for module in self.MODULES:
            for argv, returncode, stdout, stderr, expected_reason in cases:
                with self.subTest(module=module.__name__, argv=argv, reason=expected_reason):
                    completed = module.subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)
                    with mock.patch.object(module.subprocess, "run", return_value=completed):
                        result = module.run_argv(argv)

                    self.assertEqual(result["status"], "failed")
                    self.assertEqual(result["runnerExitReason"], expected_reason)
                    self.assertEqual(result["exitCode"], returncode)

    def test_testing_show_capabilities_reports_runtime_and_command_facts(self) -> None:
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
                    with self._workspace_ready(module, instructions_path=instructions_path), mock.patch.object(module, "WORKSPACE_ROOT", workspace):
                        capabilities = module.tool_testing_show_capabilities({})

                    self.assertEqual(capabilities["status"], "ok")
                    self.assertEqual(capabilities["detectedRunner"], "unittest")
                    self.assertTrue(capabilities["runTestsCommandAvailable"])
                    self.assertTrue(capabilities["venvPythonAvailable"])
                    self.assertEqual(capabilities["timeoutSeconds"], 300)
                    self.assertEqual(capabilities["supportedScopes"], ["default", "full"])
                    self.assertEqual(capabilities["supportedCoverageFormats"], ["cobertura_xml"])
                    self.assertEqual(capabilities["parsedOutputFormats"], ["pytest", "unittest"])
                    self.assertTrue(capabilities["supportsTypedTargets"])
                    self.assertEqual(capabilities["typedTargetingMode"], "argv_append")
                    self.assertFalse(capabilities["supportsTestDiscovery"])

    def test_testing_show_capabilities_does_not_overclaim_unittest_discover(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, resolve_key_command="python3 -m unittest discover -s tests -p 'test_*.py'"):
                    capabilities = module.tool_testing_show_capabilities({})

                self.assertEqual(capabilities["status"], "ok")
                self.assertEqual(capabilities["detectedRunner"], "unittest")
                self.assertFalse(capabilities["supportsTypedTargets"])
                self.assertEqual(capabilities["typedTargetingMode"], "none")
                self.assertFalse(capabilities["supportsTestDiscovery"])

    def test_testing_show_capabilities_reports_pytest_discovery_support(self) -> None:
        commands = ["pytest -q", "python3 -m pytest -q", "uv run pytest -q", "poetry run pytest -q", "pnpm exec pytest -q", "yarn exec pytest -q", "npm exec -- pytest -q", "npx pytest -q"]
        for module in self.MODULES:
            for command in commands:
                with self.subTest(module=module.__name__, command=command):
                    with self._workspace_ready(module, resolve_key_command=command):
                        capabilities = module.tool_testing_show_capabilities({})

                    self.assertEqual(capabilities["status"], "ok")
                    self.assertEqual(capabilities["detectedRunner"], "pytest")
                    self.assertTrue(capabilities["supportsTypedTargets"])
                    self.assertTrue(capabilities["supportsTestDiscovery"])

    def test_testing_show_capabilities_does_not_overclaim_opaque_wrappers(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, resolve_key_command="npm test"):
                    capabilities = module.tool_testing_show_capabilities({})

                self.assertEqual(capabilities["status"], "ok")
                self.assertEqual(capabilities["detectedRunner"], "unknown")
                self.assertFalse(capabilities["supportsTypedTargets"])
                self.assertEqual(capabilities["typedTargetingMode"], "none")
                self.assertFalse(capabilities["supportsTestDiscovery"])

    def test_testing_tools_reject_invalid_declared_commands(self) -> None:
        cases = [("bash scripts/run_tests.sh", "allowlist", (("tool_testing_show_capabilities", {}),)), ('python3 -m unittest "', "parsed", (("tool_testing_show_capabilities", {}), ("tool_testing_list_tests", {}), ("tool_testing_run_tests", {"scope": "default", "extraArgs": []})))]
        for module in self.MODULES:
            for command, expected_summary, invocations in cases:
                with self.subTest(module=module.__name__, command=command):
                    with self._workspace_ready(module, resolve_key_command=command):
                        results = [getattr(module, tool_name)(arguments) for tool_name, arguments in invocations]
                    for result in results:
                        self.assertEqual(result["status"], "unavailable")
                        self.assertIn(expected_summary, result["summary"])

    def test_testing_list_tests_rejects_unsupported_runner_and_invalid_targets(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, resolve_key_command="python3 -m unittest"):
                    unsupported = module.tool_testing_list_tests({})
                with self._workspace_ready(module, resolve_key_command="pytest -q"):
                    invalid_targets = module.tool_testing_list_tests({"targetFiles": "tests/test_a.py"})

                self.assertEqual(unsupported["status"], "unavailable")
                self.assertIn("does not support safe test discovery", unsupported["summary"])
                self.assertEqual(invalid_targets["status"], "unavailable")
                self.assertIn("targetFiles must be a string array", invalid_targets["summary"])

    def test_testing_list_tests_uses_pytest_collect_only_and_parses_test_ids(self) -> None:
        cases = [("pytest -q", ["pytest", "-q", "--collect-only", "-q", "--no-header", "tests/test_a.py"]), ("python3 -m pytest -q", None), ("pnpm exec pytest -q", ["pnpm", "exec", "pytest", "-q", "--collect-only", "-q", "--no-header", "tests/test_a.py"]), ("npm exec -- pytest -q", ["npm", "exec", "--", "pytest", "-q", "--collect-only", "-q", "--no-header", "tests/test_a.py"])]
        for module in self.MODULES:
            for command, expected_argv in cases:
                with self.subTest(module=module.__name__, command=command):
                    with self._workspace_ready(module, resolve_key_command=command), mock.patch.object(
                        module,
                        "run_argv",
                        return_value={
                            "status": "ok",
                            "summary": "Command completed successfully.",
                            "stdoutTail": "tests/test_a.py::test_one\n",
                            "_stdoutFull": "tests/test_a.py::test_one\ntests/test_a.py::TestSuite::test_two\n",
                            "stderrTail": "warning: tail noise\n",
                            "_stderrFull": "warning: collection note\n",
                        },
                    ) as run_argv:
                        result = module.tool_testing_list_tests({"targetFiles": ["tests/test_a.py"]})

                    self.assertEqual(result["status"], "ok")
                    self.assertEqual(result["testIds"], ["tests/test_a.py::test_one", "tests/test_a.py::TestSuite::test_two"])
                    self.assertEqual(result["total"], 2)
                    if expected_argv is None:
                        expected_python = str(module.WORKSPACE_ROOT / ".venv" / "bin" / "python")
                        expected_argv = [expected_python, "-m", "pytest", "-q", "--collect-only", "-q", "--no-header", "tests/test_a.py"]
                    self.assertEqual(run_argv.call_args.args[0], expected_argv)

    def test_testing_run_tests_parses_summary_from_full_mixed_output(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module, resolve_key_command="pytest -q"), mock.patch.object(
                    module,
                    "run_argv",
                    return_value={
                        "status": "failed",
                        "summary": "Command failed: tests_failed.",
                        "exitCode": 1,
                        "runnerExitReason": "tests_failed",
                        "stdoutTail": "truncated\n",
                        "stderrTail": "tail warning\n",
                        "_stdoutFull": "FAILED tests/test_a.py::test_one - AssertionError: boom\n",
                        "_stderrFull": "1 failed, 2 passed\n",
                    },
                ):
                    result = module.tool_testing_run_tests({"scope": "default", "parseOutput": True})

                self.assertEqual(result["testSummary"]["format"], "pytest")
                self.assertEqual(result["testSummary"]["failed"], 1)
                self.assertEqual(result["testSummary"]["passed"], 2)
                self.assertEqual(result["testSummary"]["firstFailure"], "tests/test_a.py::test_one: AssertionError: boom")

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

    def test_testing_parse_coverage_handles_missing_and_malformed_files(self) -> None:
        malformed = "<coverage><broken></coverage>"
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            malformed_path = workspace / "broken.xml"
            malformed_path.write_text(malformed, encoding="utf-8")
            for module in self.MODULES:
                with self.subTest(module=module.__name__):
                    with self._workspace_ready(module), mock.patch.object(module, "WORKSPACE_ROOT", workspace):
                        missing = module.tool_testing_parse_coverage({"coveragePath": "missing.xml"})
                        broken = module.tool_testing_parse_coverage({"coveragePath": "broken.xml"})

                    self.assertEqual(missing["status"], "unavailable")
                    self.assertIn("existing file", missing["summary"])
                    self.assertEqual(broken["status"], "failed")
                    self.assertIn("Cannot parse coverage XML", broken["summary"])


if __name__ == "__main__":
    unittest.main()
