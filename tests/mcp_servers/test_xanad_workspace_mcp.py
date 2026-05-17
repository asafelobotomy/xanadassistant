from __future__ import annotations

from contextlib import ExitStack
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_mcp_module(relative_path: str, module_name: str):
    repo_root = Path(__file__).resolve().parents[2]
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


SOURCE_MCP_MODULE = load_mcp_module("mcp/scripts/xanadWorkspaceMcp.py", "test_xanadWorkspaceMcp_source")
MANAGED_MCP_MODULE = load_mcp_module(
    ".github/mcp/scripts/xanadWorkspaceMcp.py", "test_xanadWorkspaceMcp_managed"
)


class XanadWorkspaceMcpTests(unittest.TestCase):
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

    def test_source_and_managed_modules_resolve_repo_workspace_root(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]

        self.assertEqual(SOURCE_MCP_MODULE.WORKSPACE_ROOT, repo_root)
        self.assertEqual(MANAGED_MCP_MODULE.WORKSPACE_ROOT, repo_root)

    def test_workspace_root_discovery_and_lockfile_reader_fallbacks(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir:
                    workspace = Path(tmpdir)
                    nested = workspace / "hooks" / "scripts" / "xanadWorkspaceMcp.py"
                    nested.parent.mkdir(parents=True)
                    (workspace / ".github").mkdir()
                    nested.write_text("# stub\n", encoding="utf-8")
                    self.assertEqual(module.discover_workspace_root(nested), workspace)

                fake_script = Path("/tmp/a/b/c/xanadWorkspaceMcp.py").resolve()
                expected = fake_script.parents[min(3, len(fake_script.parents) - 1)]
                self.assertEqual(module.discover_workspace_root(fake_script), expected)

                with tempfile.TemporaryDirectory() as tmpdir:
                    lockfile = Path(tmpdir) / "lock.json"
                    lockfile.write_text("{bad", encoding="utf-8")
                    with mock.patch.object(module, "WORKSPACE_LOCKFILE_PATH", lockfile):
                        self.assertIsNone(module.read_lockfile())

    def test_resolve_lifecycle_package_root_validates_strings_and_lockfile_package_root(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                package_root, reason = module.resolve_lifecycle_package_root(123)
                self.assertIsNone(package_root)
                self.assertIn("packageRoot must be a non-empty string", reason)

                with tempfile.TemporaryDirectory() as tmpdir:
                    pkg = Path(tmpdir) / "pkg"
                    pkg.mkdir()
                    with mock.patch.object(module, "read_lockfile", return_value={"package": {"packageRoot": str(pkg)}}):
                        package_root, reason = module.resolve_lifecycle_package_root(None)
                    self.assertEqual(package_root, pkg.resolve())
                    self.assertIsNone(reason)

                with mock.patch.object(module, "read_lockfile", return_value={"package": {"source": "github:owner/repo"}}):
                    package_root, reason = module.resolve_lifecycle_package_root(None, source_arg="github:owner/repo", version_arg="", ref_arg=None)
                self.assertIsNone(package_root)
                self.assertIn("version must be a non-empty string", reason)

    def test_remote_resolution_and_cli_lookup_failure_paths(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as tmpdir, mock.patch.object(
                    module,
                    "read_lockfile",
                    return_value={"package": {}},
                ), mock.patch.object(
                    module,
                    "parse_github_source",
                    return_value=("owner", "repo"),
                ), mock.patch.object(
                    module,
                    "resolve_github_ref",
                    side_effect=OSError("cache failed"),
                ):
                    package_root, reason = module.resolve_lifecycle_package_root(None, source_arg="github:owner/repo")
                self.assertIsNone(package_root)
                self.assertIn("Failed to resolve remote lifecycle source", reason)

                with tempfile.TemporaryDirectory() as tmpdir:
                    package_root = Path(tmpdir)
                    cli, reason = module.resolve_lifecycle_cli(package_root)
                self.assertIsNone(cli)
                self.assertIn("No xanadAssistant CLI entrypoint", reason)

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

    def test_run_lifecycle_command_rejects_invalid_boolean_and_answers_path(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module), mock.patch.object(
                    module,
                    "resolve_lifecycle_package_root",
                    return_value=(Path("/tmp/pkg"), None),
                ), mock.patch.object(module, "resolve_lifecycle_cli", return_value=(["python3", "xanadAssistant.py"], None)):
                    invalid_answers = module.run_lifecycle_command("plan", answers_path="/missing/answers.json")
                    invalid_bool = module.run_lifecycle_command("apply", dry_run="yes")

                self.assertEqual(invalid_answers["status"], "unavailable")
                self.assertIn("answersPath", invalid_answers["summary"])
                self.assertEqual(invalid_bool["status"], "unavailable")
                self.assertIn("dryRun", invalid_bool["summary"])

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

        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with self._workspace_ready(module), mock.patch.object(
                    module, "run_lifecycle_command", return_value=lifecycle_result
                ):
                    result = module.tool_workspace_show_install_state({})

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["installState"], "installed")
                self.assertEqual(result["drift"], "drift")

    def test_explicit_invalid_package_root_does_not_fall_back(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        missing_root = str(repo_root / "missing-package-root-do-not-create")

        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with mock.patch.object(
                    module,
                    "read_lockfile",
                    return_value={"package": {"source": "github:owner/repo", "ref": "main"}},
                ), mock.patch.object(
                    module,
                    "parse_github_source",
                    side_effect=AssertionError("should not resolve a fallback source"),
                ):
                    package_root, reason = module.resolve_lifecycle_package_root(missing_root)

                self.assertIsNone(package_root)
                self.assertIn("does not exist", reason)

    def test_run_argv_and_tool_wrappers_surface_payload_and_mode_validation(self) -> None:
        payload = {"command": "inspect", "status": "ok", "result": {"installState": "installed"}}

        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                completed = mock.Mock(returncode=0, stdout=json.dumps(payload), stderr="")
                with mock.patch.object(module.subprocess, "run", return_value=completed):
                    result = module.run_argv(["python3", "xanadAssistant.py", "inspect"], parse_payload=True)

                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["payload"]["command"], "inspect")

                with mock.patch.object(module, "run_lifecycle_command", return_value={"status": "ok", "summary": "done"}):
                    inspect_result = module.lifecycle_inspect(packageRoot="/tmp/pkg")
                    check_result = module.lifecycle_check(packageRoot="/tmp/pkg")
                    plan_result = module.lifecycle_plan_setup(packageRoot="/tmp/pkg", answersPath=None)
                    apply_result = module.lifecycle_apply(packageRoot="/tmp/pkg", dryRun=True)
                    update_result = module.lifecycle_update(packageRoot="/tmp/pkg", dryRun=False)
                    repair_result = module.lifecycle_repair(packageRoot="/tmp/pkg")
                    restore_result = module.lifecycle_factory_restore(packageRoot="/tmp/pkg")

                self.assertEqual(inspect_result.status, "ok")
                self.assertEqual(check_result.status, "ok")
                self.assertEqual(plan_result.status, "ok")
                self.assertEqual(apply_result.status, "ok")
                self.assertEqual(update_result.status, "ok")
                self.assertEqual(repair_result.status, "ok")
                self.assertEqual(restore_result.status, "ok")

                invalid_mode = module.lifecycle_interview(mode="bad")
                self.assertEqual(invalid_mode.status, "unavailable")

    def test_run_argv_json_error_and_non_dict_payload_branches(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                completed = mock.Mock(returncode=0, stdout=json.dumps({"status": "error", "command": "inspect"}), stderr="")
                with mock.patch.object(module.subprocess, "run", return_value=completed):
                    result = module.run_argv(["python3", "x.py"], parse_payload=True)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["payload"]["status"], "error")

                completed = mock.Mock(returncode=0, stdout="[]", stderr="")
                with mock.patch.object(module.subprocess, "run", return_value=completed):
                    result = module.run_argv(["python3", "x.py"], parse_payload=True)
                self.assertEqual(result["status"], "ok")
                self.assertNotIn("payload", result)

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
            instructions_path = self._write_text_file(tmpdir, "copilot-instructions.md", instructions)

            for module in self.MODULES:
                with self.subTest(module=module.__name__):
                    with self._workspace_ready(module, instructions_path=instructions_path), mock.patch.object(
                        module, "run_argv", return_value={"status": "ok", "summary": "ran"}
                    ) as run_argv:
                        tests_result = module.tool_workspace_run_tests({"scope": "default", "extraArgs": ["-k", "needle"]})
                        loc_result = module.tool_workspace_run_check_loc({})

                    self.assertEqual(tests_result["status"], "ok")
                    self.assertEqual(loc_result["status"], "ok")
                    self.assertEqual(run_argv.call_args_list[0].args[0], ["python3", "-m", "unittest", "-k", "needle"])

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

                with self._workspace_ready(module, resolve_key_command=None):
                    unavailable = module.tool_workspace_run_check_loc({})
                self.assertEqual(unavailable["status"], "unavailable")

    def test_run_argv_failure_and_install_state_without_payload(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                completed = mock.Mock(returncode=1, stdout="plain stdout\n", stderr="plain stderr\n")
                with mock.patch.object(module.subprocess, "run", return_value=completed):
                    result = module.run_argv(["python3", "x.py"], parse_payload=False)

                self.assertEqual(result["status"], "failed")
                self.assertIn("stderrTail", result)

                with self._workspace_ready(module), mock.patch.object(
                    module,
                    "run_lifecycle_command",
                    return_value={"status": "failed", "summary": "broken"},
                ):
                    passthrough = module.tool_workspace_show_install_state({})

                self.assertEqual(passthrough["status"], "failed")

    def test_lifecycle_wrappers_forward_arguments_and_unavailable_package_root(self) -> None:
        for module in self.MODULES:
            with self.subTest(module=module.__name__):
                with mock.patch.object(module, "run_lifecycle_command", return_value={"status": "ok", "summary": "ok"}) as runner:
                    module.lifecycle_interview(packageRoot="/tmp/pkg", mode="setup")
                    module.lifecycle_plan_setup(packageRoot="/tmp/pkg", answersPath="/tmp/answers.json", nonInteractive=True)
                    module.lifecycle_apply(packageRoot="/tmp/pkg", dryRun=True)
                    module.lifecycle_update(packageRoot="/tmp/pkg", dryRun=False)
                    module.lifecycle_repair(packageRoot="/tmp/pkg", nonInteractive=False)
                    module.lifecycle_factory_restore(packageRoot="/tmp/pkg", nonInteractive=True)

                self.assertEqual(runner.call_args_list[0].kwargs["mode"], "setup")
                self.assertTrue(runner.call_args_list[1].kwargs["non_interactive"])
                self.assertTrue(runner.call_args_list[2].kwargs["dry_run"])

                with self._workspace_ready(module), mock.patch.object(
                    module,
                    "resolve_lifecycle_package_root",
                    return_value=(None, "missing package root"),
                ):
                    unavailable = module.run_lifecycle_command("inspect")

                self.assertEqual(unavailable["status"], "unavailable")

                with self._workspace_ready(module), mock.patch.object(
                    module,
                    "resolve_lifecycle_package_root",
                    return_value=(Path("/tmp/pkg"), None),
                ), mock.patch.object(
                    module,
                    "resolve_lifecycle_cli",
                    return_value=(None, "cli missing"),
                ):
                    unavailable_cli = module.run_lifecycle_command("inspect")

                self.assertEqual(unavailable_cli["status"], "unavailable")
                self.assertIn("cli missing", unavailable_cli["summary"])


if __name__ == "__main__":
    unittest.main()