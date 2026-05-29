# core pack

The core pack is the foundation of every xanadAssistant install. It is not
optional — it is always installed and provides the baseline token values that all
other packs and agents inherit from.

## What it provides

**Token defaults** — `tokens.json` defines all ten `{{pack:...}}` tokens with
balanced, general-purpose values:

| Token | Default behavior |
|---|---|
| `{{pack:commit-style}}` | Conventional Commits 1.0 format |
| `{{pack:output-style}}` | Thorough responses with context and explanation |
| `{{pack:plan-format}}` | Full step-by-step plans with assumptions and risks |
| `{{pack:review-depth}}` | All findings Advisory and above |
| `{{pack:scope-discipline}}` | Address stated request; flag adjacent improvements |
| `{{pack:blocker-discipline}}` | Stop and ask only when action is irreversible or ambiguous |
| `{{pack:reasoning-mode}}` | Explain reasoning for all non-trivial decisions |
| `{{pack:step-size}}` | Complete each step fully before starting the next |
| `{{pack:context-hygiene}}` | Reference earlier context by pointer rather than restating |
| `{{pack:secret-guard}}` | Check for credentials before staging or committing |

Optional packs override a subset of these tokens when selected. Agent
customization questions can further override individual tokens for specific
agents.

## Structure

```
packs/core/
└── tokens.json       # Baseline {{pack:...}} token values
```

## Selection

`core` is not listed as an optional pack in the registry and is never shown
in the interview. Its token file is always loaded first during token resolution,
providing the fallback values for any token not overridden by a selected pack.
