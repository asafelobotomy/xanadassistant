---
mode: ask
description: Create a cycle kickoff document from a betted Shape Up pitch.
---

Create a cycle kickoff document from a betted Shape Up pitch.

## Instructions

Use the shapeupCycleWork skill to structure the output.

Ask the user for:
1. The betted pitch (paste or summarize it)
2. The team (designer name(s) and programmer name(s))
3. The cycle start and end dates
4. Any additional constraints or context known since the pitch was written

Then produce a cycle kickoff document that includes:

### 1. Bet Summary
- One-paragraph restatement of the problem and appetite
- Link or reference to the original pitch

### 2. Team
- Designer(s) and programmer(s) by name
- Confirmation that no team member is assigned to another concurrent bet

### 3. Initial Scope
- Break the pitch solution into an initial task list (5–15 items is typical)
- Classify each task as Uphill (unknowns remain) or Downhill (approach is settled)
- Note any tasks that are likely to be scoped out during the cycle

### 4. Rabbit Hole Mitigations
- Restate each named rabbit hole from the pitch
- Confirm the agreed mitigation strategy

### 5. Circuit Breaker Acknowledgement
- State the cycle end date explicitly
- Confirm: if the work is not done by this date, the team will stop and re-pitch
  rather than carry the work into the next cycle

### 6. Cooldown Note
- Remind the team that cooldown is not overflow time
- List any cleanup or exploration tasks planned for cooldown (optional)

## Output Format

Produce the kickoff document in Markdown suitable for pasting into a project wiki or GitHub
discussion. Keep each section concise — this is a working document, not a spec.
