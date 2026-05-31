#!/usr/bin/env python3
from __future__ import annotations
import shlex
import subprocess
import sys
from pathlib import Path
from pydantic import BaseModel, ConfigDict
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent))
from _workspace_testing_shared import parse_coverage_xml_file, parse_test_summary
from mcp.server.fastmcp import FastMCP
WORKSPACE_ROOT_UNAVAILABLE = "The MCP server is not installed in a workspace root."
SHELL_METACHARACTERS = ["|", "&", ";", ">", "<", "\n", "\r", "`", "$((", "$(", "${"]
UNRESOLVED_COMMAND_VALUES = frozenset({"(not detected)", "not detected"})
_ALLOWED_RUNNER_EXECUTABLES = frozenset({
    "python", "python3", "pytest", "py.test",
    "npm", "npx", "yarn", "pnpm", "cargo", "go",
})


def discover_workspace_root(script_path: Path) -> Path:
    resolved = script_path.resolve()
    for candidate in resolved.parents:
        if (candidate / ".github").is_dir():
            return candidate
    fallback_index = min(3, len(resolved.parents) - 1)
    return resolved.parents[fallback_index]


WORKSPACE_ROOT = discover_workspace_root(Path(__file__))
WORKSPACE_INSTRUCTIONS_PATH = WORKSPACE_ROOT / ".github" / "copilot-instructions.md"


def workspace_root_valid() -> bool: return (WORKSPACE_ROOT / ".github").is_dir()
def _check_executable_allowed(command: str) -> str | None:
    try:
        argv = shlex.split(command)
    except ValueError:
        return "command could not be parsed"
    if not argv:
        return "command is empty"
    executable = Path(argv[0]).name
    if executable in _ALLOWED_RUNNER_EXECUTABLES:
        return None
    prefix, _, suffix = executable.partition(".")
    if prefix in {"python", "python3"} and suffix.isdigit():
        return None
    return f"executable {executable!r} is not in the permitted runner allowlist"
def parse_key_commands(instructions_path: Path) -> list[dict[str, str]]:
    if not instructions_path.exists():
        return []
    lines = instructions_path.read_text(encoding="utf-8").splitlines()
    in_key_commands = False
    commands: list[dict[str, str]] = []
    for line in lines:
        if line.strip() == "## Key Commands":
            in_key_commands = True
            continue
        if in_key_commands and line.startswith("## "):
            break
        if not in_key_commands or not line.startswith("|"):
            continue
        columns = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(columns) != 2 or columns[0] == "Task" or set(columns[0]) == {"-"}:
            continue
        commands.append({"label": columns[0], "command": columns[1].strip("`")})
    return commands
def is_unresolved_command(command: str | None) -> bool:
    return command is None or not command.strip() or command.strip().lower() in UNRESOLVED_COMMAND_VALUES
def resolve_key_command(label: str) -> str | None:
    command = next((entry["command"] for entry in parse_key_commands(WORKSPACE_INSTRUCTIONS_PATH) if entry["label"] == label), None)
    return None if is_unresolved_command(command) else command
def prefer_workspace_python(command: str) -> str:
    try:
        argv = shlex.split(command)
    except ValueError:
        return command
    if not argv:
        return command
    executable = Path(argv[0]).name
    prefix, _, suffix = executable.partition(".")
    if executable not in {"python", "python3"} and (prefix not in {"python", "python3"} or not suffix.isdigit()):
        return command
    workspace_python = WORKSPACE_ROOT / ".venv" / "bin" / "python"
    if workspace_python.is_file():
        argv[0] = str(workspace_python)
    return shlex.join(argv)
def reject_shell_metacharacters(command: str) -> str | None:
    for token in SHELL_METACHARACTERS:
        if token in command:
            return f"command contains unsupported shell syntax: {token}"
    return None
def tail_text(text: str, *, max_lines: int = 20, max_chars: int = 4000) -> str | None:
    if not text:
        return None
    tail = "\n".join(text.splitlines()[-max_lines:])
    return tail[-max_chars:] if len(tail) > max_chars else tail
def build_tool_result(*, status: str, summary: str, command: str | None = None, exit_code: int | None = None, stdout: str = "", stderr: str = "") -> dict:
    result = {"status": status, "summary": summary}
    if command is not None:
        result["command"] = command
    if exit_code is not None:
        result["exitCode"] = exit_code
    for key, value in (("stdoutTail", tail_text(stdout)), ("stderrTail", tail_text(stderr))):
        if value is not None:
            result[key] = value
    return result
