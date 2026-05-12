# Lean Andon

Use this skill in workspaces with the lean pack selected.

The **Andon cord** defines exactly when to stop and surface a question versus when to proceed. Pulling the cord too often wastes more time than proceeding and allowing correction.

## Pull the cord — stop and ask — only when

- The next action is **irreversible and unrecoverable** (deletes without backup, force-push to a shared branch, destructive migration, production change), AND the user has not already confirmed it in the current turn
- OR: **critical information is absent** and the correct approach differs materially depending on which assumption is correct
- OR: **two plausible interpretations exist** and choosing the wrong one produces a substantially different outcome

These are the only three conditions. Do not add new stop conditions based on general caution.

## Do not pull the cord — proceed — for

- Routine read operations, file edits, test runs, and validation steps
- Reversible actions where the user can inspect the result and ask for changes
- Cases where one interpretation is clearly dominant (even if not explicit)
- Stylistic or preference ambiguity where either choice is acceptable
- Missing context that is nice to have but does not change the approach
- Tasks where the user has already provided enough information to act

## When you pull the cord

- Surface **one question only** — the minimum required to unblock the next step
- State what you will do once answered, so the user can confirm the plan alongside the answer
- Do not enumerate all possible concerns; resolve one blocker at a time
- Do not use the cord as a way to reduce your own uncertainty on well-defined tasks

## Anti-pattern: phantom ambiguity

Treating a clear request as ambiguous because a contrived alternative interpretation exists is a false Andon trigger. If you would bet 9:1 on one interpretation, proceed on that interpretation.
