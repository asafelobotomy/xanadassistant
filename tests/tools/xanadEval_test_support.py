"""Shared fixtures and base class for xanadEval test files.

Import from this module to access `xe`, shared constants, and fixture helpers.
Do not add test methods here — this is a support module only.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

# Resolve the tool without installing it as a package.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "tools" / "xanadEval")
)
import xanadEval as xe  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixture content
# ---------------------------------------------------------------------------

_MINIMAL_SKILL = """\
---
name: test-skill
description: "A minimal skill used for xanadEval unit tests"
---

# Test Skill

> Skill metadata: version "1.0"; tags [test].

## When to use

- When running xanadEval tests
- When verifying minimal compliance

## When NOT to use

- When not running xanadEval tests

## Module 1 — Alpha

1. Do the first thing.
2. Do the second thing.
3. Verify the result.

## Module 2 — Beta

- Rule A
- Rule B

## Verify

- [ ] All six modules run
- [ ] Findings table present
"""

_NO_FRONTMATTER = """\
# No Frontmatter File

Some content without any YAML frontmatter.
"""

_CONTENT_OVER_BUDGET = (
    "---\nname: test-skill\ndescription: \"x\"\n---\n\n"
    + ("word " * 17_000)  # ~17,000 BPE tokens — well over the 16,000-token budget
)

# Shared mock reply strings for quality / dev tests
_MOCK_QUALITY_REPLY = (
    '{"clarity": 0.8, "completeness": 0.9, "trigger_precision": 0.7, '
    '"scope_coverage": 0.8, "anti_patterns": 0.9, "overall": 0.82, '
    '"summary": "Good skill with minor gaps."}'
)

_MOCK_DEV_REPLY = (
    '{"clarity": 0.6, "completeness": 0.7, "trigger_precision": 0.5, '
    '"scope_coverage": 0.6, "anti_patterns": 0.8, "overall": 0.64, '
    '"improvements": ["Add examples", "Tighten triggers", "Add Verify section"], '
    '"summary": "Needs clearer trigger phrases."}'
)


# ---------------------------------------------------------------------------
# Base class with fixture helpers for dynamic-command tests
# ---------------------------------------------------------------------------

class DynamicTestBase:
    """Mixin with fixture-writing helpers. Combine with unittest.TestCase."""

    def _write_skill(self, d: Path, name: str = "test-skill") -> Path:
        skill_dir = d / "skills" / name
        skill_dir.mkdir(parents=True)
        p = skill_dir / "SKILL.md"
        content = _MINIMAL_SKILL.replace("test-skill", name) if name != "test-skill" else _MINIMAL_SKILL
        p.write_text(content, encoding="utf-8")
        return p

    def _write_eval(self, d: Path, name: str = "test-skill") -> Path:
        """Write a JSON-format eval spec (valid JSON is also valid YAML)."""
        eval_dir = d / "evals" / name
        (eval_dir / "tasks").mkdir(parents=True)
        spec = {
            "name": f"{name}-eval",
            "graders": [
                {"type": "text", "name": "ref_skill", "config": {"contains": ["test"]}}
            ],
            "tasks": ["tasks/*.yaml"],
        }
        eval_yaml = eval_dir / "eval.yaml"
        eval_yaml.write_text(json.dumps(spec), encoding="utf-8")
        task = {"id": "task-1", "prompt": "Tell me about test-skill"}
        (eval_dir / "tasks" / "t1.yaml").write_text(json.dumps(task), encoding="utf-8")
        return eval_yaml

    def _write_result(self, d: Path, name: str = "run", pass_rate: float = 1.0) -> Path:
        result = {
            "eval": "evals/test-skill/eval.yaml",
            "skill": "test-skill",
            "model": "gpt-4o-mini",
            "timestamp": "2026-05-20T12:00:00Z",
            "summary": {
                "total": 1, "passed": int(pass_rate), "pass_rate": pass_rate,
                "score": pass_rate,
            },
            "tasks": [{
                "id": "task-1",
                "prompt": "test prompt",
                "response": "response mentioning test skill",
                "graders": [{"type": "text", "name": "ref_skill", "pass": True, "score": 1.0}],
                "passed": pass_rate == 1.0,
                "score": pass_rate,
            }],
        }
        p = d / f"{name}-result.json"
        p.write_text(json.dumps(result), encoding="utf-8")
        return p

    def _skill_tmpfile(self) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(_MINIMAL_SKILL)
            return f.name


__all__ = [
    "xe", "mock", "io", "json", "os", "sys", "tempfile", "unittest",
    "redirect_stderr", "redirect_stdout", "Path",
    "_MINIMAL_SKILL", "_NO_FRONTMATTER", "_CONTENT_OVER_BUDGET",
    "_MOCK_QUALITY_REPLY", "_MOCK_DEV_REPLY",
    "DynamicTestBase",
]
