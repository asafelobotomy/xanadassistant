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

## Bootstrap And Package Resolution

The bootstrap path should be small, auditable, and standard-library only.

Responsibilities:

- Resolve package source from GitHub release, branch, commit, or local path.
- Download the lifecycle package or locate it on disk.
- Verify manifest presence and, when release metadata exists, expected hashes.
- Refuse unsafe or ambiguous sources unless explicitly requested.
- Cache downloaded package content in a predictable temporary or user-cache location.
- Hand off to the lifecycle engine.

Default source policy:

- normal users: GitHub release, `--version latest`
- development: explicit `--ref main` or local `--package-root`
- reproducible repair: lockfile-pinned version or commit when available

## Engine Layers

The script should be internally split into modules even if the first implementation ships as one file.

### Bootstrap Layer

Handles source resolution, download, cache location, and handoff.

### Package Loader

Loads policy, generated manifest, schemas, release metadata, and package files.

### Workspace Inspector

Detects repository state:

- Git repository presence and dirty working tree
- existing `.github/copilot-instructions.md`
- existing `.github/instructions/`, `.github/prompts/`, `.github/agents/`, `.github/skills/`
- existing hooks and MCP config
- VS Code settings and extension recommendations
- prior lockfile or legacy version file
- installed ownership modes
- local custom files not managed by the package
- language/framework hints useful for setup questions

### Interview Schema

Defines required questions as data, not prose embedded only in an agent.

The script should emit question objects such as:

```json
{
  "id": "mcp.fetch.enabled",
  "kind": "confirm",
  "prompt": "Enable the fetch MCP server for this workspace?",
  "default": true,
  "reason": "The package can install the required local hook script atomically.",
  "requiredFor": ["mcp.fetch"]
}
```

Copilot can present those questions conversationally and return `answers.json`.

### Planner

Builds a complete no-write plan.

The plan must include:

- files to add
- files to replace
- files to merge
- files to preserve
- files to skip by policy
- retired files to report or archive
- hook and MCP atomicity actions
- chmod actions
- token substitutions
- backup paths
- lockfile writes
- validation steps
- risk level and approval summary

### Applier

Executes an approved plan.

Rules:

- Create a timestamped backup before the first write.
- Write to temporary files where practical, then replace atomically.
- Apply all selected actions as one transaction as far as the filesystem allows.
- Stop on validation failure and report partial state clearly.
- Never modify files not present in the approved plan.

### Reporter

Produces:

- JSON report for Copilot and tests
- concise terminal receipt for the human
- detailed log file for debugging
- optional Markdown summary for `.github/copilot-version.md`

### Lockfile Manager

Owns `.github/xanad-assistant-lock.json` and repairs legacy state.

## Manifest And Policy Model

Do not hand-maintain an exhaustive manifest. Use a smaller human-authored policy file plus a generator.

### Human-Authored Policy

`template/setup/install-policy.json` should define:

- canonical surfaces
- source roots
- target path rules
- ownership defaults
- strategy defaults
- required conditions
- token rules
- chmod rules
- retired-file policy
- package-format delivery rules

### Generated Manifest

`template/setup/install-manifest.json` should include full file entries with computed hashes.

Example entry:

```json
{
  "id": "hooks.scripts.mcp-fetch-server",
  "surface": "hooks",
  "source": "hooks/scripts/mcp-fetch-server.py",
  "target": ".github/hooks/scripts/mcp-fetch-server.py",
  "ownership": ["local", "plugin-backed-copilot-format"],
  "strategy": "replace-verbatim",
  "requiredWhen": ["mcp.fetch.enabled", "mcp.fetch.available"],
  "tokens": [],
  "chmod": "executable-if-shell",
  "hash": "sha256:<full digest>",
  "introducedIn": "0.10.0"
}
```

Required surfaces:

- core instructions from `template/copilot-instructions.md`
- path instructions from `template/instructions/`
- prompts from `template/prompts/`
- agents from `agents/` when local ownership applies
- skills from `skills/` when local ownership applies
- hook config from `template/hooks/copilot-hooks.json`
- hook scripts from `hooks/scripts/`
- MCP config from `template/vscode/mcp.json` or `template/vscode/mcp-unsandboxed.json`
- VS Code settings and extension recommendations
- workspace files from `template/workspace/`
- starter kits from `starter-kits/`
- Claude compatibility files and workflow files

The manifest should also declare retired managed files so the updater can report, archive, or remove them according to policy.

## Lockfile Model

The canonical installed state should be structured JSON, not Markdown.

Recommended file:

```text
.github/xanad-assistant-lock.json
```

Required lockfile data:

- installed package name
- installed version, source, release, ref, or commit
- applied and updated timestamps
- package manifest schema version
- manifest hash
- ownership mode per surface
- setup answers
- install metadata, including MCP availability and enabled state
- per-file source hash and installed hash
- managed files skipped by policy
- retired managed files archived, removed, or left in place
- unknown legacy values explicitly marked as unknown

`.github/copilot-version.md` should become a generated human-readable summary. It may include a fenced JSON digest for compatibility, but it should not be the only source of truth.

Legacy repair behavior:

