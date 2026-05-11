# xanadAssistant Layer Model

This document defines the product-layer contract for `core`, `pack`, `profile`, and `catalog`.

## Status

This file is normative for feature placement and anti-bloat boundaries.

## Layer Definitions

`core`

- Required lifecycle functionality.
- Includes the lifecycle engine, package truth, planning, apply, validation, lockfile handling, and branded agent UI surface.
- Must stay small enough that setup and repair do not depend on optional capability loading.

`pack`

- Optional capability module.
- Adds discrete behavior such as memory, review, research, or workspace operations.
- Must not be required for the lifecycle engine to install, update, repair, or restore the package safely.

`profile`

- Behavior preset.
- Changes defaults such as output density, reporting style, or optional capability selection policy.
- Must not duplicate content that should live in `core` or a `pack`.

`catalog`

- Discovery metadata surface.
- Describes available commands, packs, profiles, ownership modes, and compatibility targets.
- Exists to improve discoverability for Copilot and maintainers without bloating always-on instructions.

## Inclusion Rules

- A feature belongs in `core` only if the package cannot meet its lifecycle guarantees without it.
- A reusable but optional feature belongs in a `pack`.
- A preset that changes defaults without introducing a new capability belongs in a `profile`.
- Metadata used for discovery or routing belongs in the `catalog`.

## Dependency Rules

- `core` must not depend on any optional `pack`.
- A `pack` may depend on `core`.
- A `pack` may depend on another `pack` only if the dependency is explicit, acyclic, and justified by install behavior rather than convenience.
- A `profile` may select or bias `packs`, but it must not require duplicated implementation artifacts.
- The `catalog` may describe every layer, but it must not become the source of truth for managed file state.

## Initial Placements

Initial examples derived from the lifecycle plan:

- `core`: lifecycle engine, manifests, lockfile, planning, apply, validation, branded agent UI
- `pack`: memory, review, research, workspace-ops
- `profile`: balanced, lean, ultra-lean
- `catalog`: machine-readable discovery of commands, packs, profiles, ownership modes, and compatibility targets

## Anti-Bloat Tests

Before adding a feature, the contributor should be able to answer:

- Does it clearly belong to one layer?
- Can it load on demand instead of expanding always-on instructions?
- Does it avoid forcing memory, hooks, MCP, or heavy instructions into every install?
- Does it preserve the machine protocol as the authority instead of decorative UX?

If the answer is no, the feature should not enter the default architecture.