def run_argv(argv: list[str]) -> dict:
    completed = subprocess.run(argv, cwd=WORKSPACE_ROOT, capture_output=True, text=True, check=False)
    status = "failed" if completed.returncode != 0 else "ok"
    summary = "Command completed successfully." if status == "ok" else "Command failed."
    return build_tool_result(status=status, summary=summary, command=shlex.join(argv), exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
def _resolve_workspace_file(path_value: object, argument_name: str) -> tuple[Path | None, dict | None]:
    if not (isinstance(path_value, str) and path_value.strip()):
        return None, build_tool_result(status="unavailable", summary=f"{argument_name} must be a non-empty string pointing to an existing file.")
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / candidate
    resolved = candidate.resolve()
    if not resolved.is_file():
        return None, build_tool_result(status="unavailable", summary=f"{argument_name} must be a non-empty string pointing to an existing file.")
    if not resolved.is_relative_to(WORKSPACE_ROOT):
        return None, build_tool_result(status="unavailable", summary=f"{argument_name} must be a path within the workspace root.")
    return resolved, None
def tool_testing_show_key_commands(arguments: dict) -> dict:
    del arguments
    if not workspace_root_valid():
        return {"status": "unavailable", "summary": WORKSPACE_ROOT_UNAVAILABLE, "commands": []}
    commands = parse_key_commands(WORKSPACE_INSTRUCTIONS_PATH)
    if not commands:
        return {"status": "unavailable", "summary": "No key commands were found in .github/copilot-instructions.md.", "commands": []}
    return {"status": "ok", "commands": commands, "summary": f"Discovered {len(commands)} key command(s)."}
def tool_testing_run_tests(arguments: dict) -> dict:
    if not workspace_root_valid():
        return build_tool_result(status="unavailable", summary=WORKSPACE_ROOT_UNAVAILABLE)
    scope = arguments.get("scope", "default")
    extra_args = arguments.get("extraArgs", [])
    target_files = arguments.get("targetFiles", [])
    test_names = arguments.get("testNames", [])
    parse_output = arguments.get("parseOutput", True)
    if not isinstance(extra_args, list) or not all(isinstance(arg, str) for arg in extra_args):
        return build_tool_result(status="unavailable", summary="extraArgs must be a string array.")
    for name, values in (("targetFiles", target_files), ("testNames", test_names)):
        if not isinstance(values, list) or not all(isinstance(arg, str) for arg in values):
            return build_tool_result(status="unavailable", summary=f"{name} must be a string array.")
    if parse_output not in {True, False}:
        return build_tool_result(status="unavailable", summary="parseOutput must be a boolean when provided.")
    if scope == "full" and (extra_args or target_files or test_names):
        return build_tool_result(status="unavailable", summary="scope=full runs the declared test command exactly and does not accept extraArgs, targetFiles, or testNames.")
    command = resolve_key_command("Run tests")
    if command is None:
        return build_tool_result(status="unavailable", summary="No Run tests command is declared in .github/copilot-instructions.md.")
    command = prefer_workspace_python(command)
    reason = reject_shell_metacharacters(command) or _check_executable_allowed(command)
    if reason is not None:
        return build_tool_result(status="unavailable", summary=reason, command=command)
    argv = shlex.split(command) if scope == "full" else shlex.split(command) + extra_args + target_files + test_names
    result = run_argv(argv)
    if parse_output:
        output = "\n".join(str(result.get(key, "")) for key in ("stdoutTail", "stderrTail"))
        result["testSummary"] = parse_test_summary(output)
    return result
def tool_testing_parse_coverage(arguments: dict) -> dict:
    if not workspace_root_valid():
        return build_tool_result(status="unavailable", summary=WORKSPACE_ROOT_UNAVAILABLE)
    coverage_path, error = _resolve_workspace_file(arguments.get("coveragePath", "coverage.xml"), "coveragePath")
    if error is not None or coverage_path is None:
        return error or build_tool_result(status="unavailable", summary="coveragePath could not be resolved.")
    try:
        coverage = parse_coverage_xml_file(coverage_path)
    except Exception as exc:
        return build_tool_result(status="failed", summary=f"Cannot parse coverage XML: {exc}")
    return {"status": "ok", "summary": f"Coverage parsed: {coverage['percentCovered']:.1f}% lines covered.", "coveragePath": str(coverage_path), **coverage}


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="allow")
def _tool_result(payload: dict) -> ToolResult: return ToolResult.model_validate(payload)
mcp = FastMCP("xanadWorkspaceTesting")


@mcp.tool()
def testing_show_key_commands() -> ToolResult:
    """List the workspace key commands declared in .github/copilot-instructions.md."""
    return _tool_result(tool_testing_show_key_commands({}))


@mcp.tool()
def testing_run_tests(scope: str = "default", extraArgs: list[str] | None = None, targetFiles: list[str] | None = None, testNames: list[str] | None = None, parseOutput: bool = True) -> ToolResult:
    """Run the workspace's declared test command with optional typed targets and parsed summary."""
    return _tool_result(tool_testing_run_tests({"scope": scope, "extraArgs": extraArgs or [], "targetFiles": targetFiles or [], "testNames": testNames or [], "parseOutput": parseOutput}))


@mcp.tool()
def testing_parse_coverage(coveragePath: str = "coverage.xml") -> ToolResult:
    """Parse a workspace Cobertura coverage XML artifact into a structured summary."""
    return _tool_result(tool_testing_parse_coverage({"coveragePath": coveragePath}))


if __name__ == "__main__":  # pragma: no cover
    mcp.run()