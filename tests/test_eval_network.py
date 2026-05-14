"""Network integration tests for the eval harness.

These tests make live calls to GitHub Models to verify the triage eval harness
end-to-end. They require XANAD_EVAL_ENABLED=1 **and** a GITHUB_TOKEN env var
with models:read scope, and are skipped otherwise.

Run with:
    XANAD_EVAL_ENABLED=1 GITHUB_TOKEN=<token> python3 -m unittest tests.test_eval_network -v
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

EVAL_ENABLED = bool(os.getenv("XANAD_EVAL_ENABLED")) and bool(os.getenv("GITHUB_TOKEN"))

import _eval_tasks as _tasks


@unittest.skipUnless(EVAL_ENABLED, "XANAD_EVAL_ENABLED=1 and GITHUB_TOKEN required")
class TestTriageEvalNetwork(unittest.TestCase):
    """End-to-end smoke test: run eval, verify structure and scoring dimensions."""

    @classmethod
    def setUpClass(cls) -> None:
        import _eval_triage
        cls.data = _eval_triage.run()

    def test_result_has_required_top_level_keys(self) -> None:
        for key in ("generated", "agent", "model", "tasks"):
            with self.subTest(key=key):
                self.assertIn(key, self.data)

    def test_agent_field_is_triage(self) -> None:
        self.assertEqual("triage", self.data["agent"])

    def test_task_count_matches_definitions(self) -> None:
        self.assertEqual(len(_tasks.TRIAGE_TASKS), len(self.data["tasks"]))

    def test_each_task_has_treatment_and_control(self) -> None:
        for entry in self.data["tasks"]:
            with self.subTest(task=entry["task"]):
                self.assertIn("treatment", entry)
                self.assertIn("control", entry)

    def test_treatment_prompt_tokens_greater_than_control(self) -> None:
        """Treatment has a system prompt; should consume more prompt tokens."""
        for entry in self.data["tasks"]:
            with self.subTest(task=entry["task"]):
                self.assertGreater(
                    entry["treatment"]["prompt_tokens"],
                    entry["control"]["prompt_tokens"],
                )

    def test_score_dimensions_present(self) -> None:
        dims = ("format_valid", "tier_correct", "blocker_correct", "score")
        for entry in self.data["tasks"]:
            for arm in ("treatment", "control"):
                sc = entry[arm]["score"]
                with self.subTest(task=entry["task"], arm=arm):
                    for dim in dims:
                        self.assertIn(dim, sc)

    def test_score_field_is_non_negative_int(self) -> None:
        for entry in self.data["tasks"]:
            for arm in ("treatment", "control"):
                with self.subTest(task=entry["task"], arm=arm):
                    self.assertIsInstance(entry[arm]["score"]["score"], int)
                    self.assertGreaterEqual(entry[arm]["score"]["score"], 0)

    def test_latency_is_positive(self) -> None:
        for entry in self.data["tasks"]:
            for arm in ("treatment", "control"):
                with self.subTest(task=entry["task"], arm=arm):
                    self.assertGreater(entry[arm]["latency_ms"], 0)

    def test_treatment_format_valid_rate_at_least_80_pct(self) -> None:
        """Treatment arm should reliably produce parseable output."""
        valid = sum(
            1 for e in self.data["tasks"]
            if e["treatment"]["score"]["format_valid"]
        )
        pct = valid / len(self.data["tasks"])
        self.assertGreaterEqual(
            pct, 0.8,
            msg=f"Only {valid}/{len(self.data['tasks'])} treatment responses parsed correctly",
        )


if __name__ == "__main__":
    unittest.main()
