# Drift Maintenance

This document defines how xanadassistant maintainers keep source, generated
artifacts, managed surfaces, prompts, docs, and CI behavior from drifting away
from each other.

## Core Rule

Each multi-file behavior needs one authority.

When more than one file describes the same thing, the extra files should be:

- generated from the authority
- validated against the authority by tests
- or reduced to references pointing back to the authority

## Authorities

| Concern | Authority | Derived or checked surfaces |
| --- | --- | --- |
| Lifecycle CLI and apply behavior | `scripts/lifecycle/_xanad/` | contracts, prompts, install docs, regression tests |
| Managed package truth | `template/setup/install-policy.json`, registries, template source files | `template/setup/install-manifest.json`, `template/setup/catalog.json` |
| Consumer-managed `.github` surfaces | lifecycle plan/apply/update flow | repo-local generated copies and consumer installs |
| Verification command set | `scripts/drift_preflight.py` | `.github/workflows/ci.yml`, maintainer docs |
| User-facing setup/apply flow | CLI contract + regression tests | prompts, install docs, README examples |

## Maintainer Loop

When changing source, follow this order:

1. Edit the authority first.
2. Regenerate derived artifacts instead of editing them manually.
3. Refresh managed surfaces through lifecycle when source-managed files changed.
4. Run the narrowest targeted tests for the touched authority.
5. Run `python3 scripts/drift_preflight.py` before merge or push.
6. If prompts, contracts, or mirrored hook copies changed, make sure parity or contract tests exist for that surface.

## Drift Preflight

`scripts/drift_preflight.py` is the canonical pre-merge check runner for this repository.

Default order:

1. `attention-budget`
2. `loc`
3. `tests`
4. `freshness`

Usage:

```sh
python3 scripts/drift_preflight.py
python3 scripts/drift_preflight.py --check tests
python3 scripts/drift_preflight.py --list
```

The workflow file should call this script instead of duplicating raw commands.
If a check changes, update the script first and keep CI as a thin wrapper.

## CI Rule Set

These are the repository's drift-control rules for CI:

1. CI must run only maintained commands that also work locally.
2. CI should call `scripts/drift_preflight.py` by named check instead of embedding duplicate shell logic.
3. Generated artifacts must be freshness-checked, not trusted implicitly.
4. User-facing flow changes must have contract tests, not just updated prose.
5. Mirrored source/managed hook files should have parity coverage whenever both copies ship.
6. If a maintainer adds a new always-on gate, it should be added to `scripts/drift_preflight.py`, documented here, and then wired into CI.

## When To Add Tests

Add or extend tests when any of these change:

- a CLI flag, output shape, or lifecycle mode contract
- a prompt or install guide that contains runnable command examples
- a source file that is mirrored into `.github/` or another shipped copy
- a generated artifact path or regeneration rule
- a drift-prevention policy such as LOC, attention budget, or freshness checks

## Anti-Patterns

Avoid these if the goal is low drift:

- hand-editing generated files
- updating CI commands without updating the local maintainer command path
- describing a setup/apply flow in prompts without a regression that asserts the same flow
- creating a second source of truth for manifest, lockfile, or package-state semantics
- relying on review memory instead of executable parity or contract tests
