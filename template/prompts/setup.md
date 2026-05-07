# Setup Prompt

Use this prompt when the user asks to install or refresh xanad-assistant in the
active repository.

Target workspace: {{WORKSPACE_NAME}}
Selected profile: {{XANAD_PROFILE}}

## Workflow

### 1. Inspect current state

```
python3 xanad-assistant.py inspect \
  --workspace {{WORKSPACE_NAME}} \
  --package-root <xanad-assistant-checkout> \
  --ui agent --json-lines
```

Review `installState`, `manifestSummary`, and any warnings. Ask the user to
confirm the target workspace path if it is not clear from context.

### 2. Clarify answers if needed

If `installState` is `not-installed` or if the user wants to change pack or
profile selection, run the interview:

```
python3 xanad-assistant.py interview \
  --workspace {{WORKSPACE_NAME}} \
  --package-root <xanad-assistant-checkout> \
  --mode setup --json-lines
```

Collect the user's answers and write them to an answer file, or use
`--non-interactive` if the defaults are acceptable.

### 3. Generate a plan

```
python3 xanad-assistant.py plan setup \
  --workspace {{WORKSPACE_NAME}} \
  --package-root <xanad-assistant-checkout> \
  --non-interactive --json-lines
```

If `approvalRequired` is true in the plan payload, summarise the planned writes
and retired files for the user and ask for approval before proceeding.

To preview what would be written without making any changes, pass `--dry-run` to
the `apply` command instead of running `plan` first.

### 4. Apply

Once the user approves (or `approvalRequired` is false):

```
python3 xanad-assistant.py apply \
  --workspace {{WORKSPACE_NAME}} \
  --package-root <xanad-assistant-checkout> \
  --non-interactive --ui agent --json-lines
```

Check the `validation.status` in the apply result. If it is not `passed`,
report the error and the `backupPath` to the user.

### 5. Confirm

Show the user the Receipt phase output and the path to the generated
`.github/copilot-version.md` summary.
