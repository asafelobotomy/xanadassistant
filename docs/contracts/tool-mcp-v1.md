# Xanad Assistant Tool MCP V1

This document defines the first practical implementation slice for the xanad-assistant first-party tooling MCP.

## Status

This file is normative for the first executable slice of the tooling MCP.

## V1 Goal

Ship one small first-party MCP server that is useful in consumer workspaces without requiring the full xanad-assistant package checkout to be present.

## Controlling Constraint

The managed MCP server script is installed into the consumer workspace as a local file under `.github/hooks/scripts/`.

That script must not assume that:

- the xanad-assistant repository checkout exists locally
- `xanad-assistant.py` is importable as a Python module
- the original package root can be rediscovered later

Because of that, V1 must avoid lifecycle tools that directly wrap the lifecycle CLI unless a later install slice records a stable package source contract for the MCP server to use.

## V1 Source Of Truth

V1 tools should derive workspace-approved commands from machine-readable or directly parseable files already managed into the workspace.

The primary source is the rendered `.github/copilot-instructions.md` file, especially the `Key Commands` section.

If a command is not present there, the tool must report `unavailable` rather than guessing.

## V1 Server Identity

The initial workspace-local stdio server should use a concise first-party name such as `xanadTools`.

It should expose only a small `tools` primitive surface in V1.

Resources, prompts, and apps are out of scope for the first executable slice.

## V1 Tools

### `workspace.run_tests`

Purpose:

- Run the workspace test command declared in `.github/copilot-instructions.md`.

Input schema:

- `scope`: optional string enum: `default`, `full`
- `extraArgs`: optional string array, default empty

Behavior:

- Read the `Run tests` command from `.github/copilot-instructions.md`.
- Execute that command in the workspace root.
- Reject execution if no test command is present.
- Reject execution if `extraArgs` would require shell interpolation rather than argv-safe extension.

Output requirements:

- `status`: `ok`, `failed`, or `unavailable`
- `command`: resolved command string
- `exitCode`: integer when executed
- `summary`: short text summary
- `stdoutTail`: optional trailing stdout excerpt
- `stderrTail`: optional trailing stderr excerpt

### `workspace.run_check_loc`

Purpose:

- Run the repo LOC gate when that gate is explicitly present.

Input schema:

- no arguments

Behavior:

- Prefer a known repo-local command when `.github/copilot-instructions.md` or repo documentation exposes one.
- In xanadassistant's own repo, this resolves to `python3 scripts/check_loc.py`.
- In consumer workspaces without a declared LOC command, return `unavailable`.

Output requirements:

- `status`
- `command`
- `exitCode`
- `summary`

### `workspace.show_key_commands`

Purpose:

- Return the commands discovered from `.github/copilot-instructions.md` so the agent can reason from explicit workspace policy instead of scraping markdown ad hoc.

Input schema:

- no arguments

Behavior:

- Parse the `Key Commands` table from `.github/copilot-instructions.md`.
- Return discovered entries as structured name/value pairs.
- If the file is absent or malformed, return `unavailable`.

Output requirements:

- `status`
- `commands`: array of `{label, command}`
- `summary`

## Deferred Tools

These tools are intentionally deferred from V1:

- `lifecycle.inspect`
- `lifecycle.check`
- `lifecycle.plan_*`
- `lifecycle.apply`
- `lifecycle.update`
- `lifecycle.repair`
- `lifecycle.factory_restore`
- `package.generate`
- `package.check_manifest_freshness`

Reason:

- they depend on package-root-aware execution or contributor-repo-only assets that are not guaranteed to exist in a consumer workspace

## Security Rules

V1 tools must follow these restrictions:

- only execute commands discovered from managed workspace instructions or hardcoded first-party repo contracts
- never accept an arbitrary command string from the agent
- execute from the workspace root only
- return bounded output excerpts rather than full unbounded terminal dumps
- make no outbound network calls

## Failure Model

When a tool cannot safely resolve its underlying command, it must return `unavailable` with an explanation.

It must not fall back to inferred shell commands.

## Upgrade Path

Lifecycle tools may be added in a later slice only after xanad-assistant records a stable package-source contract that the workspace-local MCP server can use safely and deterministically.