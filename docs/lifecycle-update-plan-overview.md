# Xanad Assistant Lifecycle Plan

This plan reinvents the template lifecycle around a Copilot-operated setup tool. The goal is to make `asafelobotomy/xanad-assistant` installable, updateable, repairable, and restorable without relying on Copilot to infer file ownership, merge behavior, version state, or package drift from prose.

The new default experience should be simple for the user:

1. A user asks Copilot to set up `asafelobotomy/xanad-assistant` in an active repository.
2. Copilot fetches or runs the `xanad-assistant` setup script.
3. The script inspects the workspace, resolves the package source, generates a plan, and exposes any required questions.
4. Copilot discusses the meaningful choices with the user.
5. Copilot passes structured answers back to the script.
6. The script applies the approved setup, update, repair, or restore plan transactionally.
7. The script writes structured installed state, validates the result, and reports a concise receipt.

The script is the main tool. Copilot is the conversational operator. The terminal is a visible, branded progress surface for the human.

## Product Principles

- The package must be authoritative. File inventories, hashes, ownership rules, and retired-file policies belong in generated machine-readable artifacts, not scattered Markdown checklists.
- The setup script must own lifecycle decisions. Copilot should not manually copy, diff, merge, hash, repair, or validate managed surfaces.
- The engine must be deterministic. Every write should come from an inspectable plan, use explicit strategies, create backups first, and produce structured reports.
- The interface must be Copilot-native. Copilot should use JSON, JSON Lines, stable exit codes, answer files, plan files, and report files instead of scraping a TUI.
- The visible terminal should still feel intentional. The human should see a polished `xanad-assistant` progress experience while Copilot uses the machine protocol.
- User choices and local content are protected by default. The tool should preserve project-specific content, archive before destructive changes, and prefer warnings over surprise deletions.
- First implementation should be dependency-free. Use Python 3 standard library only until the lifecycle contract is stable.

## Design Delta From Existing Repos

This plan is not a blank-sheet redesign. It intentionally keeps what already works in `copilot-instructions-template`, borrows useful patterns from adjacent projects, and replaces the parts that currently create drift, bloat, or procedural ambiguity.

### What `copilot-instructions-template` Already Does Well

The current template already provides strong raw material:

- plugin packaging across multiple manifest formats
- a Setup agent that already covers setup, update, backup restore, and factory restore
- starter-kit detection and registry-driven stack onboarding
- workspace memory scaffolding, heartbeat review, and durable project memory rules
- a machine-readable `llms.txt` index and routing metadata
- initial response-style controls and prose-compression support

`xanad-assistant` should preserve those strengths. The goal is not to remove them. The goal is to make them more deterministic, leaner, and easier for Copilot to operate.

### What The External References Add

The adjacent projects point to useful patterns, but they should be imported selectively.

From `mempalace`:

- local-first memory as an optional capability, not a cloud dependency
- structured retrieval and scoped recall instead of dumping all context into instructions
- autosave and recall surfaces that are operationally reliable
- benchmark-first thinking for claims about memory quality

From `caveman`:

- output brevity as a first-class optimization target
- multiple terseness levels instead of one fixed style
- compact auxiliary workflows for reviews, commits, and summaries
- the principle that compression should preserve identifiers, commands, paths, and technical meaning exactly

From `awesome-copilot`:

- clear taxonomy across agents, skills, hooks, prompts, plugins, and workflows
- discoverability through machine-readable catalog surfaces
- breadth through optional modules rather than one giant default install

### What `xanad-assistant` Should Do Better

`xanad-assistant` should improve the current template in these specific ways:

- Replace agent-procedural lifecycle logic with a real lifecycle engine and manifest-driven planner.
- Turn starter-kit thinking into a broader capability-pack model, not just language-stack kits.
- Turn response-style questions into real behavior profiles that influence output density, receipts, review style, and reporting defaults.
- Keep the existing memory philosophy, but move advanced local retrieval into an optional pack instead of the mandatory core install.
- Expand the current discovery surfaces into a richer machine-readable catalog for packs, profiles, lifecycle commands, ownership modes, and compatibility targets.

### Architectural Conclusions

This comparison leads to four product layers:

- **Core**: lifecycle engine, manifests, lockfile, planning, apply, validation, branded agent UI
- **Capability packs**: optional modules such as memory, review, research, or workspace operations
- **Profiles**: behavior presets such as balanced, lean, or ultra-lean
- **Catalog**: machine-readable discovery surface for Copilot and human maintainers

The core should stay small. Anything new must clearly belong to one of those layers.

### Anti-Bloat Rules

To keep `xanad-assistant` lean, every new capability must pass these tests:

