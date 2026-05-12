---
name: docsStructure
description: "Documentation structure — Diátaxis framework, README anatomy, ADR format, and section ordering."
---

# docsStructure

Use this skill when planning, scaffolding, or reorganising documentation. Apply it before drafting to choose the right document type and section order.

## Diátaxis framework

Four document types that serve different reader goals. Each type should be kept separate — do not mix tutorial steps with reference tables.

| Type | Reader goal | Characteristic |
|---|---|---|
| **Tutorial** | Learn by doing | Guided, outcome-oriented, no choices |
| **How-to guide** | Accomplish a specific task | Assumes knowledge; focused steps |
| **Reference** | Look something up | Accurate, complete, no narrative |
| **Explanation** | Understand why | Conceptual; broader context |

## README anatomy

A project README should follow this section order:

```markdown
# Project Name

One-sentence description.

## Overview

What the project does and who it is for (2–4 sentences).

## Quick start

Minimal steps to get from zero to working (copy-runnable commands).

## Installation

Full install options (OS variants, package managers, version constraints).

## Usage

Core usage patterns with examples.

## Configuration

All options, environment variables, flags — ideally in a table.

## Contributing

Link to CONTRIBUTING.md or inline brief guide.

## License

SPDX identifier and link to LICENSE file.
```

Sections before "Contributing" are required. Omit sections only if they genuinely do not apply.

## API reference structure

Each exported symbol should document:

1. **Signature** — full type signature or function prototype.
2. **Description** — one sentence; what it does, not how.
3. **Parameters / Fields** — name, type, required/optional, description.
4. **Returns** — type and meaning.
5. **Raises / Throws** — conditions and error types.
6. **Example** — minimal working example.

## Architecture Decision Record (ADR)

Use this template for ADRs:

```markdown
# ADR-NNN: Title

**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-NNN

## Context

What is the situation that required a decision?

## Decision

What was decided?

## Consequences

What becomes easier? What becomes harder? What is deferred?
```

Store ADRs in `docs/decisions/` with filenames `NNN-short-title.md`.

## Section ordering rules

- Put the most important information first (inverted-pyramid structure).
- Prerequisites and setup before usage.
- Happy-path examples before error handling.
- Reference material last (tables, full option lists).
