---
name: docsStyle
description: "Use when: improving documentation writing style, prose register, active voice, imperative mood, or term consistency."
type: reference
---

# docsStyle

> Skill metadata: version "1.0"; tags [docs, style, prose]; recommended tools [].

Use this skill when drafting or reviewing any user-facing documentation: READMEs, guides, API references, changelogs, or inline code comments.

## When to use

- Drafting or reviewing any user-facing documentation: READMEs, guides, API references, changelogs, or inline code comments

## When NOT to use

- When reviewing for technical accuracy — prefer `docsReview`
- When writing code docstrings in a language with dedicated conventions — prefer `docsApi`

## Core principles

| Principle | Rule | Example |
| --- | --- | --- |
| Active voice | Subject performs the action | "The CLI reads the config file." not "The config file is read by the CLI." |
| Imperative mood | Instructions start with a verb | "Run `npm install`." not "You should run `npm install`." |
| Short sentences | One idea per sentence | Split anything over ~25 words. |
| Present tense | Describe what the system does now | "Returns a list." not "Will return a list." |
| Second person | Address the reader as "you" | "You can configure…" not "One can configure…" or "The user can configure…" |

## Term consistency

- Establish a term for a concept the first time it appears and reuse it exactly throughout.
- Do not alternate between synonyms (e.g., "token" / "key" / "credential" — pick one and use it everywhere).
- When adopting upstream terminology (e.g., from a framework or standard), match it exactly including capitalisation.
- Define acronyms on first use: "Application Binary Interface (ABI)".

## Code examples

- Every code example must be complete enough to copy-run without additional context.
- Use fenced code blocks with a language tag: ` ```python ` not ` ``` `.
- Show realistic inputs and outputs, not placeholder strings like `<your-value-here>` unless the reader genuinely must substitute.
- Keep examples under 30 lines; link to a full working sample if more context is needed.

## Tone by doc type

| Type | Tone |
| --- | --- |
| Tutorial | Encouraging; guide the reader step by step. |
| How-to guide | Direct; assume the reader knows what they want. |
| Reference | Neutral, precise; no narrative. |
| Explanation / concept | Conversational; use analogies. |

## Common anti-patterns

- **Passive stacking**: "It should be noted that the flag may be set to…" → "Set the flag to…"
- **Weasel words**: "fairly", "quite", "very", "basically" — delete them.
- **Future tense for current behavior**: "This will allow…" → "This allows…"
- **Unnecessary preamble**: "In this section, we will explore…" → start with the content.

## Verify

- [ ] Active voice, imperative mood, and short-sentence rules applied
- [ ] Prescribed term list used; no synonym drift
- [ ] No passive constructions, filler phrases, or second-person avoidance
