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
import tempfile
import unittest
from pathlib import Path

from tests._test_base import XanadTestBase, run_lifecycle_subprocess

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



class ConflictGateTests(XanadTestBase):
    """Two packs with a shared token key must block the plan until a winner is chosen.

    Uses packs/alpha/tokens.json and packs/beta/tokens.json, both of which define
    pack:output-style.  A temporary package root is built in setUpClass that
    registers alpha and beta as active optional packs so the answer validator
    accepts them.  The real repo's pack-registry.json is not modified.
    """

    _temp_pkg_dir: str | None = None
    _temp_pkg: Path

    @classmethod
    def setUpClass(cls) -> None:
        """Copy the repo to a temp dir and register alpha/beta as active test packs."""
        cls._temp_pkg_dir = tempfile.mkdtemp()
        cls._temp_pkg = Path(cls._temp_pkg_dir)
        shutil.copytree(
            str(cls.REPO_ROOT), cls._temp_pkg_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git"),
        )

        # Register alpha/beta as active optional packs (no surfaces — token-only).
        registry_path = cls._temp_pkg / "template" / "setup" / "pack-registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["packs"].extend([
            {
                "id": "alpha", "name": "Alpha Fixture",
                "summary": "Test fixture pack for conflict resolution testing.",
                "status": "active", "optional": True,
                "dependencies": [], "discoveryTags": ["test"], "surfaces": [],
            },
            {
                "id": "beta", "name": "Beta Fixture",
                "summary": "Test fixture pack for conflict resolution testing.",
                "status": "active", "optional": True,
                "dependencies": [], "discoveryTags": ["test"], "surfaces": [],
            },
            {
                "id": "gamma", "name": "Gamma Fixture",
                "summary": "Test fixture pack for 3-pack conflict resolution testing.",
                "status": "active", "optional": True,
                "dependencies": [], "discoveryTags": ["test"], "surfaces": [],
            },
        ])
        registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

        # Create gamma fixture pack tokens (not in real repo; only in temp).
        gamma_dir = cls._temp_pkg / "packs" / "gamma"
        gamma_dir.mkdir(parents=True, exist_ok=True)
        (gamma_dir / "tokens.json").write_text(
            json.dumps({"pack:output-style": "Gamma pack output style: step-by-step procedures."}),
            encoding="utf-8",
        )

        # Regenerate catalog so the temp package root is self-consistent.
        from scripts.lifecycle.generate_manifest import generate_catalog
        from scripts.lifecycle._xanad._loader import load_optional_json as _loj
        policy = _loj(cls._temp_pkg / "template" / "setup" / "install-policy.json") or {}
        profile_registry = _loj(cls._temp_pkg / "template" / "setup" / "profile-registry.json") or {}
        catalog = generate_catalog(policy, registry, profile_registry)
        catalog_path = cls._temp_pkg / "template" / "setup" / "catalog.json"
        catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._temp_pkg_dir:
            shutil.rmtree(cls._temp_pkg_dir, ignore_errors=True)

    def _run_conflict(self, command: str, *extra_args: str, workspace: Path) -> subprocess.CompletedProcess[str]:
        """Run lifecycle command using the temp package root with alpha/beta registered."""
        return run_lifecycle_subprocess(
            command, *extra_args,
            workspace=workspace,
            repo_root=self._temp_pkg,
        )

    # ------------------------------------------------------------------
    # Non-interactive: plan exits 6
    # ------------------------------------------------------------------

    def test_plan_conflicting_packs_non_interactive_exits_6(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["alpha", "beta"]})), encoding="utf-8"
            )

            result = self._run_conflict("plan", "setup", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(6, result.returncode, result.stderr)

    def test_apply_conflicting_packs_non_interactive_exits_6(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["alpha", "beta"]})), encoding="utf-8"
            )

            result = self._run_conflict("apply", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(6, result.returncode, result.stderr)

    # ------------------------------------------------------------------
    # Interactive: plan returns blocked result
    # ------------------------------------------------------------------

    def test_plan_conflicting_packs_interactive_returns_blocked_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["alpha", "beta"]})), encoding="utf-8"
            )

            # Without --non-interactive the command exits 0 with a blocked plan.
            result = self._run_conflict("plan", "setup", "--json",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            payload = json.loads(result.stdout)
            self.assertEqual("approval-required", payload["status"])
            self.assertFalse(payload["result"]["questionsResolved"])
            self.assertIsNone(payload["result"]["plannedLockfile"])
            self.assertEqual([], payload["result"]["actions"])

    def test_plan_conflicting_packs_reports_conflict_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["alpha", "beta"]})), encoding="utf-8"
            )

            result = self._run_conflict("plan", "setup", "--json",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            conflict_details = json.loads(result.stdout)["result"]["conflictDetails"]
            self.assertEqual(1, len(conflict_details))
            conflict = conflict_details[0]
            self.assertEqual("pack:output-style", conflict["token"])
            self.assertEqual("resolvedTokenConflicts.pack:output-style", conflict["questionId"])
            self.assertIn("alpha", conflict["packs"])
            self.assertIn("beta", conflict["packs"])

    # ------------------------------------------------------------------
    # Conflict resolved: plan and apply proceed
    # ------------------------------------------------------------------

    def test_plan_conflict_resolved_to_alpha_proceeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({
                    "packs.selected": ["alpha", "beta"],
                    "resolvedTokenConflicts.pack:output-style": "alpha",
                })), encoding="utf-8"
            )

            result = self._run_conflict("plan", "setup", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            payload = json.loads(result.stdout)
            self.assertTrue(payload["result"]["questionsResolved"])
            self.assertIsNotNone(payload["result"]["plannedLockfile"])
            self.assertEqual([], payload["result"]["conflictDetails"])

    def test_plan_conflict_resolved_lockfile_records_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({
                    "packs.selected": ["alpha", "beta"],
                    "resolvedTokenConflicts.pack:output-style": "alpha",
                })), encoding="utf-8"
            )

            result = self._run_conflict("plan", "setup", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            lockfile = json.loads(result.stdout)["result"]["plannedLockfile"]["contents"]
            self.assertEqual({"pack:output-style": "alpha"}, lockfile["resolvedTokenConflicts"])

    def test_apply_conflict_resolved_to_alpha_uses_alpha_output_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({
                    "packs.selected": ["alpha", "beta"],
                    "resolvedTokenConflicts.pack:output-style": "alpha",
                })), encoding="utf-8"
            )

            result = self._run_conflict("apply", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            content = (ws / ".github" / "agents" / "explore.agent.md").read_text(encoding="utf-8")
            self.assertIn(_ALPHA_OUTPUT_PREFIX, content)
            self.assertNotIn(_BETA_OUTPUT_PREFIX, content)
            self.assertNotIn(_PACK_MARKER, content)

    def test_apply_conflict_resolved_to_beta_uses_beta_output_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({
                    "packs.selected": ["alpha", "beta"],
                    "resolvedTokenConflicts.pack:output-style": "beta",
                })), encoding="utf-8"
            )

            result = self._run_conflict("apply", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            content = (ws / ".github" / "agents" / "explore.agent.md").read_text(encoding="utf-8")
            self.assertIn(_BETA_OUTPUT_PREFIX, content)
            self.assertNotIn(_ALPHA_OUTPUT_PREFIX, content)
            self.assertNotIn(_PACK_MARKER, content)

    def test_apply_conflict_resolved_writes_winner_to_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({
                    "packs.selected": ["alpha", "beta"],
                    "resolvedTokenConflicts.pack:output-style": "beta",
                })), encoding="utf-8"
            )

            result = self._run_conflict("apply", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            lockfile = json.loads(
                (ws / ".github" / "xanadAssistant-lock.json").read_text(encoding="utf-8")
            )
            self.assertEqual({"pack:output-style": "beta"}, lockfile["resolvedTokenConflicts"])

    def test_check_after_apply_with_conflict_resolved_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({
                    "packs.selected": ["alpha", "beta"],
                    "resolvedTokenConflicts.pack:output-style": "alpha",
                })), encoding="utf-8"
            )

            apply_result = self._run_conflict("apply", "--json", "--non-interactive",
                                              "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, apply_result.returncode, apply_result.stderr)

            check_result = self._run_conflict("check", "--json", workspace=ws)
            self.assertEqual(0, check_result.returncode, check_result.stderr)
            payload = json.loads(check_result.stdout)
            self.assertEqual("clean", payload["status"])
            self.assertEqual(0, payload["result"]["summary"].get("stale", 0))
            self.assertEqual(0, payload["result"]["summary"].get("missing", 0))

    # ------------------------------------------------------------------
    # F-07: 3-pack conflict — all three packs reported
    # ------------------------------------------------------------------

    def test_plan_three_pack_conflict_reports_all_three_packs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["alpha", "beta", "gamma"]})),
                encoding="utf-8",
            )

            result = self._run_conflict("plan", "setup", "--json",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            conflict_details = json.loads(result.stdout)["result"]["conflictDetails"]
            self.assertEqual(1, len(conflict_details))
            self.assertCountEqual(["alpha", "beta", "gamma"], conflict_details[0]["packs"])

    # ------------------------------------------------------------------
    # F-08: lockfile seeds conflict resolution when no answer is provided
    # ------------------------------------------------------------------

    def test_plan_uses_lockfile_resolution_when_no_answer_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"

            # Step 1: apply with explicit resolution — writes lockfile.
            answers_path.write_text(
                json.dumps(_answers({
                    "packs.selected": ["alpha", "beta"],
                    "resolvedTokenConflicts.pack:output-style": "alpha",
                })), encoding="utf-8",
            )
            apply_result = self._run_conflict("apply", "--json", "--non-interactive",
                                              "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, apply_result.returncode, apply_result.stderr)

            # Step 2: plan again with same packs but no conflict answer.
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["alpha", "beta"]})),
                encoding="utf-8",
            )
            result = self._run_conflict("plan", "setup", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

            payload = json.loads(result.stdout)
            self.assertTrue(payload["result"]["questionsResolved"])
            self.assertEqual([], payload["result"]["conflictDetails"])


if __name__ == "__main__":
    unittest.main()
