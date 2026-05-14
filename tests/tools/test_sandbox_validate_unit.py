"""Unit tests for scripts/_sandbox_validate.py — pure function coverage."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import _sandbox_validate as validate


class TestStaleIds(unittest.TestCase):
    def test_extracts_stale_ids_sorted(self) -> None:
        stdout = json.dumps({
            "result": {
                "entries": [
                    {"id": "c.md", "status": "stale"},
                    {"id": "a.md", "status": "stale"},
                    {"id": "b.md", "status": "clean"},
                ]
            }
        })
        self.assertEqual(["a.md", "c.md"], validate._stale_ids(stdout))

    def test_returns_empty_on_invalid_json(self) -> None:
        self.assertEqual([], validate._stale_ids("not-valid-json"))

    def test_returns_empty_on_empty_string(self) -> None:
        self.assertEqual([], validate._stale_ids(""))

    def test_returns_empty_when_no_stale_entries(self) -> None:
        stdout = json.dumps({"result": {"entries": [
            {"id": "a.md", "status": "clean"},
            {"id": "b.md", "status": "present"},
        ]}})
        self.assertEqual([], validate._stale_ids(stdout))

    def test_returns_empty_on_empty_entries_list(self) -> None:
        stdout = json.dumps({"result": {"entries": []}})
        self.assertEqual([], validate._stale_ids(stdout))

    def test_returns_empty_on_missing_result_key(self) -> None:
        self.assertEqual([], validate._stale_ids(json.dumps({"other": "data"})))

    def test_handles_missing_id_key_gracefully(self) -> None:
        stdout = json.dumps({"result": {"entries": [{"status": "stale"}]}})
        self.assertEqual([], validate._stale_ids(stdout))

    def test_handles_none_entries_gracefully(self) -> None:
        stdout = json.dumps({"result": {"entries": None}})
        self.assertEqual([], validate._stale_ids(stdout))

    def test_all_stale_returns_all_ids_sorted(self) -> None:
        stdout = json.dumps({
            "result": {
                "entries": [
                    {"id": "z.md", "status": "stale"},
                    {"id": "a.md", "status": "stale"},
                    {"id": "m.md", "status": "stale"},
                ]
            }
        })
        self.assertEqual(["a.md", "m.md", "z.md"], validate._stale_ids(stdout))

    def test_mixed_status_only_returns_stale(self) -> None:
        stdout = json.dumps({
            "result": {
                "entries": [
                    {"id": "a.md", "status": "stale"},
                    {"id": "b.md", "status": "clean"},
                    {"id": "c.md", "status": "stale"},
                    {"id": "d.md", "status": "missing"},
                ]
            }
        })
        self.assertEqual(["a.md", "c.md"], validate._stale_ids(stdout))


if __name__ == "__main__":
    unittest.main()
