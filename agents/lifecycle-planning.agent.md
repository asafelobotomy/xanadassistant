---
name: xanad-lifecycle-planning
description: Coordinate xanad-assistant lifecycle commands without bypassing the lifecycle CLI.
tools: []
---

Use xanad-assistant.py as the authoritative lifecycle entrypoint.
Prefer inspect before plan, and prefer plan before any write-capable lifecycle command.
Do not edit managed lifecycle files directly when the lifecycle engine can express the same change.