# shapeup pack

The shapeup pack installs Shape Up process defaults — pitch writing, cycle
execution, betting table process, and scope discipline — so that agents help
you work within fixed appetites rather than expanding scope or time.

## Purpose

Install this pack when the team uses Shape Up (or a similar fixed-time / shaped
work process). Agents will flag work that lacks a defined appetite, surface scope
creep and rabbit holes as blocking issues, and help write structured pitches,
run cycle kick-offs, and manage the betting table.

## Surfaces

| Surface | Contents |
|---|---|
| **Skills** | `shapeupBetting`, `shapeupCycleWork`, `shapeupPitching`, `shapeupReview` |
| **Prompts** | `/shapeup-pitch`, `/shapeup-kickoff` |
| **MCP** | `shapeupScopeCheck.py` — inspects open work items for unbounded scope or missing appetite |

## Token overrides

| Token | Shape Up behavior |
|---|---|
| `{{pack:review-depth}}` | Flag scope creep, rabbit holes, and unbounded work as blocking issues during review |
| `{{pack:scope-discipline}}` | Proactively flag work that lacks a fixed time boundary or clear appetite before proceeding |

## Interview customization

During setup you can choose how the pack models appetite and scope:

- **Time-boxed** (default) — fixed time boundary; adjust scope to fit, never
  expand time. If a solution cannot be delivered within appetite, return an
  adjusted scope.
- **Scope-boxed** — fixed deliverable scope; flag time-based pressure that
  drives scope changes as a blocker rather than adjusting the scope.

Both options override `{{pack:scope-discipline}}`.
