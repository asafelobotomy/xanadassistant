# Eval Suites

This directory holds declarative eval suites for the repository's top-level skills.

Each suite contains an `eval.yaml` definition plus `tasks/` prompts used by external evaluation tooling and repo maintenance checks. If you add or rename a top-level skill, add or update the matching suite here so `python3 tools/xanadEval/xanadEval.py check skills/<skill>/SKILL.md` continues to report eval coverage.
