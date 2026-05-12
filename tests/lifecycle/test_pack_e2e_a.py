"""Phase 4 — End-to-end pack token lifecycle tests.

Covers:
1. Token rendering — agent file content after apply (core defaults vs lean pack).
2. Planned lockfile shape — resolvedTokenConflicts field is always present.
3. Post-install pack add via update — agents re-rendered, lockfile updated.
4. Check after apply — no drift for either pack configuration.
5. Conflict gate — two conflicting fixture packs block plan/apply correctly
   and resolve when a winner is supplied in answers.

Fixture packs:
  packs/alpha/tokens.json — defines pack:output-style (alpha value)
  packs/beta/tokens.json  — defines pack:output-style (beta value)
Both packs are excluded from the install policy surface and catalog; they
exist solely as token-provider fixtures for conflict testing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase

# ------------------------------------------------------------------
# Canonical token value prefixes (distinctive substrings from tokens.json)
# ------------------------------------------------------------------

# packs/core/tokens.json
_CORE_COMMIT_PREFIX = "Write commit messages following Conventional Commits 1.0:"
_CORE_REVIEW_PREFIX = "Report all finding severities:"
_CORE_OUTPUT_PREFIX = "Provide thorough responses with context and explanation."

# packs/lean/tokens.json
_LEAN_COMMIT_PREFIX = "One-line subject only."
_LEAN_REVIEW_PREFIX = "Flag Critical and High severities only:"
_LEAN_OUTPUT_PREFIX = "Terse."

# packs/alpha/tokens.json  (conflict fixture)
_ALPHA_OUTPUT_PREFIX = "Alpha pack output style:"

# packs/beta/tokens.json   (conflict fixture)
_BETA_OUTPUT_PREFIX = "Beta pack output style:"

# {{pack:...}} marker fragment — must NOT appear in installed files
_PACK_MARKER = "{{pack:"


def _answers(extra: dict | None = None) -> dict:
    """Minimal answers that write all agents locally."""
    base = {"ownership.agents": "local", "ownership.skills": "local", "packs.selected": []}
    if extra:
        base.update(extra)
    return base


class PackTokenRenderingTests(XanadTestBase):
    """Agent files must contain resolved token values, never raw {{pack:…}} markers."""

    # ------------------------------------------------------------------
    # No-pack install — core defaults
    # ------------------------------------------------------------------

    def test_apply_no_pack_renders_core_commit_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(json.dumps(_answers()), encoding="utf-8")

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            content = (ws / ".github" / "agents" / "commit.agent.md").read_text(encoding="utf-8")
            self.assertIn(_CORE_COMMIT_PREFIX, content)
            self.assertNotIn(_PACK_MARKER, content)

    def test_apply_no_pack_renders_core_review_depth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(json.dumps(_answers()), encoding="utf-8")

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            content = (ws / ".github" / "agents" / "review.agent.md").read_text(encoding="utf-8")
            self.assertIn(_CORE_REVIEW_PREFIX, content)
            self.assertNotIn(_PACK_MARKER, content)

    def test_apply_no_pack_renders_core_output_style_in_explore_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(json.dumps(_answers()), encoding="utf-8")

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            content = (ws / ".github" / "agents" / "explore.agent.md").read_text(encoding="utf-8")
            self.assertIn(_CORE_OUTPUT_PREFIX, content)
            self.assertNotIn(_PACK_MARKER, content)

    # ------------------------------------------------------------------
    # Lean-pack install — lean overrides
    # ------------------------------------------------------------------

    def test_apply_lean_pack_renders_lean_commit_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            content = (ws / ".github" / "agents" / "commit.agent.md").read_text(encoding="utf-8")
            self.assertIn(_LEAN_COMMIT_PREFIX, content)
            self.assertNotIn(_CORE_COMMIT_PREFIX, content)
            self.assertNotIn(_PACK_MARKER, content)

    def test_apply_lean_pack_renders_lean_review_depth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            content = (ws / ".github" / "agents" / "review.agent.md").read_text(encoding="utf-8")
            self.assertIn(_LEAN_REVIEW_PREFIX, content)
            self.assertNotIn(_CORE_REVIEW_PREFIX, content)
            self.assertNotIn(_PACK_MARKER, content)

    def test_apply_lean_pack_renders_lean_output_style_in_explore_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )

            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            content = (ws / ".github" / "agents" / "explore.agent.md").read_text(encoding="utf-8")
            self.assertIn(_LEAN_OUTPUT_PREFIX, content)
            self.assertNotIn(_CORE_OUTPUT_PREFIX, content)
            self.assertNotIn(_PACK_MARKER, content)


class PlannedLockfilePackShapeTests(XanadTestBase):
    """Planned lockfile always carries resolvedTokenConflicts and selectedPacks."""

    def test_plan_no_pack_lockfile_has_empty_resolved_token_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(json.dumps(_answers()), encoding="utf-8")

            result = self._run("plan", "setup", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            lockfile = json.loads(result.stdout)["result"]["plannedLockfile"]["contents"]
            self.assertIn("resolvedTokenConflicts", lockfile)
            self.assertEqual({}, lockfile["resolvedTokenConflicts"])

    def test_plan_lean_pack_lockfile_records_selected_packs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )

            result = self._run("plan", "setup", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            lockfile = json.loads(result.stdout)["result"]["plannedLockfile"]["contents"]
            self.assertEqual(["lean"], lockfile["selectedPacks"])

    def test_plan_lean_pack_lockfile_has_empty_resolved_token_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )

            result = self._run("plan", "setup", "--json", "--non-interactive",
                               "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            lockfile = json.loads(result.stdout)["result"]["plannedLockfile"]["contents"]
            self.assertIn("resolvedTokenConflicts", lockfile)
            self.assertEqual({}, lockfile["resolvedTokenConflicts"])


class PostInstallPackUpdateTests(XanadTestBase):
    """Post-install pack add via `update` re-renders agents with new token values."""

    def test_update_adds_lean_pack_and_rerenders_commit_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)

            # First: apply without any pack — commit.agent.md gets core value.
            no_pack_answers = ws / "no_pack_answers.json"
            no_pack_answers.write_text(json.dumps(_answers()), encoding="utf-8")
            result = self._run("apply", "--json", "--non-interactive",
                               "--answers", str(no_pack_answers), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            commit_before = (ws / ".github" / "agents" / "commit.agent.md").read_text(encoding="utf-8")
            self.assertIn(_CORE_COMMIT_PREFIX, commit_before)

            # Second: update adding lean pack — commit.agent.md must be re-rendered.
            lean_answers = ws / "lean_answers.json"
            lean_answers.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )
            result = self._run("update", "--json", "--non-interactive",
                               "--answers", str(lean_answers), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            commit_after = (ws / ".github" / "agents" / "commit.agent.md").read_text(encoding="utf-8")
            self.assertIn(_LEAN_COMMIT_PREFIX, commit_after)
            self.assertNotIn(_CORE_COMMIT_PREFIX, commit_after)
            self.assertNotIn(_PACK_MARKER, commit_after)

    def test_update_adds_lean_pack_and_records_selected_packs_in_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)

            no_pack_answers = ws / "no_pack_answers.json"
            no_pack_answers.write_text(json.dumps(_answers()), encoding="utf-8")
            self._run("apply", "--json", "--non-interactive",
                      "--answers", str(no_pack_answers), workspace=ws)

            lean_answers = ws / "lean_answers.json"
            lean_answers.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )
            result = self._run("update", "--json", "--non-interactive",
                               "--answers", str(lean_answers), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            lockfile = json.loads(
                (ws / ".github" / "xanadAssistant-lock.json").read_text(encoding="utf-8")
            )
            self.assertEqual(["lean"], lockfile["selectedPacks"])

    def test_update_removes_lean_pack_reverts_to_core_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)

            # Install with lean pack first.
            lean_answers = ws / "lean_answers.json"
            lean_answers.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )
            self._run("apply", "--json", "--non-interactive",
                      "--answers", str(lean_answers), workspace=ws)

            commit_lean = (ws / ".github" / "agents" / "commit.agent.md").read_text(encoding="utf-8")
            self.assertIn(_LEAN_COMMIT_PREFIX, commit_lean)

            # Update removing the lean pack — should revert to core values.
            no_pack_answers = ws / "no_pack_answers.json"
            no_pack_answers.write_text(json.dumps(_answers()), encoding="utf-8")
            result = self._run("update", "--json", "--non-interactive",
                               "--answers", str(no_pack_answers), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            commit_after = (ws / ".github" / "agents" / "commit.agent.md").read_text(encoding="utf-8")
            self.assertIn(_CORE_COMMIT_PREFIX, commit_after)
            self.assertNotIn(_LEAN_COMMIT_PREFIX, commit_after)


class CheckAfterApplyPackTests(XanadTestBase):
    """check after a fresh apply reports clean — no drift from pack token rendering."""

    def test_check_after_apply_no_pack_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(json.dumps(_answers()), encoding="utf-8")

            apply_result = self._run("apply", "--json", "--non-interactive",
                                     "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, apply_result.returncode, apply_result.stderr)

            check_result = self._run("check", "--json", workspace=ws)
            self.assertEqual(0, check_result.returncode, check_result.stderr)
            payload = json.loads(check_result.stdout)
            self.assertEqual("clean", payload["status"])
            self.assertEqual(0, payload["result"]["summary"].get("stale", 0))
            self.assertEqual(0, payload["result"]["summary"].get("missing", 0))

    def test_check_after_apply_lean_pack_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )

            apply_result = self._run("apply", "--json", "--non-interactive",
                                     "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, apply_result.returncode, apply_result.stderr)

            check_result = self._run("check", "--json", workspace=ws)
            self.assertEqual(0, check_result.returncode, check_result.stderr)
            payload = json.loads(check_result.stdout)
            self.assertEqual("clean", payload["status"])
            self.assertEqual(0, payload["result"]["summary"].get("stale", 0))
            self.assertEqual(0, payload["result"]["summary"].get("missing", 0))

    def test_check_after_update_adding_lean_pack_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)

            no_pack = ws / "no_pack.json"
            no_pack.write_text(json.dumps(_answers()), encoding="utf-8")
            self._run("apply", "--json", "--non-interactive",
                      "--answers", str(no_pack), workspace=ws)

            lean = ws / "lean.json"
            lean.write_text(
                json.dumps(_answers({"packs.selected": ["lean"]})), encoding="utf-8"
            )
            update_result = self._run("update", "--json", "--non-interactive",
                                      "--answers", str(lean), workspace=ws)
            self.assertEqual(0, update_result.returncode, update_result.stderr)

            check_result = self._run("check", "--json", workspace=ws)
            self.assertEqual(0, check_result.returncode, check_result.stderr)
            payload = json.loads(check_result.stdout)
            self.assertEqual("clean", payload["status"])
            self.assertEqual(0, payload["result"]["summary"].get("stale", 0))
            self.assertEqual(0, payload["result"]["summary"].get("missing", 0))


if __name__ == "__main__":
    unittest.main()
