---
name: commitPreflight
description: "Use when: preparing to commit or push changes in the xanadAssistant repository and you need local preflight checks for unit tests, manifest freshness, LOC limits, generated artifacts, or template-safety rules."
compatibility: ">=1.4"
---

# Commit Preflight

> Skill metadata: version "1.0"; tags [commit, preflight, ci, xanadAssistant, generated-artifacts]; recommended tools [runCommands, codebase, editFiles, askQuestions].

Run xanadAssistant's local CI-equivalent checks before commit or push, repair stale generated artifacts when the fix is mechanical, and return a clear pass, block, or residual-risk outcome to the Commit agent.

## When to use

- Before commit or push in this repository when changes may affect tests, generated artifacts, or template surfaces
- When staged changes include `template/`, `agents/`, `skills/`, `hooks/`, or lifecycle-engine files
- When the user asks for commit or push preflight in this repository

## When not to use

- Outside the xanadAssistant repository
- When there are no staged or proposed files to validate
- When the user explicitly instructs you to skip local verification

## Steps

1. Determine the candidate file set with `git diff --cached --name-only`. If nothing is staged, inspect the proposed file list before widening scope.

2. Decide the required checks.
   - Always run `python3 scripts/check_loc.py`.
   - Always run `python3 -m unittest discover -s tests -p 'test_*.py'` before push, and before commit when the change is more than trivial wording in a single documentation file.
   - Run the freshness check whenever any staged file is under `template/`, `agents/`, `skills/`, `packs/lean/skills/`, or `hooks/`.
   - Run a `{{}}` token-presence check whenever `template/copilot-instructions.md` is staged.

3. Execute checks cheapest-first.
   - `python3 scripts/check_loc.py`
   - `grep -q '{{' template/copilot-instructions.md` when needed
   - `python3 -m unittest discover -s tests -p 'test_*.py'`
   - `python3 -m scripts.lifecycle.check_manifest_freshness --package-root . --policy template/setup/install-policy.json --manifest template/setup/install-manifest.json --catalog template/setup/catalog.json` when needed

4. Repair mechanical freshness failures only.
   - If freshness fails after managed-surface edits, run `python3 scripts/generate.py`.
   - Stage `template/setup/install-manifest.json` and `template/setup/catalog.json` if they changed.
   - Re-run the freshness check after regeneration.

5. Block on template-safety violations.
   - If `template/copilot-instructions.md` is staged and unresolved `{{}}` tokens are missing, block the commit or push.
   - If a required check still fails after in-scope repair, stop and report the exact blocker.

6. Use `askQuestions` only for residual-risk acceptance.
   - If a check was intentionally skipped or could not run for a justified reason, ask whether to accept the residual risk before proceeding.

7. Return a concise summary.
   - Commands run
   - Whether generated artifacts were refreshed and staged
   - Pass, block, or residual-risk outcome

## Verify

- [ ] LOC gate run and passed, or the exact failure is surfaced
- [ ] Full unittest suite run when required, or the skip reason is explicit
- [ ] Freshness check run when managed surfaces changed
- [ ] `python3 scripts/generate.py` run and regenerated files staged when freshness repair was needed
- [ ] `template/copilot-instructions.md` still contains unresolved `{{}}` tokens when that file changed
- [ ] Commit agent received a clear pass, block, or residual-risk outcome