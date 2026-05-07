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

