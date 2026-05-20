# xanadAssistant CLI Surface

This document defines the Phase 0 contract for the lifecycle command surface.

## Status

This file is normative for argument names, command names, and machine-facing behavior.
Implementation may be stubbed, but later code and schemas should conform to this surface unless the contract packet is revised first.

## Execution Entry

The entry point is `xanadAssistant.py` at the repo root. The internal engine module lives at `scripts/lifecycle/xanadAssistant.py` but is not part of the external command surface.

## Core Command Set

The lifecycle engine must expose these commands:

- `inspect`
- `interview`
- `plan setup`
- `plan update`
- `plan repair`
- `plan factory-restore`
- `setup`
- `health-check`
- `update`
- `repair`
- `factory-restore`
- `health-report`

## Command Intent

`inspect`

- Performs read-only workspace discovery.
- Reports current install state, package source resolution, and managed-surface findings.
- Must not write to the workspace.

`interview`

- Emits structured questions required to complete setup or another lifecycle mode.
- Emits base questions first; later `plan` responses may append installed-agent follow-up questions once the effective install set is known.
- Must support non-interactive machine consumption.
- Must not write to the workspace.

`plan <mode>`

- Computes a no-write lifecycle plan for `setup`, `update`, `repair`, or `factory-restore`.
- Produces machine-readable output suitable for later `setup` when the mode is `setup`, or for review before the matching top-level write command.
- May append installed-agent follow-up questions and must preserve their answers into the serialized plan's lockfile state.
- Must not write managed files to the workspace.

`setup`

- Applies a previously generated serialized `setup` plan.
- Creates a backup before the first managed write.
- Produces a machine-readable report and writes installed state when successful.

`health-check`

- Performs read-only drift and validity classification.
- Classifies managed state as clean, missing, stale, malformed, retired, skipped, unmanaged, or unknown.
- Must not write to the workspace.

`update`

- Performs inspect plus update planning plus approved write execution through one top-level command.

`repair`

- Performs inspect plus repair planning plus approved write execution through one top-level command.

`factory-restore`

- Performs backup plus purge plus reinstall according to policy and approval rules.

`health-report`

- Collects a workspace health check report for maintainers.
- Must not write managed files to the workspace.
- May format findings for issue or discussion submission.

## Required Common Flags

Every command should accept `--workspace`.

Source selection:

- `--source`
- `--version`
- `--ref`
- `--package-root`

Machine I/O:

- `--json`
- `--json-lines`
- `--non-interactive`
- `--dry-run`
- `--answers`
- `--resolutions`
- `--plan`
- `--plan-out`
- `--report-out`
- `--log-file`

Presentation:

- `--ui quiet`
- `--ui agent`
- `--ui tui`

## Flag Semantics

`--workspace`

- Required unless the current working directory is explicitly accepted as the default in a later revision.
- Points to the consumer repository being inspected or modified.

`--source`

- Selects the package source family, such as `github:asafelobotomy/xanadAssistant`.

`--version`

- Selects a release version when release packaging is available.

`--ref`

- Selects an explicit Git ref for development or pinned installs.

`--package-root`

- Selects a local package checkout.
- This is the first source mode that implementation must support.

`--json`

- Emits one JSON document for the command result.

`--json-lines`

- Emits newline-delimited JSON events.

`--non-interactive`

- Disables interactive prompting.
- Commands must fail with a stable exit code when required answers are missing.
- `setup` must reject this flag because interactive decisions are already frozen into the serialized plan.

`--dry-run`

- Allows planning behavior without managed writes.

`--answers`

- Supplies machine-readable answers for interview-driven decisions.
- `setup` must reject this flag because answers are resolved before the serialized plan is produced.

`--resolutions`

- Supplies a pre-recorded conflict-resolution file.
- Used by `plan`, `update`, and `repair` to resolve decisions about pre-existing files.
- `setup` must reject this flag because conflict decisions are already frozen into the serialized plan.

`--plan`

- Supplies a previously generated serialized lifecycle plan.
- Required by `setup`.

## Retired Commands

`apply`

- Remains parseable only as a retirement tombstone for stale automation.
- Must fail with code `retired_command` and actionable migration guidance.
- Use `setup` for serialized setup plans, or the top-level `update`, `repair`, or `factory-restore` commands for those modes.

`--plan-out`

- Writes a serialized lifecycle plan for later setup when the mode is `setup`, or for review before the matching top-level write command.

`--report-out`

- Writes the final structured report.

`--log-file`

- Writes a plain-text operational log.

## Output Guarantees

- `--ui quiet` must emit structured output only.
- `--ui agent` must keep machine-readable protocol on `stdout` and branded human-visible progress on `stderr`.
- Decorative terminal output must never be required for Copilot decisions.
- The CLI contract is stable even if internal modules, helper scripts, or packaging layout change.

## Deferred Decisions

These details may remain implementation-level for now as long as the external surface above remains stable:

- exact argument parser library
- internal module names
- whether `plan` also accepts an optional plan file input for replanning
- whether `--json-lines` becomes the default for `--ui agent`
