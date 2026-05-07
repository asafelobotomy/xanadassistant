# Xanad Assistant Implementation Plan

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
- Phase 5 has started with a validated public execution slice: `apply` now performs setup planning plus managed writes for the currently supported setup actions, creates backup roots, renders tokenized prompt output, performs deterministic `merge-json-object` writes for MCP config while preserving unrelated keys, preserves explicit user-owned Markdown blocks and the `## §10 - Project-Specific Overrides` section in managed instructions, writes structured lockfile state, generates `.github/copilot-version.md` as a readable derivative summary, emits `apply-report` JSON Lines events, supports `--report-out`, and validates the resulting workspace with `check`. Top-level `update`, `repair`, and `factory-restore` now execute the existing plan and apply path for the currently modeled surfaces, and `factory-restore` now backs up and purges unmanaged lookalikes before reinstalling managed files. Retired-file handling remains pending.
- Phase 9 has partial groundwork only: pack and profile registries exist, the catalog artifact exists, and read-only commands load discovery metadata, but optional capability behavior is not implemented yet.
- Phase 6 remains unstarted for release/ref resolution, cache behavior, integrity checks, stale-upgrade handling, and incomplete-install recovery, and Phases 7, 8, and 10 remain unstarted for Copilot integration, UI polish, and repo cleanup.
- The current fixture consumer strategy is ephemeral temporary workspaces in unit tests rather than committed fixture repositories. That is sufficient for current Phases 2 and 3 validation, but not for later end-to-end upgrade and restore coverage.
- Checklist state below should track implemented behavior and verified documentation, not intended sequence alone.

## Current Remaining Work

The remaining implementation work is now concentrated in the unfinished execution behaviors and the later integration phases.

### Immediate Remaining Work

- Finish the remaining Phase 5 write strategies: `copy-if-missing` and retired-file handling.
- Make validation failure reporting leave an understandable post-failure state with backups intact.
- Expand Phase 5 tests beyond the current setup-apply slice to cover remaining strategies, lockfile schema validation, repair behavior, factory-restore behavior, and validation-failure paths.

### Next Execution Work

- Implement release/ref source resolution, package caching, integrity checks, stale-upgrade handling, and incomplete-install recovery.
- Introduce committed fixture repos or equivalent stable end-to-end fixtures before relying on upgrade and restore gates.

## Phase 0 - Freeze The Contracts

### Phase 0 Goal

Define the product-layer, protocol, and schema contracts tightly enough that the rest of the implementation can proceed without semantic churn.

### Phase 0 Deliverables

- CLI command matrix for `xanad-assistant.py`
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
- [ ] Implement `copy-if-missing`.
- [x] Implement `merge-json-object`.
- [x] Implement `preserve-marked-markdown-blocks`.
- [x] Implement `token-replace`.
- [ ] Implement `archive-retired` and `report-retired`.
- [x] Implement chmod application.
- [x] Implement structured lockfile writing.
- [x] Implement generated Markdown summary writing.
- [x] Implement post-write validation and failure reporting.
- [ ] Implement legacy repair rewrite behavior.

### Phase 5 Validation Gate

- [ ] A failed validation leaves the workspace in an understandable state with backup intact.
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
- [ ] strategy tests for each write strategy
- [ ] lockfile schema validation test
- [ ] legacy migration repair test
- [ ] validation failure behavior test

## Phase 6 - Implement Update And Factory Restore End-To-End

### Phase 6 Goal

Complete the transactional lifecycle path for real setup, update, repair, and restore usage.

### Phase 6 Deliverables

- end-to-end `update`
- end-to-end `repair`
- end-to-end `factory-restore`
- source resolution for releases and refs
- package cache behavior

### Phase 6 Checklist

- [x] Implement `update` as inspect plus plan plus approved apply for the current modeled surfaces.
- [x] Implement `repair` as inspect plus repair plan plus apply for the current modeled surfaces.
- [x] Implement `factory-restore` as backup plus purge plus reinstall for the current modeled surfaces.
- [ ] Implement GitHub release resolution.
- [ ] Implement explicit ref resolution.
- [ ] Implement package caching.
- [ ] Implement package integrity checks where metadata supports them.
- [ ] Implement stale-version upgrade behavior.
- [ ] Implement incomplete-install recovery behavior.

### Phase 6 Validation Gate

- [ ] A stale fixture upgrades cleanly.
- [ ] A malformed fixture repairs cleanly.
- [ ] A customized fixture preserves user-owned content according to policy.
- [ ] Release and local path installs converge on the same final state.

## Phase 7 - Integrate Copilot-Facing Workflow

### Phase 7 Goal

Make the script the lifecycle authority for Copilot-facing setup and updates.

### Phase 7 Deliverables

- updated Setup agent contract
- prompt and handoff updates
- removal of prose-driven file inventory behavior
- trigger phrase and routing updates

### Phase 7 Checklist

