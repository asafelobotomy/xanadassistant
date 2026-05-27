"""Unit tests for the extended grader types: trigger, file, diff.

Tests _grade_trigger, _grade_file, _grade_diff, _tokenize, _parse_use_for_phrases,
and their dispatch through _run_graders.  Imported via the xanadEval facade.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from xanadEval_test_support import xe

# Pull grader functions from the facade.
_grade_trigger = xe._grade_trigger
_grade_file = xe._grade_file
_grade_diff = xe._grade_diff
_tokenize = xe._tokenize
_parse_use_for_phrases = xe._parse_use_for_phrases
_run_graders = xe._run_graders

# ── Minimal SKILL.md fixture ──────────────────────────────────────────────────

_SKILL_CONTENT = """\
---
name: azure-deploy
description: "Deploy workloads to Azure. USE FOR: deploy to azure, publish api to azure. DO NOT USE FOR: local builds, unit tests."
---

# Azure Deploy Skill

> version "1.0"

## When to use

- Deploying applications to Azure App Service
- Publishing REST APIs to Azure API Management
- Running ARM template deployments

## Steps

1. Authenticate with az login.
2. Select the target subscription.
3. Run az deploy or az webapp up.
"""


def _write_skill(directory: Path, content: str = _SKILL_CONTENT) -> Path:
    skill_dir = directory / "azure-deploy"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")
    return skill_file


# ── _tokenize ─────────────────────────────────────────────────────────────────


class TokenizeTests(unittest.TestCase):
    def test_basic_tokenization(self) -> None:
        tokens = _tokenize("Deploy to Azure App Service")
        self.assertIn("deploy", tokens)
        self.assertIn("azure", tokens)
        self.assertIn("app", tokens)
        self.assertIn("service", tokens)
        # "to" is a stop word (too short); should be absent
        self.assertNotIn("to", tokens)

    def test_stop_words_excluded(self) -> None:
        result = _tokenize("the and for with this")
        self.assertEqual(result, [])

    def test_tokens_shorter_than_three_excluded(self) -> None:
        result = _tokenize("a to go if is in it")
        self.assertEqual(result, [])

    def test_case_normalised(self) -> None:
        tokens = _tokenize("Deploy DEPLOY deploy")
        self.assertEqual(tokens, ["deploy", "deploy", "deploy"])

    def test_hyphens_preserved(self) -> None:
        tokens = _tokenize("well-known fact")
        self.assertIn("well-known", tokens)


# ── _parse_use_for_phrases ─────────────────────────────────────────────────────


class ParseUseForPhrasesTests(unittest.TestCase):
    def test_extracts_use_for_phrases(self) -> None:
        desc = "Skill description. USE FOR: deploy to azure, publish api to azure. DO NOT USE FOR: local builds."
        phrases = _parse_use_for_phrases(desc)
        self.assertTrue(any("deploy" in p.lower() for p in phrases), phrases)
        self.assertTrue(any("publish" in p.lower() for p in phrases), phrases)

    def test_does_not_include_do_not_use_for(self) -> None:
        desc = "Skills. USE FOR: run tests. DO NOT USE FOR: building."
        phrases = _parse_use_for_phrases(desc)
        combined = " ".join(phrases).lower()
        self.assertNotIn("build", combined)

    def test_returns_empty_when_no_marker(self) -> None:
        phrases = _parse_use_for_phrases("No relevant marker here.")
        self.assertEqual(phrases, [])

    def test_when_marker_also_works(self) -> None:
        desc = "Skill. WHEN: running a deployment pipeline."
        phrases = _parse_use_for_phrases(desc)
        self.assertTrue(any("deployment" in p.lower() or "running" in p.lower() for p in phrases), phrases)


# ── _grade_trigger ─────────────────────────────────────────────────────────────


class TriggerGraderTests(unittest.TestCase):

    def _make_skill(self) -> Path:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        return _write_skill(Path(self._tmpdir.name))

    def test_positive_mode_matching_prompt_passes(self) -> None:
        skill_file = self._make_skill()
        config = {
            "skill_path": str(skill_file),
            "mode": "positive",
            "threshold": 0.1,
        }
        passed, score, details = _grade_trigger("deploy to azure", config)
        self.assertTrue(passed)
        self.assertGreater(score, 0.0)
        self.assertNotIn("error", details)

    def test_positive_mode_unrelated_prompt_fails(self) -> None:
        skill_file = self._make_skill()
        config = {
            "skill_path": str(skill_file),
            "mode": "positive",
            "threshold": 0.5,
        }
        passed, score, _ = _grade_trigger("write some unit tests for python", config)
        self.assertFalse(passed)

    def test_negative_mode_unrelated_prompt_passes(self) -> None:
        skill_file = self._make_skill()
        config = {
            "skill_path": str(skill_file),
            "mode": "negative",
            "threshold": 0.5,
        }
        passed, score, _ = _grade_trigger("plan a birthday party", config)
        self.assertTrue(passed)

    def test_negative_mode_matching_prompt_fails(self) -> None:
        skill_file = self._make_skill()
        config = {
            "skill_path": str(skill_file),
            "mode": "negative",
            "threshold": 0.1,
        }
        passed, score, _ = _grade_trigger("deploy to azure app service", config)
        self.assertFalse(passed)

    def test_missing_skill_path_returns_error(self) -> None:
        passed, score, details = _grade_trigger("anything", {"mode": "positive"})
        self.assertFalse(passed)
        self.assertIn("error", details)

    def test_invalid_mode_returns_error(self) -> None:
        _, _, details = _grade_trigger("prompt", {"skill_path": "x.md", "mode": "maybe"})
        self.assertIn("error", details)

    def test_skill_path_as_directory_finds_skill_md(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        skill_file = _write_skill(Path(tmpdir.name))
        # Pass the directory (not the SKILL.md file)
        skill_dir = skill_file.parent
        config = {"skill_path": str(skill_dir), "mode": "positive", "threshold": 0.1}
        passed, score, details = _grade_trigger("deploy to azure", config)
        self.assertNotIn("error", details)
        self.assertGreater(score, 0.0)

    def test_relative_skill_path_resolved_with_eval_dir(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        root = Path(tmpdir.name)
        skill_file = _write_skill(root)
        eval_dir = root
        # Only the relative directory name, not the full path
        config = {"skill_path": "azure-deploy/SKILL.md", "mode": "positive", "threshold": 0.1}
        passed, score, details = _grade_trigger("deploy to azure", config, eval_dir=eval_dir)
        self.assertNotIn("error", details)
        self.assertGreater(score, 0.0)

    def test_empty_prompt_negative_mode_passes(self) -> None:
        skill_file = self._make_skill()
        config = {"skill_path": str(skill_file), "mode": "negative"}
        passed, score, _ = _grade_trigger("", config)
        self.assertTrue(passed)
        self.assertEqual(score, 0.0)

    def test_run_graders_dispatches_trigger_type(self) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        skill_file = _write_skill(Path(tmpdir.name))
        spec = [{
            "type": "trigger",
            "name": "is-azure-deploy",
            "config": {"skill_path": str(skill_file), "mode": "positive", "threshold": 0.1},
        }]
        results = _run_graders(
            "ignored response",
            spec,
            "gpt-4o-mini",
            "",
            ctx={"prompt": "deploy to azure"},
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "trigger")
        self.assertIsNotNone(results[0]["pass"])


# ── _grade_file ────────────────────────────────────────────────────────────────


class FileGraderTests(unittest.TestCase):

    def _tmpdir(self) -> Path:
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return Path(d.name)

    def test_must_exist_file_present_passes(self) -> None:
        ws = self._tmpdir()
        (ws / "output.txt").write_text("hello")
        passed, score, _ = _grade_file({"must_exist": ["output.txt"]}, ws)
        self.assertTrue(passed)
        self.assertEqual(score, 1.0)

    def test_must_exist_file_absent_fails(self) -> None:
        ws = self._tmpdir()
        passed, score, _ = _grade_file({"must_exist": ["missing.txt"]}, ws)
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)

    def test_must_not_exist_absent_passes(self) -> None:
        ws = self._tmpdir()
        passed, score, _ = _grade_file({"must_not_exist": ["artifact.log"]}, ws)
        self.assertTrue(passed)

    def test_must_not_exist_present_fails(self) -> None:
        ws = self._tmpdir()
        (ws / "artifact.log").write_text("junk")
        passed, score, _ = _grade_file({"must_not_exist": ["artifact.log"]}, ws)
        self.assertFalse(passed)

    def test_content_must_match_pattern_passes(self) -> None:
        ws = self._tmpdir()
        (ws / "config.py").write_text("DEBUG = True")
        cfg = {"content_patterns": [{"path": "config.py", "must_match": [r"DEBUG\s*=\s*True"]}]}
        passed, score, _ = _grade_file(cfg, ws)
        self.assertTrue(passed)

    def test_content_must_not_match_fails_when_pattern_present(self) -> None:
        ws = self._tmpdir()
        (ws / "config.py").write_text("SECRET = 'abc123'")
        cfg = {"content_patterns": [{"path": "config.py", "must_not_match": [r"SECRET"]}]}
        passed, score, _ = _grade_file(cfg, ws)
        self.assertFalse(passed)

    def test_unsafe_path_traversal_rejected(self) -> None:
        ws = self._tmpdir()
        passed, score, feedback = _grade_file({"must_exist": ["../escape.txt"]}, ws)
        self.assertFalse(passed)
        self.assertIn("unsafe", feedback.lower())

    def test_absolute_path_rejected(self) -> None:
        ws = self._tmpdir()
        passed, score, feedback = _grade_file({"must_exist": ["/etc/passwd"]}, ws)
        self.assertFalse(passed)
        self.assertIn("unsafe", feedback.lower())

    def test_no_checks_returns_false_with_message(self) -> None:
        ws = self._tmpdir()
        passed, score, feedback = _grade_file({}, ws)
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)
        self.assertIn("required", feedback)

    def test_partial_scoring(self) -> None:
        ws = self._tmpdir()
        (ws / "a.txt").write_text("exists")
        # 2 must_exist (one present, one absent) → 1/2 = 0.5
        cfg = {"must_exist": ["a.txt", "b.txt"]}
        passed, score, _ = _grade_file(cfg, ws)
        self.assertFalse(passed)
        self.assertAlmostEqual(score, 0.5, places=2)

    def test_run_graders_dispatches_file_type(self) -> None:
        ws = self._tmpdir()
        (ws / "output.txt").write_text("done")
        spec = [{
            "type": "file",
            "name": "has-output",
            "config": {"workspace": str(ws), "must_exist": ["output.txt"]},
        }]
        results = _run_graders("llm response", spec, "gpt-4o-mini", "")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "file")
        self.assertTrue(results[0]["pass"])


# ── _grade_diff ────────────────────────────────────────────────────────────────


class DiffGraderTests(unittest.TestCase):

    def _tmpdir(self) -> Path:
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return Path(d.name)

    def test_snapshot_match_passes(self) -> None:
        ws = self._tmpdir()
        ctx = self._tmpdir()
        (ws / "result.txt").write_text("hello world")
        (ctx / "expected.txt").write_text("hello world")
        cfg = {"expected_files": [{"path": "result.txt", "snapshot": "expected.txt"}]}
        passed, score, _ = _grade_diff(cfg, ws, ctx)
        self.assertTrue(passed)
        self.assertEqual(score, 1.0)

    def test_snapshot_mismatch_fails(self) -> None:
        ws = self._tmpdir()
        ctx = self._tmpdir()
        (ws / "result.txt").write_text("hello world")
        (ctx / "expected.txt").write_text("goodbye world")
        cfg = {"expected_files": [{"path": "result.txt", "snapshot": "expected.txt"}]}
        passed, score, _ = _grade_diff(cfg, ws, ctx)
        self.assertFalse(passed)

    def test_contains_plus_fragment_present_passes(self) -> None:
        ws = self._tmpdir()
        (ws / "output.txt").write_text("step one\nstep two\nstep three")
        cfg = {"expected_files": [{"path": "output.txt", "contains": ["+step one"]}]}
        passed, score, _ = _grade_diff(cfg, ws)
        self.assertTrue(passed)

    def test_contains_bare_fragment_present_passes(self) -> None:
        ws = self._tmpdir()
        (ws / "output.txt").write_text("line one two three")
        cfg = {"expected_files": [{"path": "output.txt", "contains": ["one two"]}]}
        passed, score, _ = _grade_diff(cfg, ws)
        self.assertTrue(passed)

    def test_contains_minus_fragment_absent_passes(self) -> None:
        ws = self._tmpdir()
        (ws / "output.txt").write_text("clean output")
        cfg = {"expected_files": [{"path": "output.txt", "contains": ["-TODO"]}]}
        passed, score, _ = _grade_diff(cfg, ws)
        self.assertTrue(passed)

    def test_contains_minus_fragment_present_fails(self) -> None:
        ws = self._tmpdir()
        (ws / "output.txt").write_text("output with TODO marker")
        cfg = {"expected_files": [{"path": "output.txt", "contains": ["-TODO"]}]}
        passed, score, _ = _grade_diff(cfg, ws)
        self.assertFalse(passed)

    def test_file_missing_fails(self) -> None:
        ws = self._tmpdir()
        cfg = {"expected_files": [{"path": "nonexistent.txt"}]}
        passed, score, _ = _grade_diff(cfg, ws)
        self.assertFalse(passed)
        self.assertEqual(score, 0.0)

    def test_empty_expected_files_returns_error_message(self) -> None:
        ws = self._tmpdir()
        passed, score, feedback = _grade_diff({}, ws)
        self.assertFalse(passed)
        self.assertIn("expected_files", feedback)

    def test_partial_scoring(self) -> None:
        ws = self._tmpdir()
        (ws / "present.txt").write_text("here")
        # One file exists (1 check passes), one is absent (1 check fails) → 1/2
        cfg = {"expected_files": [{"path": "present.txt"}, {"path": "absent.txt"}]}
        passed, score, _ = _grade_diff(cfg, ws)
        self.assertFalse(passed)
        self.assertAlmostEqual(score, 0.5, places=2)

    def test_unsafe_path_traversal_rejected(self) -> None:
        ws = self._tmpdir()
        cfg = {"expected_files": [{"path": "../secret.txt"}]}
        passed, score, feedback = _grade_diff(cfg, ws)
        self.assertFalse(passed)
        self.assertIn("unsafe", feedback.lower())

    def test_run_graders_dispatches_diff_type(self) -> None:
        ws = self._tmpdir()
        (ws / "artifact.txt").write_text("result data")
        spec = [{
            "type": "diff",
            "name": "artifact-exists",
            "config": {"workspace": str(ws), "expected_files": [{"path": "artifact.txt"}]},
        }]
        results = _run_graders("llm response", spec, "gpt-4o-mini", "")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "diff")
        self.assertTrue(results[0]["pass"])


if __name__ == "__main__":
    unittest.main()
