"""Unit tests for scripts/_sandbox_benchmark.py — pure function coverage."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import _sandbox_benchmark as bench


class TestPercentile(unittest.TestCase):
    def test_p0_returns_first_element(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(1.0, bench._percentile(data, 0.0))

    def test_p100_returns_last_element(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(5.0, bench._percentile(data, 1.0))

    def test_p50_of_4_element_list(self) -> None:
        data = [10.0, 20.0, 30.0, 40.0]
        # idx = min(int(0.5 * 4), 3) = min(2, 3) = 2 → data[2] = 30.0
        self.assertEqual(30.0, bench._percentile(data, 0.50))

    def test_p95_of_100_elements(self) -> None:
        data = sorted(float(i) for i in range(100))
        # idx = min(int(0.95 * 100), 99) = min(95, 99) = 95 → data[95] = 95.0
        self.assertEqual(95.0, bench._percentile(data, 0.95))

    def test_single_element_any_percentile(self) -> None:
        self.assertEqual(42.0, bench._percentile([42.0], 0.0))
        self.assertEqual(42.0, bench._percentile([42.0], 0.5))
        self.assertEqual(42.0, bench._percentile([42.0], 1.0))

    def test_p5_of_20_elements(self) -> None:
        data = sorted(float(i) for i in range(20))
        # idx = min(int(0.05 * 20), 19) = min(1, 19) = 1 → data[1] = 1.0
        self.assertEqual(1.0, bench._percentile(data, 0.05))


class TestBenchmarkConstants(unittest.TestCase):
    def test_timed_runs_greater_than_warmup(self) -> None:
        self.assertGreater(bench._TIMED_RUNS, bench._TIMED_WARMUP)

    def test_measured_samples_are_positive(self) -> None:
        measured = bench._TIMED_RUNS - bench._TIMED_WARMUP
        self.assertGreater(measured, 0)

    def test_results_dir_is_under_repo_root(self) -> None:
        self.assertTrue(str(bench.RESULTS_DIR).startswith(str(bench.REPO_ROOT)))

    def test_timed_runs_at_least_5(self) -> None:
        self.assertGreaterEqual(bench._TIMED_RUNS, 5)


class TestSaveResults(unittest.TestCase):
    def _call_save(self, tmpdir: Path) -> Path:
        orig = bench.RESULTS_DIR
        bench.RESULTS_DIR = tmpdir
        try:
            bench._save_results(
                {"ws-a": {"inspect": {"p50_ms": 100.0}, "check": {"p50_ms": 110.0}}},
                {"inspect": 90.0, "check": 95.0},
                {"inspect": 190.0, "check": 195.0},
                bench._TIMED_RUNS - bench._TIMED_WARMUP,
            )
        finally:
            bench.RESULTS_DIR = orig
        return tmpdir

    def test_save_results_creates_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._call_save(Path(tmp))
            files = list(Path(tmp).glob("bench-*.json"))
            self.assertEqual(1, len(files))

    def test_save_results_payload_has_required_keys(self) -> None:
        required = {"generated", "mode", "runs", "warmup", "measured",
                    "control_baseline", "agent_avg", "workspaces"}
        with tempfile.TemporaryDirectory() as tmp:
            self._call_save(Path(tmp))
            out = next(Path(tmp).glob("bench-*.json"))
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(required, set(payload.keys()))

    def test_save_results_mode_is_timed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._call_save(Path(tmp))
            out = next(Path(tmp).glob("bench-*.json"))
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual("timed", payload["mode"])

    def test_save_results_runs_matches_constant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._call_save(Path(tmp))
            out = next(Path(tmp).glob("bench-*.json"))
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(bench._TIMED_RUNS, payload["runs"])
            self.assertEqual(bench._TIMED_WARMUP, payload["warmup"])

    def test_save_results_control_baseline_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._call_save(Path(tmp))
            out = next(Path(tmp).glob("bench-*.json"))
            payload = json.loads(out.read_text(encoding="utf-8"))
            baseline = payload["control_baseline"]
            self.assertIn("inspect_p50_ms", baseline)
            self.assertIn("check_p50_ms", baseline)

    def test_save_results_workspaces_data_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._call_save(Path(tmp))
            out = next(Path(tmp).glob("bench-*.json"))
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("ws-a", payload["workspaces"])


if __name__ == "__main__":
    unittest.main()
