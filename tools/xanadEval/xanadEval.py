#!/usr/bin/env python3
"""xanadEval — skill analyser and eval runner for Copilot surface files.

Static commands (no API key required):
  tokens <path>          Structural metrics: token count, sections, nesting
  check  <path>          Spec-compliance and advisory checks
  suggest <path>         Scaffold an eval task suite from frontmatter
  coverage [root]        Skill-to-eval coverage report
  compare <ref>          Git-ref token-diff
  report  [paths]        Self-contained HTML check report

Dynamic commands (require GITHUB_TOKEN or GH_TOKEN):
  run     <eval.yaml>    Execute eval tasks against GitHub Models
  grade   <eval.yaml> <results.json>   Re-run graders on existing results
  quality <path>         LLM-as-judge: score skill on 5 quality dimensions
  dev     <path>         Surface top improvement suggestions
  results list  [dir]    List saved result files
  results compare <f1> <f2>  Compare pass-rate deltas across runs
  results view  <file>   Display a saved result file
"""
from __future__ import annotations

import sys

# ── Shared helpers, model integration, graders ────────────────────────────────
import _common
from _common import (
    TOKEN_BUDGET, _CHARS_PER_TOKEN, _DEFAULT_MODEL, _DEFAULT_RESULTS_DIR,
    _QUALITY_DIMENSIONS, _GITHUB_MODELS_URL, _yaml, _TK_ENC,
    _get_token, _call_model, _load_spec, _load_tasks, _extract_first_json_object,
    _read, _parse_frontmatter, _count_tokens, _yaml_str, _max_nesting_depth,
    _grade_text, _grade_behavior, _grade_json_schema, _grade_program,
    _grade_prompt_judge, _run_graders, _aggregate_trials,
)
_token_estimate = _count_tokens  # backwards-compatibility alias (renamed in refactor)

import _graders_ext
from _graders_ext import (
    _grade_trigger, _grade_file, _grade_diff,
    _tokenize, _parse_use_for_phrases,
)

# Bind this module so mock.patch("xanadEval._call_model") is intercepted by _common.
_common.bind_api(sys.modules[__name__])

import _static
from _static import _build_check_result, cmd_tokens, cmd_check, cmd_suggest

import _reporting
from _reporting import cmd_coverage, cmd_compare, cmd_report

import _dynamic
from _dynamic import cmd_run, cmd_grade

import _feedback
from _feedback import cmd_quality, cmd_dev, _QUALITY_PROMPT, _DEV_PROMPT

import _results
from _results import cmd_results_list, cmd_results_view, cmd_compare_results

from _cli import main  # noqa: E402

# Bind this module to sibling modules that call _call_model via _api.
_dynamic.bind_api(sys.modules[__name__])
_feedback.bind_api(sys.modules[__name__])

if __name__ == "__main__":
    sys.exit(main())



