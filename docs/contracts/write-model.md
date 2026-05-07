# Xanad Assistant Write Model

This document defines ownership modes, write strategies, and retired-file handling rules.

## Status

This file is normative for how the lifecycle engine reasons about writes.

## Ownership Modes

Initial ownership modes:

- `local`
- `plugin-backed-copilot-format`

`local`

- The managed artifact is installed directly into the consumer repository.
- The lifecycle engine is responsible for applying and updating it locally.

`plugin-backed-copilot-format`

- The managed artifact is expected to come from Copilot-format plugin packaging where supported.
- Local lifecycle state may still need to manage adjacent files that are not reliably owned by plugin delivery.

## Ownership Rules

- Ownership must be explicit for every managed surface.
- The updater must not assume ownership of unmanaged lookalike files.
- User-owned or project-specific content must not be overwritten without policy, plan visibility, and backup.

## Supported Write Strategies

Initial supported strategies:

- `replace-verbatim`
- `copy-if-missing`
- `merge-json-object`
- `preserve-marked-markdown-blocks`
- `token-replace`
- `archive-retired`
- `report-retired`

## Strategy Definitions

`replace-verbatim`

- Replace the target with the package source exactly.

`copy-if-missing`

- Create the target only when it does not already exist.

`merge-json-object`

- Merge structured JSON object content according to deterministic key rules.

`preserve-marked-markdown-blocks`

- Replace managed content while preserving explicitly marked user blocks.

`token-replace`

- Materialize package templates using explicit token rules.

`archive-retired`

- Move a retired managed file into a backup or archive location.

`report-retired`

- Report a retired managed file without modifying it.

## Unsupported Strategies

These should remain unsupported unless later contracts say otherwise:

- heuristic line-by-line merge with no marked boundaries
- prompt-authored manual diff application as lifecycle authority
- silent destructive overwrite of user-owned content
- implicit retired-file deletion without policy, flag, or approval

## Conflict Classes

Initial conflict classes for planning and apply reporting:

- `user-owned-collision`
- `managed-drift`
- `malformed-managed-state`
- `unmanaged-lookalike`
- `retired-file-present`
- `unsupported-merge-request`

## Retired-File Default Behavior

Default retired-file behavior should be:

- archive when update policy says archive and backup exists
- report when the file should remain visible for manual review
- remove only with explicit policy, flag, or user approval
