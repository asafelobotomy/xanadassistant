---
mode: ask
description: "Run a TDD session for a feature or behavior using Red-Green-Refactor discipline."
---

Run a TDD session for the feature or behavior described below.

Use the `tddCycle` skill for Red-Green-Refactor discipline and commit guidance.
Use the `testDoubles` skill when the implementation requires isolation from dependencies.

Work one cycle at a time:

**Red**: Write one failing test. State what it asserts and why it fails.
**Green**: Write the minimum implementation to make it pass. State what you changed.
**Refactor**: Clean up without changing behavior. State what you restructured and confirm tests are still green.

After each complete cycle, pause and ask whether to continue to the next behavior or stop.
