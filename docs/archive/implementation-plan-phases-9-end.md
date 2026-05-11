## Phase 9 - Add Optional Capability Layers

### Phase 9 Goal

Add packs, profiles, and optional memory behavior only after the lifecycle core is reliable.

### Phase 9 Deliverables

- initial pack registry implementation
- initial profile implementation
- optional memory pack design and possibly first implementation slice
- catalog artifact
- first-party tooling MCP contract and initial server/tool boundary

### Phase 9 Checklist

- [x] Implement pack metadata loading.
- [x] Implement pack selection and lockfile recording.
- [x] Implement profile selection and lockfile recording.
- [x] Implement at least one lean output profile.
- [x] Implement catalog generation.
- [x] Decide whether the first memory slice is documentation-only, metadata-only, or executable. (Decision: metadata-only, kept planned.)
- [ ] If memory pack begins implementation, keep it local-first, optional, and verification-aware.
- [ ] Define the first-party tooling MCP contract and keep its tool surface semantic, narrow, and repo-owned.
- [ ] Keep lifecycle CLI as the authority even if first-party MCP tools wrap lifecycle workflows.
- [ ] Define a first executable tooling MCP slice that works in consumer workspaces without assuming a local xanadAssistant package checkout.

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

- [x] Replace hand-maintained mirrors with generated outputs where safe. (`install-manifest.json` and `catalog.json` are both generated; `check_manifest_freshness.py` enforces both.)
- [x] Keep only necessary differences between plugin, template, developer workspace, and compatibility formats. (Ownership and strategy differences are fully policy-driven; no hand-maintained format forks exist.)
- [x] Update contributor docs for the new flow. (`scripts/generate.py` is the single regeneration command; `agents/lifecycle-planning.agent.md` and `template/prompts/setup.md` cover the contributor workflow.)
- [x] Replace redundant inventories with links to generated machine-readable artifacts. (Stale backlog slices updated; `catalog.json` and `install-manifest.json` are the authoritative inventories.)
- [x] Ensure CI checks derived-state freshness. (`.github/workflows/ci.yml` runs unit tests and manifest+catalog freshness on every push and PR.)

### Phase 10 Validation Gate

- [x] A contributor can change one canonical surface and run one generation command to refresh derived outputs. (`python3 scripts/generate.py` regenerates manifest and catalog from policy and registries.)
- [x] Repo structure communicates source of truth clearly.

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
- [ ] First-party MCP tools avoid arbitrary shell passthrough and document every privileged workflow they expose.

### Memory Checklist

- [x] Core lifecycle does not depend on optional memory infrastructure.
- [x] Memory v1 scope, routing, and verification rules are defined. (`docs/contracts/memory-v1.md`)
- [ ] Durable memory uses citations or directly verifiable source anchors.
- [ ] Memory state can be expired, repaired, or discarded safely.
- [ ] Repo-scoped memory is kept separate from user-wide preference memory.

### Release Checklist

- [x] Version metadata is bumped consistently.
- [x] Manifest regeneration is part of release prep. (`python3 scripts/generate.py`)
- [x] Stale-consumer fixture upgrade passes before release. (`StaleConsumerFixtureConvergenceTests` in `tests/test_convergence_and_network.py`)
- [x] Lockfile migration coverage is current. (`LockfileMigrationTests` in `tests/test_xanadAssistant_inspect.py`)
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
- [x] add `docs/contracts/tool-mcp-boundary.md`
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

- [x] implement backup
- [x] implement strategy execution
- [x] implement lockfile write
- [x] implement validation

### Slice 6 - Copilot Integration

- [x] script-driven Setup agent
- [x] prompt and routing updates
- [x] branded `--ui agent`

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
- current plugin marketplace behavior if `xanadAssistant` will ship through more than one marketplace path

## Definition Of Ready To Start Coding

Coding should begin only when the following are true:

- [x] Phase 0 contracts are written down in repo artifacts, not just chat.
- [x] Phase 1 layer model is clear enough that new functionality can be placed without debate.
- [x] Phase 2 generated manifest path is agreed.
- [x] At least one fixture consumer repo strategy is chosen.
- [ ] The team accepts the anti-bloat rules as a hard constraint.

## Definition Of Done For The Program

The implementation program is complete when:

- [x] setup, update, repair, and factory restore all run through the same lifecycle engine (`build_execution_result` → `build_plan_result` → `execute_apply_plan`; tested in `test_factory_restore_applies_customized_workspace_and_returns_clean_state`)
- [x] the package manifest is authoritative and generated
- [x] the installed-state lockfile is structured and validated (`xanadAssistant-lock.schema.json`; validated in `test_lockfile_written_by_apply_validates_against_schema`; migration coverage in `LockfileMigrationTests`)
- [x] Copilot can drive the flow through a machine-readable protocol (`--json` and `--json-lines` flags on all commands; interview/plan/apply separation; machine-readable exit codes)
- [x] the visible terminal experience is branded but optional and non-blocking (`--ui quiet/agent/tui`; `emit_agent_progress` with ANSI color; suppressed by `NO_COLOR`; non-blocking on missing tty)
- [x] optional packs and profiles do not bloat the default install
- [x] stale consumer installs can be upgraded and repaired reliably (`StaleConsumerFixtureConvergenceTests` in `tests/test_convergence_and_network.py`)
- [x] contributor authoring flow has one clear source of truth per managed surface (`scripts/generate.py` regenerates manifest and catalog; `check_manifest_freshness.py` enforces freshness in CI)
