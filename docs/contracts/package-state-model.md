# xanadAssistant Package State Model

This document defines contract-level expectations for package policy, generated manifest, and installed-state lockfile data.

## Status

This file is normative for field expectations before JSON schemas are written.
The schema files created in later phases should encode these expectations rather than inventing new ones.

## Authoritative Artifacts

Package-side authoritative artifacts:

- `template/setup/install-policy.json`
- `template/setup/install-manifest.json`

Consumer-side authoritative artifact:

- `.github/xanadAssistant-lock.json`

Human-readable derivative artifact:

- `.github/copilot-version.md`

## Policy Contract

`install-policy.json` is the small human-authored ruleset.
It should define:

- schema version
- canonical source roots
- target path rules
- ownership defaults per surface
- conditional inclusion rules
- token replacement rules
- chmod rules
- retired-file policy
- generation settings for mirrors or indexes when those become part of lifecycle generation

The policy file should stay compact and rule-oriented.
It should not become a hand-maintained full manifest.

## Manifest Contract

`install-manifest.json` is generated package truth.
It should contain full managed entries with computed data derived from policy plus filesystem state.

Each managed entry should be able to express at least:

- source path
- target path
- hash
- ownership mode or allowed ownership modes
- write strategy
- conditional install metadata when applicable
- executable or chmod metadata when applicable
- surface or layer classification when applicable

The manifest should also express retired managed files and the intended handling policy for them.

## Lockfile Contract

`.github/xanadAssistant-lock.json` records installed state in the consumer workspace.
It should contain at least:

- lockfile schema version
- installed package version, ref, or commit identity
- manifest schema version
- manifest hash
- selected packs and profile
- ownership mode per managed surface where needed
- applied managed file records or equivalent applied-state summary
- managed files skipped by policy
- retired managed files archived, removed, or left in place
- backup metadata for the last write operation when relevant
- timestamps or comparable lifecycle receipt data

## Migration Rules

- Legacy `.github/copilot-version.md` may exist before the lockfile exists.
- The lifecycle engine should read legacy version state when present.
- A lockfile whose `package.name` is `copilot-instructions-template` is a predecessor install and must be treated as migration-required.
- Successor migration should archive predecessor-owned local files before writing the fresh xanadAssistant lockfile.
- A successful approved apply or repair should write a fresh lockfile.
- The generated Markdown summary is readable output only and must not become the installed-state authority.

## Separation Rules

- Policy is rule-oriented authoring input.
- Manifest is generated package truth.
- Lockfile is consumer installed-state truth.
- Generated Markdown summaries and chat explanations are non-authoritative.