- Parse old `.github/copilot-version.md` when present.
- Reconstruct what can be verified from current files and package hashes.
- Mark unknown values explicitly.
- Write a fresh lockfile after user approval or in repair mode.
- Preserve the old file in backup before replacement.

## Ownership Defaults

Default architecture:

- Keep plugin delivery as the package channel.
- Make hooks and MCP servers local whenever `.vscode/mcp.json` uses workspace-local executable paths.
- Keep agents and skills plugin-backed by default.
- Treat all-local mode as an explicit customization choice.
- Copy the lifecycle tool into the consumer repo only for explicit all-local or offline repair modes.

Rationale:

- Hooks and MCP often require executable paths and must be atomic with workspace config.
- Agents and skills are better left plugin-backed when the plugin can supply them reliably.
- All-local installs are useful but should not be the default surprise footprint.

## MCP And Hook Atomicity

MCP config and hook scripts must update together.

Rules:

- If an MCP server entry launches `${workspaceFolder}/.github/hooks/scripts/<name>.py`, that script must exist and match the package hash.
- If a required script is missing or stale, the plan must include it.
- If hooks are plugin-owned and the active package format cannot provide hook or MCP executable paths, the plan must switch that surface to local installation or request confirmation.
- If package-root paths are used, the plan must verify that the active plugin format supports those paths.
- Validation must fail when MCP references an unavailable executable.

This avoids split updates where `.vscode/mcp.json` changes but runtime scripts do not.

## Merge And Write Strategies

Keep supported strategies intentionally small.

Initial strategies:

- `replace-verbatim`: replace managed file exactly from package source
- `copy-if-missing`: create file only when absent
- `merge-json-object`: merge JSON objects while preserving unrelated keys
- `preserve-marked-markdown-blocks`: replace managed Markdown while preserving marked blocks
- `token-replace`: render source with explicit setup tokens
- `archive-retired`: move retired managed file into backup/archive location
- `report-retired`: report retired file without modifying it

Avoid a general Markdown merge engine in the first version. Preserve only explicit markers and known project-specific sections.

## User Content Protection

The updater must not overwrite project-specific content without policy and backup.

Rules:

- Preserve `## §10 - Project-Specific Overrides` in installed instructions.
- Preserve blocks marked `<!-- user-added -->` or `<!-- migrated -->`.
- Merge VS Code settings instead of replacing the whole file.
- Preserve MCP enabled/disabled choices unless a server is new or retired.
- Preserve local custom files not listed in the lockfile.
- Back up every managed file before modification.
- Report unmanaged files that resemble package files instead of assuming ownership.
- Remove retired files only with explicit policy, flag, or user approval.

Default retired-file behavior:

- report by default
- archive when update policy says archive and backup exists
- remove only with explicit confirmation or a clearly named flag

## Repository Authoring Model

Recommended canonical sources:

- `agents/`: canonical for plugin and local agent delivery
- `skills/`: canonical for plugin and local skill delivery
- `hooks/scripts/`: canonical for hook scripts and MCP Python servers
- `template/prompts/`: canonical for consumer prompt delivery
- `template/instructions/`: canonical for consumer instruction stubs
- `template/workspace/`: canonical for workspace files
- `.github/`: developer workspace mirrors only, generated or parity-checked where practical

Existing sync scripts should either feed the manifest generator or be replaced by a broader lifecycle sync command.

Contributor goal:

- A contributor changes one canonical file.
- A single generation command updates manifest, mirrors, and indexes.
- Tests fail if generated state is stale.

## Release Gates And Tests

Required suites:

- policy schema validation
- manifest schema validation
- manifest generation produces stable JSON and full hashes
- every manifest source exists in the package
- every managed source file appears in the generated manifest or an explicit ignore list
- every plugin-delivered surface appears in the correct plugin manifest
- every MCP config executable path has a matching manifest entry
- `inspect` reports existing repo state without writing
- `check` reports missing, stale, malformed, skipped, retired, and unknown surfaces without writing
- simulated stale consumer install updates cleanly to current version
- malformed legacy version files repair into structured lockfiles
- update mode creates backups before writes
- factory restore backs up and reinstalls every managed surface
- retired managed files are reported or archived according to policy
- prompt, instruction, hook, skill, and agent surfaces stay covered
- JSON Lines protocol remains stable for Copilot
- `--ui quiet` emits no decorative output
- `--ui agent` preserves machine protocol while showing branded progress

Existing MCP validation should remain focused. Add lifecycle tests beside it rather than expanding unrelated contract tests.

## Exit Codes

Define stable exit codes early.

Suggested codes:

- `0`: success, no action needed or completed
- `1`: completed with warnings
- `2`: user or approval required
- `3`: plan contains conflicts
- `4`: validation failed
- `5`: package source or manifest error
- `6`: workspace state prevents safe writes
- `7`: partial apply or rollback required attention
- `8`: invalid command, options, or answer file

Copilot should use these codes to decide whether to ask the user, retry with answers, summarize warnings, or stop.

## Implementation Phases

### Phase 1 - Freeze The Contract

Deliverables:

