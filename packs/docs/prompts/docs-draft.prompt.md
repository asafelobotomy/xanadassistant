---
mode: ask
description: "Draft a documentation section — README, guide, API reference, or how-to."
---

You are helping draft documentation for a software project.

Apply the docsStyle skill for prose quality and the docsStructure skill to choose the right document type and section order. Apply the docsApi skill if the content documents code symbols, CLI commands, or API endpoints.

---

## Inputs

Provide as many of the following as you have:

- **Document type**: Tutorial / How-to guide / Reference / Explanation / README section / ADR / Other.
- **Subject**: What is being documented (feature, function, endpoint, concept).
- **Audience**: Who will read this (new users, experienced developers, ops engineers, etc.).
- **Existing content**: Paste any existing draft, code, or spec to build from.
- **Key points to cover**: Bullet list of things that must appear in the output.

---

## Output

Produce the section in Markdown, ready to paste. Use the heading depth that fits the surrounding document (state "H2 top-level" or similar if unsure, and I will pick an appropriate depth).

Include at least one concrete, copy-runnable example unless the document type is purely conceptual.

If any required input is missing (e.g., the exact function signature for an API reference), ask before writing rather than inventing it.
