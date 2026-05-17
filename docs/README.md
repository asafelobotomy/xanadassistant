# Docs Layout

The `docs/` tree is split by document role:

- `contracts/` holds stable interface and behavior contracts.
- `plans/` holds implementation and rollout plans.
- `archive/` holds historical material that should not drive current behavior.

The `docs/` root is reserved for living reference notes that are neither contracts nor plans:

- `maintenance-drift.md` is the maintainer drift-control policy referenced by the main README.
- `template-review-adopt.md` is the template-adoption decision ledger referenced by agent routing and attention-budget checks.

If a new document is primarily a plan, place it under `docs/plans/`. If it defines a stable interface or protocol, place it under `docs/contracts/`. Keep the root small and limited to standing reference ledgers like the two files above.
