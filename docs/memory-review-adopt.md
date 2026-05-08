# Memory Review — What To Keep From The Predecessor Template

This note extracts the useful parts of the predecessor `copilot-instructions-template`
memory model and separates them from the parts xanad-assistant should avoid.

## Keep

### Git-tracked durable repo memory

The strongest idea worth keeping is a git-tracked durable repo memory document for
validated project facts that are useful but do not naturally belong in always-on
instructions.

The value is not the file itself. The value is that durable team knowledge becomes:

- reviewable
- diffable
- portable across machines
- separate from ephemeral session notes

For xanad-assistant, that durable target should stay simple: one `docs/memory.md`
file with clear sections rather than multiple persona files.

### Inbox-to-promotion workflow

The predecessor model had a useful distinction between temporary captured facts and
durable validated facts.

That distinction is worth keeping in simplified form:

- use `/memories/repo/` as a temporary inbox during a task
- validate facts against the repo
- promote only stable facts into durable git-tracked memory

This avoids forcing every observed pattern into a permanent document too early.

### Citation-backed durable facts

The predecessor’s strongest durable-memory habit was associating facts with sources.

That should remain mandatory for xanad-assistant durable repo memory because it keeps
memory subordinate to repository truth instead of turning it into folklore.

## Avoid

### Always-on heartbeat or pulse infrastructure

The predecessor pulse system was too heavy for the value it provided.

It introduced:

- runtime complexity on every tool call
- lockfiles and state files
- silent degradation risk
- extra maintenance burden unrelated to lifecycle correctness

Xanad-assistant should not adopt an always-on session-monitoring system as part of
memory v1.

### Mixing runtime state with git-tracked knowledge

The predecessor mixed tracked knowledge and runtime artifacts under the same general
workspace tree. That increases `git status` noise and blurs the difference between
durable knowledge and operational state.

Xanad-assistant should keep these separate:

- runtime or temporary state stays outside durable docs
- durable repo knowledge stays in version-controlled docs only

### Multi-file persona memory splits

The predecessor’s separate MEMORY, SOUL, and USER files imposed too much routing
overhead for normal development work.

For xanad-assistant, a single durable repo memory document with topic sections is the
better default unless real scale later proves otherwise.

## Proposed Xanad V1 Shape

| Concern | Xanad v1 choice |
|--------|------------------|
| Current task notes | `/memories/session/` |
| User-wide preferences | `/memories/` |
| In-flight repo facts | `/memories/repo/` |
| Durable validated repo memory | `docs/memory.md` |
| Runtime telemetry | not part of memory v1 |
| Always-on automation | not part of memory v1 |

## Adoption Rule

Adopt the predecessor’s verification discipline and promotion workflow.

Do not adopt its heavyweight runtime memory machinery.

The intended result is a memory system that is:

- optional
- local-first
- low-overhead
- reviewable
- compatible with the lifecycle engine’s authoritative artifacts