## Phase 2 - Generate Package Truth

### Phase 2 Goal

Make the package authoritative through a small hand-authored policy file and generated machine-readable artifacts.

### Phase 2 Deliverables

- `template/setup/install-policy.schema.json`
- `template/setup/install-policy.json`
- `template/setup/install-manifest.schema.json`
- generated `template/setup/install-manifest.json`
- `template/setup/xanad-assistant-lock.schema.json`
- manifest generator under `scripts/lifecycle/`

### Phase 2 Checklist

- [x] Define canonical source roots.
- [x] Define target path rules per surface.
- [x] Define ownership defaults per surface.
- [x] Define conditional inclusion rules.
- [x] Define token replacement rules.
- [x] Define chmod rules.
- [x] Define retired-file rules.
- [x] Implement manifest generation from policy plus filesystem scan.
- [x] Compute full hashes for all managed sources.
- [x] Fail generation when a source lacks policy coverage.
- [x] Decide how generated mirrors and indexes tie into manifest generation.

### Phase 2 Validation Gate

- [x] Manifest generation is deterministic.
- [x] A managed source add, move, or remove breaks CI unless policy and manifest are updated.
- [x] Generated output is machine-diffable and stable.

### Phase 2 Test Checklist

- [x] schema validation test
- [x] source existence test
- [x] unmanaged source detection test
- [x] retired file declaration test
- [x] hash stability test

## Phase 3 - Implement Read-Only Lifecycle Surfaces

### Phase 3 Goal

Build the read-only engine first so inspection, drift detection, and question generation work before any file writes exist.

### Phase 3 Deliverables

- `xanad-assistant.py` or `scripts/lifecycle/xanad_assistant.py` skeleton
- source resolver for local package roots first
- workspace inspector
- legacy install reader
- `inspect`
- `check`
- `interview`
- `--ui quiet`
- initial `--ui agent`

### Phase 3 Checklist

- [x] Resolve package from `--package-root`.
- [x] Load policy, manifest, and schemas.
- [x] Detect repo state, Git state, existing instructions, prompts, agents, skills, hooks, MCP config, workspace files, and prior version state.
- [x] Parse legacy `.github/copilot-version.md` when present.
- [x] Parse existing future lockfile when present.
- [x] Implement structured `inspect` output.
- [x] Implement `check` classification: missing, stale, malformed, skipped, retired, unmanaged, unknown.
- [x] Implement question emission based on interview schema.
- [x] Emit JSON and JSON Lines outputs.
- [x] Emit concise `--ui agent` preflight summaries to the visible terminal.

### Phase 3 Validation Gate

- [x] No command in this phase writes to the workspace.
- [x] `inspect` and `check` produce actionable structured output on clean, stale, and malformed fixtures.
- [x] Interview output can drive a future non-interactive plan step without conversational heuristics.

### Phase 3 Test Checklist

- [x] fixture: clean workspace
- [x] fixture: stale install
- [x] fixture: malformed legacy version file
- [x] fixture: plugin-backed vs all-local installs
- [x] fixture: unmanaged custom files present

## Phase 4 - Implement Planning

### Phase 4 Goal

Generate complete no-write plans for setup, update, repair, and factory restore.

### Phase 4 Starting Point

The current validated inputs for Phase 4 are:

- contract docs and protocol examples under `docs/contracts/`
- deterministic policy and manifest generation
- metadata registries for packs, profiles, and catalog discovery
- read-only `inspect`, `check`, and `interview`
- manifest freshness coverage
- temporary-workspace fixture strategy for unit-level planning tests

The main missing behavior has shifted from planning to execution: `plan setup`, `plan update`, `plan repair`, and `plan factory-restore` now compute intended writes, approval state, ownership resolution for current core surfaces plus plugin-backed agent and skill skips and opt-in local hook and MCP planning, token substitution summaries for tokenized files, deterministic backup path planning, planned lockfile output, validated answer-driven profile and pack selection, conflict summaries, and serialized no-write plan output for the currently modeled surfaces.

### Phase 4 Deliverables

- `plan setup`
- `plan update`
- `plan repair`
- `plan factory-restore`
- risk summary model
- approval summary model

### Phase 4 Checklist

- [x] Implement ownership resolution.
- [x] Implement per-surface install selection.
- [x] Implement token-substitution planning.
- [x] Implement retired-file planning.
- [x] Implement MCP and hook atomicity planning.
- [x] Implement backup target planning.
- [x] Implement lockfile write planning.
- [x] Implement profile and pack selection planning.
- [x] Implement warning and conflict classification.
- [x] Implement machine-readable diff summary for the plan.
- [x] Implement plan serialization for later apply.

### Phase 4 Validation Gate

- [x] A plan contains every intended write and no implicit writes.
- [x] Risk classification is understandable from the plan alone.
- [x] Plans are stable when rerun against unchanged state.

### Phase 4 Test Checklist

- [x] plan setup from empty consumer repo
- [x] plan update from stale version
- [x] plan repair from malformed legacy install
- [x] plan factory-restore from locally customized repo
- [x] plan with plugin-backed agents/skills and local hooks/MCP

## Phase 5 - Implement Apply, Repair, And Lockfile Writing

### Phase 5 Goal

Build the write engine with backups, strategy execution, lockfile output, and validation.

Current validated scope in this phase: public `apply` now drives the setup slice end to end for the currently supported setup actions. Top-level `update`, `repair`, and `factory-restore` also execute end to end for the currently modeled surfaces through the same planning and write engine. The write path creates backup roots, writes add/replace setup targets, renders tokenized prompt content, performs deterministic `merge-json-object` writes for MCP config, preserves explicit user-owned Markdown blocks during managed instruction updates, backs up and purges unmanaged lookalikes during `factory-restore`, writes structured lockfile state, generates `.github/copilot-version.md`, emits apply reports, supports `--report-out`, and validates the resulting workspace with `check`.

### Phase 5 Deliverables

- backup creation
- replace/copy/merge/token/chmod/archive behaviors
- lockfile writer
- generated `.github/copilot-version.md` summary
- post-apply validation
- repair path for legacy malformed installs

### Phase 5 Checklist

- [x] Create timestamped backup before the first write.
- [x] Implement `replace-verbatim`.
- [x] Implement `copy-if-missing`.
- [x] Implement `merge-json-object`.
- [x] Implement `preserve-marked-markdown-blocks`.
- [x] Implement `token-replace`.
- [x] Implement `archive-retired` and `report-retired`.
- [x] Implement chmod application.
- [x] Implement structured lockfile writing.
- [x] Implement generated Markdown summary writing.
- [x] Implement post-write validation and failure reporting.
- [x] Implement legacy repair rewrite behavior.

### Phase 5 Validation Gate

- [x] A failed validation leaves the workspace in an understandable state with backup intact.
- [x] Lockfile content fully reflects applied state for the current setup slice.
- [x] Generated Markdown summary is readable but not authoritative.

### Phase 5 Test Checklist

- [x] backup creation test
- [x] setup apply end-to-end test
- [x] apply JSON Lines and `--ui agent` test
- [x] focused `merge-json-object` apply test
- [x] focused `preserve-marked-markdown-blocks` apply test
- [x] generated summary writing test
- [x] end-to-end `repair`
- [x] end-to-end `factory-restore`
- [x] strategy tests for each write strategy
- [x] lockfile schema validation test
- [x] legacy migration repair test
- [x] validation failure behavior test