- It belongs in `core`, a `pack`, a `profile`, or the `catalog`.
- It does not need to be always loaded to be useful.
- It does not force memory, hooks, MCP, or large instruction surfaces into every install.
- It does not replace structured protocol with decorative UX.
- It does not depend on Copilot remembering procedural file inventories from prose.

If a capability fails those tests, it should not enter the default architecture.

### Explicit Non-Goals

`xanad-assistant` should not:

- make local memory mandatory
- turn the assistant voice into a novelty persona
- install every optional capability by default
- grow into a loose marketplace clone with no opinionated core
- let visible terminal cosmetics compete with protocol clarity

## Known Failure Mode

The previous lifecycle model depended on agent-authored instructions and Markdown inventories. That works for small instruction-only updates, but fails when a release changes executable or multi-surface behavior.

The failure class observed during a stale install included:

- installed version metadata still reporting an older version after an attempted update
- missing ownership and install metadata
- malformed fingerprint blocks
- stale or missing agents, skills, hooks, prompts, instruction stubs, and workspace files
- MCP config pointing at local scripts that were not updated atomically
- package manifests and plugin delivery metadata drifting from template sources

The root problem is that no single executable lifecycle system applied the package state as a transaction.

## Target Architecture

The system has five durable parts:

- `xanad-assistant.py`: the Copilot-facing setup, update, repair, and restore tool
- `template/setup/install-policy.json`: small human-authored lifecycle policy
- `template/setup/install-manifest.json`: generated package truth with sources, targets, hashes, ownership, strategies, and retired files
- `.github/xanad-assistant-lock.json`: structured installed-state lockfile in consumer repos
- `.github/copilot-version.md`: optional human-readable installed summary generated from the lockfile

The setup script should be able to run from a GitHub release, a branch, a local checkout, or a pinned commit. Normal user installs should prefer releases once release packaging exists. Development installs may use `main` or another branch explicitly.

## Default Lifecycle Commands

The script should support these high-level commands through one engine:

```bash
python3 xanad-assistant.py inspect --workspace .
python3 xanad-assistant.py interview --workspace . --mode setup
python3 xanad-assistant.py plan setup --workspace . --answers answers.json --plan-out plan.json
python3 xanad-assistant.py apply --workspace . --plan plan.json
python3 xanad-assistant.py check --workspace .
python3 xanad-assistant.py update --workspace .
python3 xanad-assistant.py repair --workspace .
python3 xanad-assistant.py factory-restore --workspace .
```

Supported source options:

```bash
--source github:asafelobotomy/xanad-assistant
--version latest
--version 0.10.0
--ref main
--package-root /local/path/to/xanad-assistant
```

Supported automation options:

```bash
--json
--json-lines
--non-interactive
--dry-run
--answers answers.json
--plan-out plan.json
--report-out report.json
--log-file .xanad-assistant/logs/<timestamp>.log
--ui quiet
--ui agent
--ui tui
```

## Output Modes

The script should separate protocol from presentation.

### `--ui quiet`

Use for tests, CI, and pure automation.

- Emits structured JSON or JSON Lines only.
- Prints no decorative progress.
- Never prompts interactively.
- Uses stable exit codes.

### `--ui agent`

Use as the default when Copilot runs the script.

- Emits machine-readable JSON Lines for Copilot.
- Shows concise branded progress in the visible terminal.
- Avoids full-screen redraws, cursor-dependent menus, animations, and timing-sensitive behavior.
- Frames the script as a lifecycle companion working with Copilot.
- Never requires Copilot to parse decorative text for decisions.

Recommended stream split:

- `stdout`: JSON Lines protocol
- `stderr`: human-visible branded progress

Example visible progress:

```text
xanad-assistant
Copilot lifecycle companion

Preflight
  Workspace scanned
  Existing Copilot config found
  MCP support available
  Git working tree has local changes

Setup Plan
  Add       12 managed files
  Merge      2 settings files
  Preserve   3 user-owned files
  Skip       plugin-backed agents/skills

Waiting on Copilot
  I found two safe setup paths. Copilot is checking which one fits this repo.
```

Example protocol output:

```jsonl
{"type":"event","phase":"preflight","status":"complete","workspace":"/repo"}
{"type":"question","id":"ownership.hooks","kind":"choice","options":["local","plugin-backed"],"recommended":"local"}
{"type":"plan","status":"ready","adds":12,"merges":2,"preserves":3,"skips":1}
```

### `--ui tui`

Use for human-first direct execution.

- May use color and richer prompts.
- Still uses the same planner and applier.
- Should remain optional, not the interface Copilot depends on.
