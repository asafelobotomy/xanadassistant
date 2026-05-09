---
name: tech-debt-audit
description: "Use when: auditing xanadassistant for maintainability debt such as oversized files, generated-artifact drift, manifest coverage gaps, brittle tests, stale debt markers, or lifecycle-engine complexity hotspots, and you need prioritized follow-up actions."
compatibility: ">=1.4"
---

# Tech Debt Audit

> Skill metadata: version "1.0"; tags [tech-debt, quality, xanadassistant, maintainability, generated-artifacts]; recommended tools [codebase, runCommands, editFiles].

Audit xanadassistant for repo-native maintainability debt. Start from the quality signals this repository already trusts, then build a prioritized debt register with concrete follow-up actions and expected validation.

## When to use

- When the user asks to find tech debt, audit maintainability, identify cleanup candidates, or assess code quality in this repository
- Before a larger refactor of the lifecycle engine, hooks, tests, or consumer-facing surfaces
- When generated-artifact drift, manifest coverage, brittle tests, or LOC pressure may be obscuring the real maintenance cost of recent work

## When not to use

- Outside the xanadassistant repository
- For security review; use a dedicated security-focused audit instead
- For dependency upgrades or ecosystem migrations; this repository is stdlib-only at runtime and needs a narrower workflow

## Steps

1. Start with repo-native quality signals.
   - Run `python3 scripts/check_loc.py`.
   - Check the current regression state with `python3 -m unittest discover -s tests -p 'test_*.py'` when a fresh result is needed.
   - Check generated-artifact freshness with `python3 -m scripts.lifecycle.check_manifest_freshness --package-root . --policy template/setup/install-policy.json --manifest template/setup/install-manifest.json --catalog template/setup/catalog.json` when recent work touched managed surfaces.

2. Scan for explicit debt markers in active repo surfaces.
   - Search `scripts/`, `hooks/`, `agents/`, `skills/`, and `tests/` for `TODO`, `FIXME`, `HACK`, `WORKAROUND`, and `deprecated`.
   - Treat markers in lifecycle-engine call paths, hook scripts, or tests that guard frozen contracts as higher priority than notes in planning docs.

3. Review hotspot files and recurring friction.
   - Inspect files near the LOC warning threshold.
   - Look for modules or tests that repeatedly need exact-string maintenance after wording-only changes.
   - Flag maintainer-only logic that may be leaking into consumer-delivered surfaces.

4. Use xanadassistant's primary debt categories.
   - `contract-drift`: generated artifacts, manifest coverage, or policy expectations drifting out of sync.
   - `test-brittleness`: wording-sensitive or duplicated assertions that make harmless surface cleanups expensive.
   - `size-pressure`: Python, Markdown, or shell files approaching or exceeding LOC thresholds.
   - `explicit-debt-marker`: stale TODO/FIXME/HACK items in active paths.
   - `ownership-blur`: repo-local maintainer behavior at risk of leaking into consumer-managed surfaces.

5. Build a prioritized debt register.
   - For each item, include: category, file or surface, why it matters, the concrete next action, and the validation that would prove the debt was reduced.
   - Prioritize by delivery risk first: contract drift, generated-artifact churn, and brittle tests outrank cosmetic cleanup.

6. Keep optional second-tier checks explicit.
   - Use tool-assisted dead-code or complexity scans only if those tools are already available.
   - Do not make `vulture`, `radon`, coverage tools, or other non-stdlib helpers a default dependency of the audit.

## Verify

- [ ] Repo-native quality signals were checked before broader speculation
- [ ] Debt findings are grouped by xanadassistant-specific categories, not generic language buckets
- [ ] High-priority items include a concrete next action and validation step
- [ ] Generated-artifact drift, manifest coverage, and brittle tests were considered alongside explicit debt markers
- [ ] Optional external tools were treated as second-tier, not mandatory