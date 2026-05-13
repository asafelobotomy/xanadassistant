# Installing xanadAssistant

xanadAssistant installs a curated set of GitHub Copilot surface files — agents,
skills, prompts, hooks, and instructions — into any VS Code workspace.

Requirements: Python 3.10+, stdlib only, internet access.

---

## For Copilot

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

Create the temporary answers directory and write the answers file:

```sh
mkdir -p .xanadAssistant/tmp
```

The following example shows all keys with their default values for reference.
Include only the keys the user explicitly overrides:

```json
{
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
both the `plan setup` and `apply` commands below.
Skip this step entirely when `existingFiles` is empty.

### Step 4 — Generate the plan

```sh
python3 xanadBootstrap.py plan setup \
  --workspace . \
  --answers .xanadAssistant/tmp/setup-answers.json \
  --non-interactive --json
```

If `approvalRequired` is `true` in the plan payload, summarise the planned
writes for the user and ask for confirmation before continuing.

### Step 5 — Apply

```sh
python3 xanadBootstrap.py apply \
  --workspace . \
  --answers .xanadAssistant/tmp/setup-answers.json \
  --non-interactive --json
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

## For humans

One-step install using defaults:

```sh
curl -fsSL https://raw.githubusercontent.com/asafelobotomy/xanadassistant/main/xanadBootstrap.py | python3 - apply --workspace . --non-interactive --json
```

Or download-then-run for a pinned release:

```sh
curl -fsSL https://raw.githubusercontent.com/asafelobotomy/xanadassistant/main/xanadBootstrap.py -o xanadBootstrap.py
python3 xanadBootstrap.py apply --workspace . --version v1.0.0 --non-interactive --json
```

---

## After installation

All future lifecycle operations are available through:

- The `xanadLifecycle` Copilot agent (`.github/agents/xanadLifecycle.agent.md`)
- The installed CLI: `python3 xanadAssistant.py <command> --workspace . --package-root <path>`

See [README.md](README.md) for full usage, update, repair, and factory-restore
documentation.
