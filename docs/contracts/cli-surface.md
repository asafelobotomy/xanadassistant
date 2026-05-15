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
- `apply`
- `check`
- `update`
- `repair`
- `factory-restore`

## Command Intent

`inspect`

- Performs read-only workspace discovery.
- Reports current install state, package source resolution, and managed-surface findings.
- Must not write to the workspace.

`interview`

- Emits structured questions required to complete setup or another lifecycle mode.
- Must support non-interactive machine consumption.
- Must not write to the workspace.

`plan <mode>`

- Computes a no-write lifecycle plan for `setup`, `update`, `repair`, or `factory-restore`.
- Produces machine-readable output suitable for later `apply`.
- Must not write managed files to the workspace.

`apply`

- Applies a previously generated plan.
- Creates a backup before the first managed write.
- Produces a machine-readable report and writes installed state when successful.

`check`

- Performs read-only drift and validity classification.
- Classifies managed state as clean, missing, stale, malformed, retired, skipped, unmanaged, or unknown.
- Must not write to the workspace.

`update`

- Performs inspect plus update planning plus approved apply through one top-level command.

`repair`

- Performs inspect plus repair planning plus apply through one top-level command.

`factory-restore`

- Performs backup plus purge plus reinstall according to policy and approval rules.

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

`--dry-run`

- Allows planning behavior without managed writes.

`--answers`

- Supplies machine-readable answers for interview-driven decisions.

`--resolutions`

- Supplies a pre-recorded conflict-resolution file.
- Used by `apply`, `update`, and `repair` to resolve decisions about pre-existing files.

`--plan-out`

- Writes a serialized lifecycle plan for later apply.

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
