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
- [x] Implement GitHub release resolution.
- [x] Implement explicit ref resolution.
- [x] Implement package caching.
- [x] Implement package integrity checks where metadata supports them.
- [x] Implement stale-version upgrade behavior.
- [x] Implement incomplete-install recovery behavior.

### Phase 6 Validation Gate

- [x] A stale fixture upgrades cleanly.
- [x] A malformed fixture repairs cleanly.
- [x] A customized fixture preserves user-owned content according to policy.
- [x] Release and local path installs converge on the same final state. (Covered by `StaleConsumerFixtureConvergenceTests.test_fresh_and_updated_lockfiles_converge` and by `GitHubSourceResolutionNetworkTests.test_local_and_github_ref_installs_converge` when network tests are enabled.)

## Phase 7 - Integrate Copilot-Facing Workflow

### Phase 7 Goal

Make the script the lifecycle authority for Copilot-facing setup and updates.

### Phase 7 Deliverables

- updated Setup agent contract
- prompt and handoff updates
- removal of prose-driven file inventory behavior
- trigger phrase and routing updates

### Phase 7 Checklist

- [x] Update the Setup agent to call the script rather than interpret manifests itself.
- [x] Keep the Setup agent responsible for conversation and approvals only.
- [x] Replace prose lifecycle steps with script invocation guidance.
- [x] Add or update prompt files only where they improve focused flows.
- [x] Ensure trigger phrases align with the new lifecycle commands.
- [x] Verify handoffs still make sense after lifecycle centralization.

### Phase 7 Validation Gate

- [x] Copilot can run setup using the script path alone.
- [x] Setup behavior no longer depends on remembering file lists from Markdown.
- [x] The user sees one coherent lifecycle experience.

## Phase 8 - Polish The Agent UI Surface

### Phase 8 Goal

Deliver the visible terminal experience for humans without compromising machine efficiency.

### Phase 8 Deliverables

- polished `--ui agent`
- compact visual identity
- stable phase naming
- receipts and progress lines

### Phase 8 Checklist

- [x] Finalize phase labels: Preflight, Interview, Plan, Apply, Validate, Receipt.
- [x] Finalize `Waiting on Copilot` state messaging.
- [x] Finalize concise progress summaries for writes and validation.
- [x] Add color only as optional enhancement with plain-text fallback.
- [x] Ensure JSON Lines remain stdout-only and free of decorative text.
- [x] Ensure visible terminal output remains readable without full-screen TUI assumptions.

### Phase 8 Validation Gate

- [x] Copilot does not need to parse visible cosmetic output.
- [x] The human-visible terminal feels intentional without adding operational fragility.
- [x] Logs remain useful in plain-text environments.

