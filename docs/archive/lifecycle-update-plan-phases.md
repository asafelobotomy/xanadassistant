## Implementation Phases

### Phase 1 - Freeze The Contract

Deliverables:

- Finalize command names, output modes, exit codes, and JSON Lines event types.
- Add `template/setup/install-policy.schema.json`.
- Add `template/setup/install-manifest.schema.json`.
- Add lockfile schema for `.github/xanadAssistant-lock.json`.
- Document supported strategies and ownership modes.
- Decide release-source defaults and branch/local development flags.

Definition of done:

- The lifecycle protocol can be implemented and tested without guessing semantics.

### Phase 2 - Generate Package Truth

Deliverables:

- Add `template/setup/install-policy.json`.
- Add manifest generator under `scripts/lifecycle/`.
- Generate `template/setup/install-manifest.json` from policy plus filesystem state.
- Add tests for schema validity, source existence, stable hashes, and unmanaged source detection.

Definition of done:

- CI fails when a managed source file is added, removed, or moved without manifest/policy coverage.

### Phase 3 - Build Inspect, Check, And Interview

Deliverables:

- Add `xanadAssistant.py` or `scripts/lifecycle/xanadAssistant.py` skeleton.
- Implement package resolution for local `--package-root` first.
- Implement workspace inspector.
- Implement lockfile parser and legacy version-file reader.
- Implement `inspect` and `check` with JSON output.
- Implement interview schema emission.
- Add `--ui quiet` and initial `--ui agent` output.

Definition of done:

- Copilot can run the script, receive structured workspace state and questions, and no files are written.

### Phase 4 - Build Planning

Deliverables:

- Implement `plan setup`, `plan update`, `plan repair`, and `plan factory-restore`.
- Implement ownership detection and defaults.
- Implement MCP and hook atomicity planning.
- Implement retired-file planning.
- Implement answer-file validation.
- Implement risk summary and approval summary.

Definition of done:

- A complete write plan can be generated and reviewed without touching the workspace.

### Phase 5 - Build Apply And Repair

Deliverables:

- Implement backup creation.
- Implement replace, copy-if-missing, JSON merge, marked Markdown preservation, token replacement, chmod, retired archive/report.
- Implement lockfile writes.
- Implement generated `.github/copilot-version.md` summary.
- Implement validation after writes.
- Implement repair of malformed legacy installs.

Definition of done:

- A stale or malformed fixture can be repaired with backups, structured state, and validation.

### Phase 6 - Build Update And Factory Restore

Deliverables:

- Implement `update` as inspect plus plan plus approved apply.
- Implement `factory-restore` as backup plus clean managed reinstall.
- Add release/package source support for GitHub releases and explicit refs.
- Add package cache and source verification where metadata allows.

Definition of done:

- A simulated old consumer install updates cleanly to the current package with no missing managed files.

### Phase 7 - Integrate Copilot-Facing Customizations

Deliverables:

- Update the Setup agent to treat the script as the lifecycle authority.
- Replace prose file-copy instructions with script invocation instructions.
- Ensure agent descriptions contain trigger phrases for setup, update, repair, factory restore, and xanadAssistant lifecycle operations.
- Add prompts or skills only where they improve focused workflows; avoid always-loaded instruction sprawl.

Definition of done:

- Copilot setup behavior is driven by the script protocol, not by manually interpreting file inventories.

### Phase 8 - Improve The Agent UI Surface

Deliverables:

- Polish `--ui agent` visible progress.
- Add compact `xanadAssistant` branding.
- Add phase summaries: Preflight, Interview, Plan, Apply, Validate, Receipt.
- Add terminal messages for `Waiting on Copilot`, `Applying approved plan`, and `Validation complete`.
- Ensure color is optional and disabled automatically when unsupported.
- Keep JSON Lines stable and free of decorative text.

Definition of done:

- The terminal feels like a branded lifecycle companion while Copilot still uses the efficient protocol.

### Phase 9 - Simplify Repo Structure

Deliverables:

- Replace hand-maintained mirrors with generated mirrors where practical.
- Keep only necessary differences between template, developer workspace, plugin packaging, and compatibility targets.
- Update contributor docs with the new authoring and release flow.
- Retire redundant Markdown inventories or make them link to generated manifests.

Definition of done:

- Contributors can update canonical sources and run one generation command to refresh derived surfaces.

## Minimum Viable First Slice

The smallest valuable implementation should include:

- local package-root support only
- policy schema
- generated manifest
- lockfile schema
- `inspect`
- `check`
- `interview` question emission
- `plan setup`
- `--ui quiet`
- `--ui agent`
- tests for manifest coverage and check output

This proves the contract before writing files.

## First Build Order

1. Define schemas and protocol fixtures.
2. Write manifest policy and generator.
3. Add fixture consumer repositories for clean, stale, malformed, and locally customized installs.
4. Implement read-only `inspect` and `check`.
5. Implement interview question emission.
6. Implement plan generation.
7. Implement backups and apply strategies.
8. Implement structured lockfile and generated Markdown summary.
9. Add update, repair, and factory restore commands.
10. Integrate the Setup agent and retire prose lifecycle instructions.

## Final North Star

`xanadAssistant` should be a Copilot-operated lifecycle installer for agent customizations, with a human-friendly terminal presence and a deterministic engine underneath.

The human-visible terminal is transparency and personality. The machine-readable protocol is the source of truth.
