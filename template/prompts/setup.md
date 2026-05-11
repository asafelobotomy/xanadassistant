# Setup Prompt

Use this prompt when the user asks to install or refresh xanadAssistant in the
active repository.

Target workspace: {{WORKSPACE_NAME}}
Selected profile: {{XANAD_PROFILE}}

## Workflow

If the workspace already has the `xanadTools` MCP server connected and the
server can resolve a local xanadAssistant package root or a supported remote
source, prefer the MCP
lifecycle tools over shelling out directly:

- `lifecycle_inspect`
- `lifecycle_interview`
- `lifecycle_plan_setup`
- `lifecycle_apply`
- `lifecycle_check`

For a first-time local install, pass the checkout path as `packageRoot` to the
MCP tool call. For a remote install, pass `source` plus `version` or `ref`.
If the MCP server is unavailable or the workspace cannot resolve the requested
package source, fall back to the CLI commands below.

### 1. Inspect current state

```
python3 xanadAssistant.py inspect \
  --workspace {{WORKSPACE_NAME}} \
  --package-root <path-to-xanadAssistant-checkout> \
  --ui agent --json-lines
```

Review `installState`, `manifestSummary`, and any warnings. Ask the user to
confirm the target workspace path if it is not clear from context.

When `mcp.enabled` is true, the plan should also install the local hook scripts.
Expect `.github/hooks/scripts/xanad-workspace-mcp.py`,
`.github/hooks/scripts/mcp-sequential-thinking-server.py`, and `.vscode/mcp.json`
to appear in the planned writes.

If the warnings include `package_name_mismatch` or `successor_cleanup_required`,
treat the workspace as a predecessor `copilot-instructions-template` install.
Use `plan repair` plus `repair` so xanadAssistant can archive predecessor-owned
 8f6b648 (refactor: standardize product name to xanadAssistant)
files and adopt the workspace cleanly.

### 2. Clarify answers if needed

If `installState` is `not-installed` or if the user wants to change pack or
profile selection, run the interview:

```
python3 xanadAssistant.py interview \
  --workspace {{WORKSPACE_NAME}} \
  --package-root <path-to-xanadAssistant-checkout> \
  --mode setup --json-lines
```

Collect the user's answers and write them to an answer file, or use
`--non-interactive` if the defaults are acceptable.

### 3. Generate a plan

```
python3 xanadAssistant.py plan setup \
  --workspace {{WORKSPACE_NAME}} \
  --package-root <path-to-xanadAssistant-checkout> \
  --non-interactive --json-lines
```

For predecessor-managed installs, replace `plan setup`
with `plan repair`.

If `approvalRequired` is true in the plan payload, summarise the planned writes
and retired files for the user and ask for approval before proceeding.

To preview what would be written without making any changes, pass `--dry-run` to
the `apply` command instead of running `plan` first.

### 4. Apply

Once the user approves (or `approvalRequired` is false):

```
python3 xanadAssistant.py apply \
  --workspace {{WORKSPACE_NAME}} \
  --package-root <path-to-xanadAssistant-checkout> \
  --non-interactive --ui agent --json-lines
```

For predecessor-managed installs, replace `apply` with
`repair`.

Check the `validation.status` in the apply result. If it is not `passed`,
report the error and the `backupPath` to the user.

### 5. Confirm

Show the user the Receipt phase output and the path to the generated
`.github/copilot-version.md` summary.

When MCP is available, prefer `lifecycle_check` for the final confirmation step.
