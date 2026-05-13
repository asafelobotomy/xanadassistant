---
name: leanContext
description: "Context window hygiene — keep working context tight, current, and actionable."
---

# Lean Context

Use this skill in workspaces with the lean pack selected.

Context window hygiene: keep working context tight, current, and actionable. Carrying stale or redundant context across turns degrades response quality and wastes capacity.

## What to prune

- Raw tool results after you have derived an answer from them — emit the conclusion, not the raw output
- Intermediate steps that have been completed and are no longer relevant to what comes next
- Unchanged-state confirmations ("the file was not modified") unless ambiguity requires them
- Re-reading files or re-running commands that already produced a result this session

## What to defer

- File reads until the step that actually needs them — do not pre-load files speculatively
- Fetching referenced context (schemas, configs, lockfiles) until it is required for the current step
- Broad codebase exploration until the specific file or symbol is identified

## How to reference earlier context

When building on decisions or context established earlier in the conversation:
- Use pointers: "same approach as the previous fix" rather than re-quoting the full approach
- Summarize multi-step prior work as: `Prior: [what was done] → [result] → [current state]`
- Never repeat file contents already read this session; reference by path only
- Never repeat the user's full original request back to them

## What never to compress

- Error messages from failed operations — include verbatim; do not paraphrase
- File paths, symbol names, and schema field names — precision cannot be recovered from summaries
- Security or destructive action confirmations — always enumerate what is affected
- The active task state — the user must be able to orient from your last response alone
