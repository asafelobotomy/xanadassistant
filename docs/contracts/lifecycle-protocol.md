# Xanad Assistant Lifecycle Protocol

This document defines the machine-facing protocol contract for `xanad-assistant.py`.

## Status

This file is normative for machine-readable output shape and stream boundaries.
Phase 0 examples under `docs/contracts/examples/` are part of this contract.

## Transport Modes

The lifecycle engine must support two machine-readable transport styles:

- single JSON document via `--json`
- JSON Lines event stream via `--json-lines`

## Stream Boundaries

`--ui quiet`

- `stdout` carries structured output only.
- `stderr` should be empty except for exceptional runtime failures that prevent structured output.

`--ui agent`

- `stdout` carries structured protocol output only.
- `stderr` carries concise human-visible progress.
- Copilot must never need to scrape `stderr` to make lifecycle decisions.

## Single JSON Result Shape

When a command runs with `--json`, the top-level object should include:

- `command`: top-level command name
- `mode`: lifecycle mode when applicable
- `workspace`: target workspace path or normalized workspace reference
- `source`: resolved package source summary
- `status`: final machine status
- `warnings`: array of warning objects
- `errors`: array of error objects
- `result`: command-specific payload

## JSON Lines Event Shape

Each JSON Lines event must be one complete JSON object per line.

Each event must include:

- `type`: event type name
- `command`: top-level command name
- `sequence`: monotonically increasing integer per invocation

Event-specific fields may add additional keys.

## Required Event Types

Initial Phase 0 protocol examples should cover these event types:

- `phase`
- `inspect-summary`
- `check-summary`
- `question`
- `plan-summary`
- `warning`
- `apply-report`
- `receipt`
- `error`

## Event Type Contracts

`phase`

- Announces a stable lifecycle phase transition.
- Uses one of these labels when applicable: `Preflight`, `Interview`, `Plan`, `Apply`, `Validate`, `Receipt`.

`inspect-summary`

- Reports read-only workspace findings.
- Should summarize install state, source resolution, and relevant managed-surface counts.

`check-summary`

- Reports read-only drift classification results.
- Should summarize clean, missing, stale, malformed, retired, unmanaged, skipped, and unknown counts when available.

`question`

- Requests one structured answer.
- Must include a stable `id`, a `kind`, and enough metadata for non-interactive answer files.

`plan-summary`

- Reports the intended write set, conflicts, backup needs, retired-file actions, and approval requirements.

`warning`

- Reports a non-fatal issue that does not prevent continued planning or application.

`apply-report`

- Reports executed writes, backup location, lockfile writes, validation results, and retired-file actions.

`receipt`

- Reports final user-visible machine state after a successful lifecycle path.

`error`

- Reports a fatal or command-terminating issue.
- Must include a stable machine code and message.

## Question Object Contract

A `question` event should include:

- `id`
- `kind`
- `prompt`
- `required`
- `options` when the question is choice-based
- `recommended` when there is a preferred value
- `default` when a default is safe and meaningful

## Warning And Error Contract

Warning and error objects should include:

- `code`: stable machine identifier
- `message`: concise human-readable summary
- `details`: optional structured details object

## Approval Contract

Plans and top-level write commands should expose whether approval is required before apply.
If approval or answers are missing in non-interactive mode, the command must fail with a stable exit code and structured explanation.

## Protocol Stability Rules

- Additive fields are allowed.
- Removing or renaming a required field is a contract change.
- Changing the meaning of an event type is a contract change.
- Visible terminal text is not part of the machine protocol.
