# xanadAssistant Exit Codes

This document defines stable exit-code meanings for machine callers.

## Status

This file is normative for exit-code meaning.
Commands may refine reporting details later, but these meanings should remain stable unless the contract packet changes first.

## Exit Codes

`0`

- Success.
- The command completed and produced a valid result.

`1`

- Internal runtime failure.
- Use for unexpected exceptions or unrecoverable implementation faults.

`2`

- Invalid invocation.
- Use for invalid CLI syntax, incompatible flags, or missing required command arguments.

`3`

- Source resolution failure.
- Use when the package source, release, ref, or local package root cannot be resolved.

`4`

- Contract input failure.
- Use when required policy, manifest, schema, answers, or plan inputs are missing, malformed, or inconsistent.

`5`

- Inspection or workspace-state failure.
- Use when the workspace cannot be inspected reliably enough to continue.

`6`

- Approval or answer requirement not satisfied.
- Use when non-interactive execution cannot proceed because required answers or approval are missing.

`7`

- Managed drift or stale state detected.
- Use when `check` or another read-only command determines the install is not current.

`8`

- Managed state is malformed or conflicting.
- Use when legacy state, lockfile state, or managed targets are present but invalid or contradictory.
- **Reserved — not yet raised.** Current malformed-state conditions surface as code `5` or `7`. Code `8` is defined for future use when migration and integrity-check paths require a distinct signal.

`9`

- Apply or validation failure.
- Use when writes were attempted but post-apply validation failed or the plan could not be completed safely.

`10`

- User or operator cancellation.
- Use when the run stops intentionally after a structured cancellation point.

## Handling Guidance

- Exit codes `0` through `6` are primarily about execution flow.
- Exit codes `7` and `8` are meaningful state signals for drift-aware automation.
- Exit code `9` implies the caller should inspect the structured report and backup path.
- Exit code `10` should not be treated as an internal failure.

## Reserved Ranges

- `11` through `19` are reserved for future lifecycle execution states.
- `20` through `29` are reserved for future check-specific classifications if finer machine handling becomes necessary.
