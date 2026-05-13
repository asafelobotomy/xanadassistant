"""Phase 4 — End-to-end pack token lifecycle tests.

Covers:
1. Token rendering — agent file content after apply (core defaults vs lean pack).
2. Planned lockfile shape — resolvedTokenConflicts field is always present.
3. Post-install pack add via update — agents re-rendered, lockfile updated.
4. Check after apply — no drift for either pack configuration.
5. Multi-pack conflict gating — selecting multiple packs with conflicting tokens
   requires conflict resolution answers; unresolved conflicts exit 6 in non-interactive.

Fixture packs:
  packs/alpha/tokens.json — defines pack:output-style (alpha value)
  packs/beta/tokens.json  — defines pack:output-style (beta value)
Both packs are excluded from the install policy surface and catalog; they
exist solely as token-provider fixtures for conflict-resolution testing.
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
    """Multi-pack selection is allowed; conflicting tokens must be resolved.

    Uses packs/alpha/tokens.json, packs/beta/tokens.json, and packs/gamma/tokens.json
    as test fixtures.  All three define pack:output-style, so any combination of two
    or more creates a token conflict.  In --non-interactive mode with no resolution
    answers the plan exits 6 (approval_or_answers_required).  A temporary package
    root is built in setUpClass that registers alpha, beta, and gamma as active optional
    packs so the answer validator recognises them as valid pack ids.
    """

    _temp_pkg_dir: str | None = None
    _temp_pkg: Path

    @classmethod
    def setUpClass(cls) -> None:
        """Copy the repo to a temp dir and register alpha/beta/gamma as active test packs."""
        cls._temp_pkg_dir = tempfile.mkdtemp()
        cls._temp_pkg = Path(cls._temp_pkg_dir)
        shutil.copytree(
            str(cls.REPO_ROOT), cls._temp_pkg_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git"),
        )

        registry_path = cls._temp_pkg / "template" / "setup" / "pack-registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["packs"].extend([
            {
                "id": "alpha", "name": "Alpha Fixture",
                "summary": "Test fixture pack for max-selections testing.",
                "status": "active", "optional": True,
                "dependencies": [], "discoveryTags": ["test"], "surfaces": [],
            },
            {
                "id": "beta", "name": "Beta Fixture",
                "summary": "Test fixture pack for max-selections testing.",
                "status": "active", "optional": True,
                "dependencies": [], "discoveryTags": ["test"], "surfaces": [],
            },
            {
                "id": "gamma", "name": "Gamma Fixture",
                "summary": "Test fixture pack for max-selections testing.",
                "status": "active", "optional": True,
                "dependencies": [], "discoveryTags": ["test"], "surfaces": [],
            },
        ])
        registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

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
        return run_lifecycle_subprocess(
            command, *extra_args,
            workspace=workspace,
            repo_root=self._temp_pkg,
        )

    # ------------------------------------------------------------------
    # Unresolved conflict: 2+ packs with conflicting tokens → exit 6
    # ------------------------------------------------------------------

    def test_plan_two_conflicting_packs_exits_6(self) -> None:
        """Two packs with a conflicting token and no resolution answer exits 6."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["alpha", "beta"]})), encoding="utf-8"
            )
            result = self._run_conflict("plan", "setup", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(6, result.returncode, result.stderr)

    def test_apply_two_conflicting_packs_exits_6(self) -> None:
        """apply with two conflicting packs and no resolution also exits 6."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["alpha", "beta"]})), encoding="utf-8"
            )
            result = self._run_conflict("apply", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(6, result.returncode, result.stderr)

    def test_plan_three_conflicting_packs_exits_6(self) -> None:
        """Three packs with a conflicting token and no resolution answer exits 6."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["alpha", "beta", "gamma"]})),
                encoding="utf-8",
            )
            result = self._run_conflict("plan", "setup", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(6, result.returncode, result.stderr)

    # ------------------------------------------------------------------
    # Positive: zero or one pack proceeds
    # ------------------------------------------------------------------

    def test_plan_single_pack_proceeds(self) -> None:
        """Selecting exactly one pack is accepted by plan (exit 0)."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": ["alpha"]})), encoding="utf-8"
            )
            result = self._run_conflict("plan", "setup", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_plan_zero_packs_proceeds(self) -> None:
        """Selecting zero packs is also valid (exit 0)."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            answers_path = ws / "answers.json"
            answers_path.write_text(
                json.dumps(_answers({"packs.selected": []})), encoding="utf-8"
            )
            result = self._run_conflict("plan", "setup", "--json", "--non-interactive",
                                        "--answers", str(answers_path), workspace=ws)
            self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
