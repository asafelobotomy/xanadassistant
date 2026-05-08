# Xanad Assistant Memory v1 Contract

This document defines the first operational memory contract for xanad-assistant.

## Status

This file is normative for memory v1.

Memory v1 is metadata-only and workflow-oriented. It defines scopes, routing, and
verification rules. It does not require a retrieval engine, embeddings, ranking,
or always-on runtime services.

Memory v1 also standardizes a lean durable format: plain Markdown, one durable
repo file by default, and optional topic expansion only when the main file would
otherwise become noisy.

## Relationship To Core Lifecycle

This contract refines the boundary in `docs/contracts/memory-boundary.md`.

- Lifecycle correctness must not depend on memory state.
- Memory may improve recall and contributor consistency.
- Memory must not replace policy, manifest, lockfile, plan output, report output,
  or other authoritative lifecycle artifacts.
- A default install must still work without any memory pack surface.

## Core Philosophy

- Local-first by default.
- Optional by design.
- Citation-backed when durable.
- Safe to discard, rebuild, or expire.
- Separate by scope rather than by speculative always-on automation.
- Prefer simple Markdown over specialized schemas.
- Keep always-read durable memory lean.

## Memory Tiers

| Scope | Location | Lifetime | Purpose | Authority |
|------|----------|----------|---------|-----------|
| Session | `/memories/session/` | Current conversation or task | In-progress notes and temporary context | Non-authoritative |
| User | `/memories/` | Cross-repo, user-wide | Personal preferences and durable individual conventions | Non-authoritative |
| Repo inbox | `/memories/repo/` | Machine-local, intermediate | Candidate repo facts not yet promoted | Non-authoritative |
| Repo durable | `docs/memory.md` | Project lifetime | Validated project conventions, decisions, and gotchas | Git-tracked reference |

## Routing Rules

Use the smallest scope that matches the fact.

- Current task notes, temporary hypotheses, and in-flight reminders belong in session memory.
- Cross-repo user preferences belong in user memory.
- Candidate repo facts discovered during implementation or review belong in repo inbox memory first.
- Only validated, durable, repo-specific facts should be promoted to `docs/memory.md`.

## Durable Memory Admission Rules

A fact may be promoted into durable repo memory only when all of the following are true:

- It is likely to matter again in future implementation, review, or release work.
- It is stable enough to outlive the current task.
- It is directly verifiable from repository state or an explicit project decision.
- It is not already better represented as a contract, schema, test, or generated artifact.

The preferred source anchors are:

- contracts
- tests
- schemas
- canonical source files
- explicit user decisions recorded in the repo

## Durable Memory Schema

When `docs/memory.md` is introduced, it should use a simple structured format.

### Format Rule

- Durable repo memory should be plain Markdown.
- The default durable shape is one file: `docs/memory.md`.
- Additional topic files should only be introduced when the main file becomes too
    large or too noisy to scan quickly.
- Topic files are optional support files, not the default starting structure.

### Leanness Rule

- `docs/memory.md` should stay concise and scannable.
- Prefer short table rows or short bullets over long prose blocks.
- If an explanation needs multiple paragraphs, the source document should hold
    the detail and memory should link to it.
- Durable memory should contain facts worth reusing, not tutorials or task logs.

### Template Rule

The first durable file should use stable sections rather than ad hoc headings.
The minimum expected sections are:

- Architecture Decisions
- Known Gotchas
- Conventions

### Architecture Decisions

| Date | Decision | Rationale | Source |
|------|----------|-----------|--------|

### Known Gotchas

| Date | Pattern | Context | Source |
|------|---------|---------|--------|

### Conventions

| Date | Convention | Applies To | Source |
|------|-----------|------------|--------|

## Verification Rules

- Durable entries should include a concrete source reference.
- Memory-derived advice must remain falsifiable against repository state.
- If a durable fact becomes stale, the canonical contract, test, or code wins.
- Memory may summarize authoritative truth, but it must not silently override it.

## Metadata Rules

- Tags are deferred from memory v1.
- Frontmatter is not required for `docs/memory.md`.
- Section placement plus source references are sufficient organization for v1.
- If topic files are added later, they may adopt lightweight metadata, but v1 does
    not require it.

## Non-Goals For V1

The following are explicitly out of scope for memory v1:

- always-on heartbeat or pulse infrastructure
- lockfiles, journals, or background daemons for every tool call
- embedding or ranking systems
- hidden memory-dependent lifecycle behavior
- multiple git-tracked memory files split by abstract persona categories
- mandatory tags or taxonomy design before real usage proves the need

## Pack Delivery Rule

If a memory pack becomes executable later, it must remain optional.

- No mandatory runtime dependency may be added to the lifecycle core.
- Memory pack surfaces must be installable or omitted without affecting setup,
  inspect, update, repair, or factory-restore correctness.
- Any memory tooling should expose narrow, semantic workflows rather than generic,
  opaque persistence.

## Promotion Workflow

The intended workflow is:

1. Capture in-flight repo facts in repo inbox memory during a task.
2. Validate the fact against code, tests, contracts, or explicit project decisions.
3. Promote only stable facts into durable repo memory.
4. Prefer improving an existing contract or test instead of duplicating the same rule in memory.

## Initial Durable File Expectation

The initial `docs/memory.md` file should:

- be useful without additional tooling
- be readable in a normal diff or code review
- avoid frontmatter unless a concrete workflow needs it later
- avoid tags unless retrieval or filtering needs prove they help more than they cost

## Acceptance Criteria For V1

Memory v1 is complete when:

- the boundary between lifecycle truth and memory is explicit
- scope routing is explicit
- durable memory requires verification
- memory can expire or be discarded without breaking lifecycle correctness
- no always-on runtime machinery is required