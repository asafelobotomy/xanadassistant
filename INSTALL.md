# Installing xanadAssistant

xanadAssistant installs a curated set of GitHub Copilot surface files — agents,
skills, prompts, hooks, and instructions — into any VS Code workspace.

Requirements: Python 3.10+ for the lifecycle core, internet access, and `uvx`-managed MCP runtime dependencies when hook-enabled installs are used.

---

## Quickstart: Copilot agent setup (recommended)

Open Copilot chat (agent mode) and say:

> **Setup asafelobotomy/xanadassistant**

Copilot fetches the `xanadLifecycle` agent from GitHub (Step 0 below), installs
it into your workspace, then drives the full bootstrap — interview, plan, apply,
cleanup. No manual commands needed.

### Manual alternative

If you prefer to run Step 0 yourself before handing off to Copilot:

```sh
mkdir -p .github/agents && curl -fsSL \
  https://raw.githubusercontent.com/asafelobotomy/xanadassistant/main/agents/xanadLifecycle.agent.md \
  -o .github/agents/xanadLifecycle.agent.md
```

Then in Copilot chat: **@xanadLifecycle Setup xanadAssistant**

---

## Copilot agent workflow (step-by-step reference)

This section documents what the `xanadLifecycle` agent does internally.
It is also the procedure to follow when using Copilot without the agent
pre-installed (e.g. when the agent file cannot be downloaded first).

If a user has asked you to set up xanadAssistant in their workspace, follow
these steps. No prior installation or local checkout is needed.

### Step 1 — Fetch the bootstrap runner

Download `xanadBootstrap.py` using whichever method is available:

```sh
curl -fsSL https://raw.githubusercontent.com/asafelobotomy/xanadassistant/main/xanadBootstrap.py -o xanadBootstrap.py
```

```sh
python3 -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/asafelobotomy/xanadassistant/main/xanadBootstrap.py', 'xanadBootstrap.py')"
```

To pin to a specific release instead of `main`, replace `main` in the URL with
the release tag (e.g. `v1.0.0`). Check the
[releases page](https://github.com/asafelobotomy/xanadassistant/releases) for
the latest tag.

### Step 2 — Inspect the workspace

```sh
python3 xanadBootstrap.py inspect --workspace . --json
```

Review `installState`. If it is not `not-installed`, stop and report the state
to the user before continuing.

### Step 3 — Run the interview

```sh
python3 xanadBootstrap.py interview --workspace . --mode setup --json
```

Parse the `result.questions` array. For each question, present the `prompt` and
the `default` to the user and ask whether they want to override it. Collect the
responses. Omitted keys are filled from their `default` values automatically —
only include keys that differ from the default or that the user explicitly
provided.

Each question also carries a `batch` field:

- `setup` — always first; ask `setup.depth` before anything else
- `simple` — always shown
- `advanced` — shown when `setup.depth` is `advanced` or `full`
- `full` — shown only when `setup.depth` is `full`

Use the user's `setup.depth` answer to decide which later questions to ask.

Create the temporary answers directory and write the answers file:

```sh
mkdir -p .xanadAssistant/tmp
```

The following example shows all keys with their default values for reference.
Include only the keys the user explicitly overrides:

```json
{
  "setup.depth": "simple",
  "profile.selected": "balanced",
  "packs.selected": [],
  "ownership.agents": "plugin-backed-copilot-format",
  "ownership.skills": "plugin-backed-copilot-format",
  "response.style": "balanced",
  "autonomy.level": "ask-first",
  "agent.persona": "professional",
  "testing.philosophy": "always",
  "mcp.enabled": true,
  "mcp.servers": []
}
```

Write the collected answers to `.xanadAssistant/tmp/setup-answers.json`. Any
key omitted from the file is resolved to its declared `default` by the
lifecycle engine.

`packs.selected` accepts one or more pack names as an array. If the user
selects multiple packs, the plan step will surface any token conflicts that
need resolution before proceeding.

### Step 3.5 — Resolve pre-existing files (optional)

If the interview response includes a non-empty `result.existingFiles` array,
review it before planning.  Each record has a `type` and `availableDecisions`:

- `collision` — a file xanadAssistant would overwrite. Decisions: `keep`, `replace`, `merge` (if supported).
- `unmanaged` — a file in a managed directory xanadAssistant does not own. Decisions: `keep`, `remove`.

Write your per-file decisions to `.xanadAssistant/tmp/conflict-resolutions.json`:

```json
{
  ".github/prompts/my-prompt.md": "keep",
  ".github/agents/old-agent.md": "remove"
}
```

Then pass `--resolutions .xanadAssistant/tmp/conflict-resolutions.json` to
the `plan setup` command below.
Skip this step entirely when `existingFiles` is empty.

### Step 4 — Generate the plan

```sh
python3 xanadBootstrap.py plan setup \
  --workspace . \
  --answers .xanadAssistant/tmp/setup-answers.json \
  --plan-out .xanadAssistant/tmp/setup-plan.json \
  --non-interactive --json
```

If `approvalRequired` is `true` in the plan payload, summarise the planned
writes for the user and ask for confirmation before continuing.

### Step 5 — Apply

```sh
python3 xanadBootstrap.py apply \
  --workspace . \
  --plan .xanadAssistant/tmp/setup-plan.json \
  --json
```

Check `validation.status` in the response. If it is not `passed`, report the
error and the `backupPath` to the user.

### Step 6 — Clean up

```sh
rm xanadBootstrap.py
rm -rf .xanadAssistant/tmp
```

The install is complete. The `xanadLifecycle` Copilot agent installed in
`.github/agents/` handles all future lifecycle operations (update, repair,
factory-restore).

---

## Without Copilot

> **Note:** The Copilot agent method above is the recommended path. Use this only when Copilot agent mode is unavailable.

Two-step install using defaults:

```sh
curl -fsSL https://raw.githubusercontent.com/asafelobotomy/xanadassistant/main/xanadBootstrap.py -o xanadBootstrap.py
python3 xanadBootstrap.py plan setup --workspace . --non-interactive --plan-out .xanadAssistant/tmp/setup-plan.json --json
python3 xanadBootstrap.py apply --workspace . --plan .xanadAssistant/tmp/setup-plan.json --json
```

Or download-then-run for a pinned release:

```sh
curl -fsSL https://raw.githubusercontent.com/asafelobotomy/xanadassistant/main/xanadBootstrap.py -o xanadBootstrap.py
python3 xanadBootstrap.py plan setup --workspace . --version v1.0.0 --non-interactive --plan-out .xanadAssistant/tmp/setup-plan.json --json
python3 xanadBootstrap.py apply --workspace . --plan .xanadAssistant/tmp/setup-plan.json --json
```

---

## After installation

All future lifecycle operations are available through the `xanadLifecycle`
Copilot agent installed at `.github/agents/xanadLifecycle.agent.md`. Use the
installed prompts for day-to-day operations: `/setup`, `/update`.

The lifecycle CLI (`python3 xanadAssistant.py`) is available for maintainers
and advanced use — see [README.md](README.md).
