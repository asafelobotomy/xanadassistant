# xanadAssistant Implementation Plan

This document turns the architecture in `docs/lifecycle-update-plan.md` into an implementation sequence.

It is intentionally contract-first. The repo should not begin implementation work until the protocol, ownership model, packaging boundaries, and context-discipline rules are explicit enough that contributors can build without guessing.

This plan optimizes for five outcomes:

- deterministic lifecycle behavior
- low-bloat context and packaging
- strong Copilot operability
- safe recovery and upgrade paths
- clear contributor workflow and testability

## Relationship To The Lifecycle Plan

Use this document to execute the work.

Use `docs/lifecycle-update-plan.md` for:

- product direction
- architecture principles
- design deltas from `copilot-instructions-template`
- anti-bloat rules
- target command surface and lifecycle concepts

This document adds:

- implementation order
- checklists
- phase gates
- deliverable inventory
- validation requirements
- source packet for implementation decisions

Later in the program, this document intentionally splits the final repo-structure work from optional capability work. The lifecycle plan's later cleanup phase becomes two implementation phases here: Phase 9 for optional packs, profiles, and catalog behavior, and Phase 10 for repo-structure simplification.

## Operating Rules

These rules apply to every phase.

- Do not expand the always-on instruction surface unless a capability cannot be loaded on demand.
- Prefer `skills`, targeted instructions, prompt files, and lifecycle protocol over giant agent bodies.
- Keep hooks and MCP deterministic, inspectable, and minimal.
- Treat memory as scoped, optional, and citation-backed where durability matters.
- Preserve plugin-backed delivery where it is reliable; fall back to local ownership where runtime path guarantees are missing.
- Land small, testable slices. No phase should require a “big bang” migration.
- Each phase must leave the repo in a releasable state.

## Workstreams

Implementation spans five parallel concerns, but they should land in the phase order below.

### A. Lifecycle Engine

- package resolution
- inspect and check
- interview schema
- planning
- apply and repair
- update and factory restore

### B. Package Truth

- policy schema
- generated manifest
- lockfile schema
- derived mirrors and indexes

### C. Copilot Integration

- setup agent integration
- prompts and handoffs
- branded terminal UX
- JSON Lines protocol

### D. Capability Model

- core vs packs vs profiles vs catalog
- optional memory layer
- lean response profiles
- discovery metadata

### E. Validation And Release

- fixture repos
- contract tests
- stale-install upgrade tests
- release gating

## Audit Status

Audit status as of 2026-05-07:

- Phases 0 through 3 are complete and validated in repo artifacts, code, and tests.
- Phase 4 is complete for the currently modeled surfaces: the CLI emits deterministic no-write plans for current core surfaces plus conditional agent, skill, hook, and MCP surfaces, with write summaries, backup path planning, retired-file planning, ownership resolution, token substitution summaries for tokenized managed files, planned lockfile output, validated answer-file handling for profile and pack selection, explicit conflict and warning classification, and `--plan-out` serialization. Token-aware prompt hashing is now applied consistently across inspect, check, planning, and lockfile output for the current setup slice.
- Phase 5 is complete: all supported write strategies are implemented and tested. `copy-if-missing` skips files that are already present (even in factory-restore mode). `archive-retired` moves retired managed files to the configured archive root. `report-retired` leaves files in place and records them without causing validation drift. `classify_manifest_entries` correctly excludes report-retired files from the drift count. The apply engine backs up any existing lockfile before overwriting it, enabling malformed-lockfile repair to be fully reversible. Validation failure now leaves the workspace in a recoverable state with the backup root intact and the backup path surfaced in the error payload. All Phase 5 test checklist items are covered, including per-strategy focused tests, lockfile schema validation, malformed-lockfile repair, and validation-failure behavior.
- Phase 9 is complete: pack selection and profile selection are implemented and lockfile-recorded. `condition_matches` handles list membership for conditional surfaces. `seed_answers_from_profile` applies profile defaultPacks and filtered setupAnswerDefaults before question resolution. The `lean` pack and `lean` profile are active. The first lean pack surface (`lean-skills`) is fully wired in the policy with `requiredWhen: ["packs.selected=lean"]`. `generate_catalog` produces `catalog.json` from policy and registries. The memory pack is deliberately metadata-only and kept planned. 16 Phase 9 tests pass alongside the full 96-test suite.
- Phase 6 is complete: GitHub release resolution, explicit ref resolution, package caching, integrity checks, stale-version warning, and incomplete-install recovery are all implemented and tested. The source resolution pipeline resolves `--package-root` (local) or `--source github:owner/repo` with optional `--version` or `--ref`. Package cache lives under `~/.xanadAssistant/pkg-cache/` (overridable via `XANAD_PKG_CACHE`). GitHub release tarballs are downloaded and extracted with path-traversal protection; GitHub refs are cloned with `git clone --depth 1`. `verify_manifest_integrity` compares the current manifest hash against the lockfile's recorded hash. `collect_context` emits a `package_version_changed` warning when the hashes differ. `determine_repair_reasons` now includes `incomplete-install` when the lockfile is present but managed files are missing. `--dry-run` skips all file writes and reports planned write counts instead. `--log-file` writes agent-progress lines to a file. The lockfile `package` field is populated with `version`, `source`, and `ref` from `_session_source_info` when a GitHub source is used.
- Phase 7 is complete: `agents/lifecycle-planning.agent.md` now includes trigger phrases, a full command reference with exact CLI invocations for all lifecycle commands including GitHub source and dry-run, and a clear responsibility boundary. `template/prompts/setup.md` provides a complete five-step workflow (Inspect → Clarify → Plan → Apply → Confirm) with concrete command invocations and dry-run guidance.
- Phase 8 is complete: `emit_agent_progress` now emits Preflight, Plan, Apply, Validate, and Receipt phase labels. ANSI color is applied when `sys.stderr.isatty()` is true or `FORCE_COLOR` is set, and suppressed when `NO_COLOR` is set. Dry-run results note that no files were written. Agent progress output is also mirrored to `--log-file` when provided.
- The current fixture consumer strategy is ephemeral temporary workspaces in unit tests rather than committed fixture repositories. That is sufficient for current Phases 2 and 3 validation, but not for later end-to-end upgrade and restore coverage.
- Checklist state below should track implemented behavior and verified documentation, not intended sequence alone.

## Current Remaining Work

The remaining implementation work is now concentrated in the unfinished execution behaviors and the later integration phases.

### Next Execution Work

- Verify the GitHub release and ref resolution paths against real network targets. Run with `XANAD_NETWORK_TESTS=1 python3 -m unittest tests.test_convergence_and_network` (requires outbound HTTPS to github.com).
- Lockfile migration coverage is done: `_lockfile_needs_migration`, `migrate_lockfile_shape`, and `LockfileMigrationTests` (15 tests) added.
- Definition of Done: all items verified and checked off. The implementation program is complete.

## Phase 0 - Freeze The Contracts

### Phase 0 Goal

Define the product-layer, protocol, and schema contracts tightly enough that the rest of the implementation can proceed without semantic churn.

### Phase 0 Deliverables

- CLI command matrix for `xanadAssistant.py`
- JSON and JSON Lines protocol specification
- lifecycle exit-code table
- `core`, `pack`, `profile`, and `catalog` definitions
- lifecycle policy schema design
- manifest schema design
- lockfile schema design
- ownership-mode vocabulary
- write-strategy vocabulary
- memory-boundary contract
- branding and `--ui agent` output contract

### Phase 0 Artifact Set

Phase 0 should end with concrete repo artifacts, not just agreement in chat. The minimum contract packet should be:

- `docs/contracts/cli-surface.md`
- `docs/contracts/lifecycle-protocol.md`
- `docs/contracts/exit-codes.md`
- `docs/contracts/layer-model.md`
- `docs/contracts/package-state-model.md`
- `docs/contracts/write-model.md`
- `docs/contracts/memory-boundary.md`
- `docs/contracts/ui-agent-contract.md`
- `docs/contracts/examples/inspect.json`
- `docs/contracts/examples/plan-setup.json`
- `docs/contracts/examples/apply-report.json`
- `docs/contracts/examples/event-stream.jsonl`

These artifacts should describe the contract even if the implementation is still stubbed. They are documentation-first contract surfaces, but they must be specific enough that later schemas and code can be judged against them.

### Phase 0 Order Of Operations

Phase 0 should land in this order:

1. Freeze the CLI surface, command matrix, and exit-code meanings.
2. Freeze the JSON and JSON Lines protocol, including event names and required fields.
3. Freeze the layer model for `core`, `pack`, `profile`, and `catalog`.
4. Freeze ownership modes, write strategies, and retired-file semantics.
5. Freeze lockfile, policy, and manifest field expectations at the contract level.
6. Freeze the `--ui agent` boundary so human-visible terminal text stays non-authoritative.
7. Add example fixtures that demonstrate the contract on one clean setup path and one update path.