- [ ] Update the Setup agent to call the script rather than interpret manifests itself.
- [ ] Keep the Setup agent responsible for conversation and approvals only.
- [ ] Replace prose lifecycle steps with script invocation guidance.
- [ ] Add or update prompt files only where they improve focused flows.
- [ ] Ensure trigger phrases align with the new lifecycle commands.
- [ ] Verify handoffs still make sense after lifecycle centralization.

### Phase 7 Validation Gate

- [ ] Copilot can run setup using the script path alone.
- [ ] Setup behavior no longer depends on remembering file lists from Markdown.
- [ ] The user sees one coherent lifecycle experience.

## Phase 8 - Polish The Agent UI Surface

### Phase 8 Goal

Deliver the visible terminal experience for humans without compromising machine efficiency.

### Phase 8 Deliverables

- polished `--ui agent`
- compact visual identity
- stable phase naming
- receipts and progress lines

### Phase 8 Checklist

- [ ] Finalize phase labels: Preflight, Interview, Plan, Apply, Validate, Receipt.
- [ ] Finalize `Waiting on Copilot` state messaging.
- [ ] Finalize concise progress summaries for writes and validation.
- [ ] Add color only as optional enhancement with plain-text fallback.
- [ ] Ensure JSON Lines remain stdout-only and free of decorative text.
- [ ] Ensure visible terminal output remains readable without full-screen TUI assumptions.

### Phase 8 Validation Gate

- [ ] Copilot does not need to parse visible cosmetic output.
- [ ] The human-visible terminal feels intentional without adding operational fragility.
- [ ] Logs remain useful in plain-text environments.

## Phase 9 - Add Optional Capability Layers

### Phase 9 Goal

Add packs, profiles, and optional memory behavior only after the lifecycle core is reliable.

### Phase 9 Deliverables

- initial pack registry implementation
- initial profile implementation
- optional memory pack design and possibly first implementation slice
- catalog artifact

### Phase 9 Checklist

- [x] Implement pack metadata loading.
- [ ] Implement pack selection and lockfile recording.
- [ ] Implement profile selection and lockfile recording.
- [ ] Implement at least one lean output profile.
- [ ] Implement catalog generation.
- [ ] Decide whether the first memory slice is documentation-only, metadata-only, or executable.
- [ ] If memory pack begins implementation, keep it local-first, optional, and verification-aware.

### Phase 9 Validation Gate

- [x] The core install remains small when no optional packs are selected.
- [x] Packs do not force always-on instruction growth.
- [x] Profile changes alter behavior through configuration, not duplicated instructions.

## Phase 10 - Simplify Repo Structure And Contributor Flow

### Phase 10 Goal

Remove hand-maintained duplication and make canonical authoring obvious.

### Phase 10 Deliverables

- generated mirrors where practical
- contributor workflow updates
- release flow updates
- documentation cleanup

### Phase 10 Checklist

- [ ] Replace hand-maintained mirrors with generated outputs where safe.
- [ ] Keep only necessary differences between plugin, template, developer workspace, and compatibility formats.
- [ ] Update contributor docs for the new flow.
- [ ] Replace redundant inventories with links to generated machine-readable artifacts.
- [ ] Ensure CI checks derived-state freshness.

### Phase 10 Validation Gate

- [ ] A contributor can change one canonical surface and run one generation command to refresh derived outputs.
- [ ] Repo structure communicates source of truth clearly.

## Cross-Phase Checklists

### Context Discipline Checklist

- [x] No new giant always-on instruction file added.
- [ ] Every large reusable workflow becomes a skill, pack, or prompt, not a base instruction block.
- [ ] Forked skill context is considered for large or noisy workflows.
- [ ] Tool sets remain scoped; avoid enabling irrelevant tools by default.
- [ ] The system stays below practical tool overload limits.

### Security Checklist

- [ ] Hook scripts are reviewed and minimally privileged.
- [ ] MCP servers are trusted explicitly and documented.
- [ ] Secrets are never hardcoded in hook scripts or MCP configs.
- [ ] Network and file-system assumptions are clear for local and sandboxed operation.
- [ ] Auto-approval assumptions are explicit and conservative by default.

### Memory Checklist

- [x] Core lifecycle does not depend on optional memory infrastructure.
- [ ] Durable memory uses citations or directly verifiable source anchors.
- [ ] Memory state can be expired, repaired, or discarded safely.
- [ ] Repo-scoped memory is kept separate from user-wide preference memory.

### Release Checklist

- [ ] Version metadata is bumped consistently.
- [ ] Manifest regeneration is part of release prep.
- [ ] Stale-consumer fixture upgrade passes before release.
- [ ] Lockfile migration coverage is current.
- [x] Catalog, pack, and profile metadata remain in sync.

## Suggested Initial Backlog By Slice

### Slice 1 - Contract Artifacts Only