- Finalize command names, output modes, exit codes, and JSON Lines event types.
- Add `template/setup/install-policy.schema.json`.
- Add `template/setup/install-manifest.schema.json`.
- Add lockfile schema for `.github/xanad-assistant-lock.json`.
- Document supported strategies and ownership modes.
- Decide release-source defaults and branch/local development flags.

Definition of done:

- The lifecycle protocol can be implemented and tested without guessing semantics.

### Phase 2 - Generate Package Truth

Deliverables:

- Add `template/setup/install-policy.json`.
- Add manifest generator under `scripts/lifecycle/`.
- Generate `template/setup/install-manifest.json` from policy plus filesystem state.
- Add tests for schema validity, source existence, stable hashes, and unmanaged source detection.

Definition of done:

- CI fails when a managed source file is added, removed, or moved without manifest/policy coverage.

### Phase 3 - Build Inspect, Check, And Interview

Deliverables:

- Add `xanad-assistant.py` or `scripts/lifecycle/xanad_assistant.py` skeleton.
- Implement package resolution for local `--package-root` first.
- Implement workspace inspector.
- Implement lockfile parser and legacy version-file reader.
- Implement `inspect` and `check` with JSON output.
- Implement interview schema emission.
- Add `--ui quiet` and initial `--ui agent` output.

Definition of done:

- Copilot can run the script, receive structured workspace state and questions, and no files are written.

### Phase 4 - Build Planning

Deliverables:

- Implement `plan setup`, `plan update`, `plan repair`, and `plan factory-restore`.
- Implement ownership detection and defaults.
- Implement MCP and hook atomicity planning.
- Implement retired-file planning.
- Implement answer-file validation.
- Implement risk summary and approval summary.

Definition of done:

- A complete write plan can be generated and reviewed without touching the workspace.

### Phase 5 - Build Apply And Repair

Deliverables:

- Implement backup creation.
- Implement replace, copy-if-missing, JSON merge, marked Markdown preservation, token replacement, chmod, retired archive/report.
- Implement lockfile writes.
- Implement generated `.github/copilot-version.md` summary.
- Implement validation after writes.
- Implement repair of malformed legacy installs.

Definition of done:

- A stale or malformed fixture can be repaired with backups, structured state, and validation.

### Phase 6 - Build Update And Factory Restore

Deliverables:

- Implement `update` as inspect plus plan plus approved apply.
- Implement `factory-restore` as backup plus clean managed reinstall.
- Add release/package source support for GitHub releases and explicit refs.
- Add package cache and source verification where metadata allows.

Definition of done:

- A simulated old consumer install updates cleanly to the current package with no missing managed files.

### Phase 7 - Integrate Copilot-Facing Customizations

Deliverables:

- Update the Setup agent to treat the script as the lifecycle authority.
- Replace prose file-copy instructions with script invocation instructions.
- Ensure agent descriptions contain trigger phrases for setup, update, repair, factory restore, and xanad-assistant lifecycle operations.
- Add prompts or skills only where they improve focused workflows; avoid always-loaded instruction sprawl.

Definition of done:

- Copilot setup behavior is driven by the script protocol, not by manually interpreting file inventories.

### Phase 8 - Improve The Agent UI Surface

Deliverables:

- Polish `--ui agent` visible progress.
- Add compact `xanad-assistant` branding.
- Add phase summaries: Preflight, Interview, Plan, Apply, Validate, Receipt.
- Add terminal messages for `Waiting on Copilot`, `Applying approved plan`, and `Validation complete`.
- Ensure color is optional and disabled automatically when unsupported.
- Keep JSON Lines stable and free of decorative text.

Definition of done:

- The terminal feels like a branded lifecycle companion while Copilot still uses the efficient protocol.

### Phase 9 - Simplify Repo Structure

Deliverables:

- Replace hand-maintained mirrors with generated mirrors where practical.
- Keep only necessary differences between template, developer workspace, plugin packaging, and compatibility targets.
- Update contributor docs with the new authoring and release flow.
- Retire redundant Markdown inventories or make them link to generated manifests.

Definition of done:

- Contributors can update canonical sources and run one generation command to refresh derived surfaces.

## Minimum Viable First Slice

The smallest valuable implementation should include:

- local package-root support only
- policy schema
- generated manifest
- lockfile schema
- `inspect`
- `check`
- `interview` question emission
- `plan setup`
- `--ui quiet`
- `--ui agent`
- tests for manifest coverage and check output

This proves the contract before writing files.

## First Build Order

1. Define schemas and protocol fixtures.
2. Write manifest policy and generator.
3. Add fixture consumer repositories for clean, stale, malformed, and locally customized installs.
4. Implement read-only `inspect` and `check`.
5. Implement interview question emission.
6. Implement plan generation.
7. Implement backups and apply strategies.
8. Implement structured lockfile and generated Markdown summary.
9. Add update, repair, and factory restore commands.
10. Integrate the Setup agent and retire prose lifecycle instructions.

## Final North Star

`xanad-assistant` should be a Copilot-operated lifecycle installer for agent customizations, with a human-friendly terminal presence and a deterministic engine underneath.

The human-visible terminal is transparency and personality. The machine-readable protocol is the source of truth.