If one of these steps is still unstable, Phase 0 is not done.

### Phase 0 Checklist

- [x] Define final command list for `inspect`, `interview`, `plan`, `apply`, `check`, `update`, `repair`, and `factory-restore`.
- [x] Freeze CLI flags for source selection, output format, non-interactive mode, dry-run mode, answer files, plan files, report files, and UI mode.
- [x] Write `docs/contracts/cli-surface.md` with command, flag, input, and output expectations.
- [x] Define protocol event types for JSON Lines output.
- [x] Write `docs/contracts/lifecycle-protocol.md` with required event fields, object shapes, and `stdout` / `stderr` rules.
- [x] Define approval and warning semantics for plan generation and apply.
- [x] Freeze exit codes and their operational meanings.
- [x] Write `docs/contracts/exit-codes.md` with stable meanings and machine-handling guidance.
- [x] Define what belongs in `core` vs `pack` vs `profile` vs `catalog`.
- [x] Define pack installation rules and whether packs can depend on other packs.
- [x] Define profile semantics and which settings a profile is allowed to influence.
- [x] Write `docs/contracts/layer-model.md` with inclusion rules, dependency rules, and examples.
- [x] Define lockfile required fields and migration behavior for legacy installs.
- [x] Define manifest entry fields and retired-file representation.
- [x] Write `docs/contracts/package-state-model.md` with policy, manifest, and lockfile field expectations before writing schemas.
- [x] Define write strategies and explicitly reject unsupported merge strategies.
- [x] Write `docs/contracts/write-model.md` with ownership modes, write strategies, conflict classes, and retired-file handling.
- [x] Define how the script identifies Copilot-driven execution.
- [x] Define which visible terminal messages are stable enough to preserve and which are cosmetic only.
- [x] Write `docs/contracts/ui-agent-contract.md` with the `--ui agent` split between machine protocol and visible progress.
- [x] Define memory policy: mandatory core behavior, optional memory pack behavior, and rules for verification.
- [x] Write `docs/contracts/memory-boundary.md` with required separation between core lifecycle state and optional memory behavior.
- [x] Add at least four protocol examples: `inspect`, `plan setup`, `apply` report, and JSON Lines event stream.
- [x] Cross-check Phase 0 contract terms against `docs/lifecycle-update-plan.md` so the same word never means two different things.

### Phase 0 Validation Gate

- [x] The full Phase 0 contract packet exists in the repo under `docs/contracts/`.
- [x] A contributor unfamiliar with prior discussion can answer “what is the contract?” by reading the schemas/spec notes alone.
- [x] No critical lifecycle term is still overloaded or ambiguous.
- [x] The contract does not require broad always-on context to work.
- [x] Slice 1 can begin without reopening naming or protocol debates.

### Phase 0 Risks To Resolve

- overdesigning packs before the core exists
- conflating catalog metadata with lifecycle manifest metadata
- allowing the UI layer to leak into the machine protocol
- treating Markdown as installed-state truth

## Phase 1 - Define Product Layers And Discovery Metadata

### Phase 1 Goal

Turn the `core` / `pack` / `profile` / `catalog` model into concrete repository metadata before implementing the lifecycle engine.

### Phase 1 Deliverables

- initial pack registry design
- initial profile registry design
- catalog schema draft
- mapping from current template surfaces into the new layer model

### Phase 1 Checklist

- [x] Identify all current or planned surfaces that are always part of `core`.
- [x] Define the first pack candidates, likely including `memory`, `lean`, `review`, `research`, and `workspace-ops`.
- [x] Define initial profiles, likely `balanced`, `lean`, and `ultra-lean`.
- [x] Define how packs are represented in package metadata.
- [x] Define how profiles are represented in setup answers and lockfile state.
- [x] Define the catalog fields needed for Copilot-facing discovery.
- [x] Decide whether starter kits remain separate from packs or become a specialized pack subtype.
- [x] Decide whether catalog metadata is generated from policy, manifest, or both.

### Phase 1 Validation Gate

- [x] Every known feature can be placed cleanly in one layer.
- [x] No pack requires loading its full instructions at session start.
- [x] Profile behavior remains configuration, not content duplication.

