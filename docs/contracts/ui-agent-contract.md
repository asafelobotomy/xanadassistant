# xanadAssistant UI Agent Contract

This document defines the boundary for `--ui agent`.

## Status

This file is normative for the visible terminal experience when Copilot runs the lifecycle engine.

## Purpose

`--ui agent` exists to serve two audiences at once:

- Copilot consumes the machine-readable protocol.
- The human sees concise branded progress in the visible terminal.

The machine protocol remains authoritative.

## Stable Phase Labels

The visible terminal should use these stable phase labels when applicable:

- `Preflight`
- `Interview`
- `Plan`
- `Apply`
- `Validate`
- `Receipt`

## Stream Split

- `stdout` is reserved for machine-readable protocol output.
- `stderr` is reserved for concise human-visible progress.
- Decorative text must not appear on `stdout` in `--ui agent` mode.

## Human-Visible Rules

- The terminal should feel intentional and branded.
- Output should remain concise and line-oriented.
- No full-screen redraws, cursor-dependent menus, or timing-sensitive animations.
- Optional color is acceptable only with a plain-text fallback.
- `Waiting on Copilot` is an allowed visible state when the script needs conversational input.

## Stability Boundary

These elements are stable enough for contributors to preserve:

- phase names
- the stdout versus stderr split
- the rule that visible text is non-authoritative
- the existence of concise receipts

These elements are cosmetic and may evolve without protocol change:

- exact spacing
- decorative separators
- color choices
- short taglines or branding copy
