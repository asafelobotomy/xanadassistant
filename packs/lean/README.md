# lean pack

The lean pack replaces the core pack's defaults with brevity-oriented values,
reducing agent verbosity and tightening scope discipline across all surfaces.

## Purpose

Install this pack when you want agents to produce the smallest correct output
for each request — no receipts, no rationale, no filler. It is well-suited to
experienced engineers who want fast iteration and minimal prose overhead.

## Surfaces

| Surface | Contents |
|---|---|
| **Skills** | `leanAndon`, `leanContext`, `leanOutput`, `leanVerification` |
| **Prompts** | `/lean-plan`, `/lean-review`, `/lean-status` |
| **Tool scripts** | `.github/mcp/scripts/leanContextBudget.py` and `.github/mcp/scripts/leanTestReporter.py` when the lean pack is installed. These scripts are not part of the default core MCP server roster. |

## Token overrides

The lean pack overrides all nine behavioral tokens with terse equivalents:

| Token | Lean behavior |
|---|---|
| `{{pack:commit-style}}` | One-line subject only; body only for breaking changes |
| `{{pack:output-style}}` | Terse; one-line descriptions; skip unchanged-state commentary |
| `{{pack:plan-format}}` | Numbered steps only; omit rationale and risks unless asked |
| `{{pack:review-depth}}` | Critical and High only; skip Advisory and style notes |
| `{{pack:scope-discipline}}` | Answer exactly what was asked; no scope expansion |
| `{{pack:blocker-discipline}}` | Stop only for irreversible/unrecoverable actions or missing critical info |
| `{{pack:reasoning-mode}}` | Compressed conclusions only; suppress narration for routine tasks |
| `{{pack:step-size}}` | Smallest independently verifiable step; no adjacent improvements |
| `{{pack:context-hygiene}}` | Emit conclusion only; use pointers not restatements |

## Interview customization

During setup you can adjust the output verbosity:

- **Compressed** (default) — compressed state receipts for routine tasks;
  explicit reasoning reserved for Critical/High findings and irreversible
  decisions.
- **Silent** — results only; no reasoning narration; one line per action taken.

Both options override `{{pack:reasoning-mode}}`.