- [x] add `docs/contracts/cli-surface.md`
- [x] add `docs/contracts/lifecycle-protocol.md`
- [x] add `docs/contracts/exit-codes.md`
- [x] add `docs/contracts/layer-model.md`
- [x] add `docs/contracts/package-state-model.md`
- [x] write schema stubs

- [x] add `docs/contracts/write-model.md`
- [x] add `docs/contracts/memory-boundary.md`
- [x] add `docs/contracts/ui-agent-contract.md`
- [x] add protocol fixture examples under `docs/contracts/examples/`

### Slice 2 - Generated Manifest

- [x] add install policy
- [x] add manifest generator
- [x] add manifest validation tests

### Slice 3 - Read-Only Engine

- [x] add script skeleton
- [x] implement inspect
- [x] implement check
- [x] implement interview emission

### Slice 4 - Planning Engine

- [x] implement setup planning
- [x] implement update planning
- [x] implement repair planning
- [x] implement factory-restore planning

### Slice 5 - Apply Engine

- [ ] implement backup
- [ ] implement strategy execution
- [ ] implement lockfile write
- [ ] implement validation

### Slice 6 - Copilot Integration

- [ ] script-driven Setup agent
- [ ] prompt and routing updates
- [ ] branded `--ui agent`

## Source Packet

These sources should remain in scope while implementing. They are grouped by confidence and practical relevance.

### Primary Product And Platform Sources

- `docs/lifecycle-update-plan.md`
- VS Code customization overview: <https://code.visualstudio.com/docs/copilot/customization/overview>
- VS Code custom instructions: <https://code.visualstudio.com/docs/copilot/customization/custom-instructions>
- VS Code custom agents: <https://code.visualstudio.com/docs/copilot/customization/custom-agents>
- VS Code agent skills: <https://code.visualstudio.com/docs/copilot/customization/agent-skills>
- VS Code prompt files: <https://code.visualstudio.com/docs/copilot/customization/prompt-files>
- VS Code hooks: <https://code.visualstudio.com/docs/copilot/customization/hooks>
- VS Code plugins: <https://code.visualstudio.com/docs/copilot/customization/agent-plugins>
- VS Code MCP servers: <https://code.visualstudio.com/docs/copilot/customization/mcp-servers>
- VS Code tools: <https://code.visualstudio.com/docs/copilot/agents/agent-tools>
- VS Code planning: <https://code.visualstudio.com/docs/copilot/agents/planning>
- VS Code memory: <https://code.visualstudio.com/docs/copilot/agents/memory>
- GitHub Copilot CLI plugin reference: <https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference#pluginjson>

### Primary Research Sources

- Brevity constraints paper: <https://arxiv.org/abs/2604.00025>
- LLM response length paper: <https://aclanthology.org/2025.findings-acl.1125/>
- Mem0 long-term memory paper: <https://arxiv.org/abs/2504.19413>
- GitHub engineering write-up on agentic memory: <https://github.blog/ai-and-ml/github-copilot/building-an-agentic-memory-system-for-github-copilot/>
- GitHub Copilot Memory docs: <https://docs.github.com/en/copilot/how-tos/use-copilot-agents/copilot-memory>

### Secondary Context Sources

- Awesome Copilot: <https://github.com/github/awesome-copilot>
- MemPalace: <https://github.com/MemPalace/mempalace>
- Caveman: <https://github.com/JuliusBrussee/caveman>
- Prompt congestion article: <https://dev.to/sai_samineni/prompt-congestion-the-hidden-cost-of-overloading-ai-context-1ngf>

### Additional Sources To Pull During Implementation

These are not blocking before implementation starts, but should be fetched when the corresponding work begins.

- VS Code MCP configuration reference
- VS Code security and trust-and-safety docs
- VS Code context engineering guide
- agentskills.io specification pages used by `context: fork`
- any official GitHub docs for organization-level custom agents or instructions that affect future distribution
- current plugin marketplace behavior if `xanad-assistant` will ship through more than one marketplace path

## Definition Of Ready To Start Coding

Coding should begin only when the following are true:

- [x] Phase 0 contracts are written down in repo artifacts, not just chat.
- [x] Phase 1 layer model is clear enough that new functionality can be placed without debate.
- [x] Phase 2 generated manifest path is agreed.
- [x] At least one fixture consumer repo strategy is chosen.
- [ ] The team accepts the anti-bloat rules as a hard constraint.

## Definition Of Done For The Program

The implementation program is complete when:

- [ ] setup, update, repair, and factory restore all run through the same lifecycle engine
- [x] the package manifest is authoritative and generated
- [ ] the installed-state lockfile is structured and validated
- [ ] Copilot can drive the flow through a machine-readable protocol
- [ ] the visible terminal experience is branded but optional and non-blocking
- [x] optional packs and profiles do not bloat the default install
- [ ] stale consumer installs can be upgraded and repaired reliably
- [ ] contributor authoring flow has one clear source of truth per managed surface
