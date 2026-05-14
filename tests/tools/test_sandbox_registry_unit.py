"""Unit tests for scripts/_sandbox_registry.py — shape and metadata validation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import _sandbox_registry as registry
from _sandbox_control_workspaces import CONTROL_WORKSPACES
from _sandbox_core_workspaces import CORE_WORKSPACES
from _sandbox_pack_workspaces import PACK_WORKSPACES


def _valid_entry() -> dict:
    return {
        "desc": "test workspace",
        "fn": lambda ws: None,
        "expected_state": "not-installed",
        "expected_exit_codes": {"inspect": 0, "check": 7},
        "expected_findings": [],
    }


class TestValidateEntry(unittest.TestCase):
    def test_valid_entry_returns_no_errors(self) -> None:
        self.assertEqual([], registry.validate_entry("ws", _valid_entry()))

    def test_missing_desc_returns_error(self) -> None:
        e = _valid_entry()
        del e["desc"]
        errors = registry.validate_entry("ws", e)
        self.assertTrue(any("desc" in err for err in errors))

    def test_missing_fn_returns_error(self) -> None:
        e = _valid_entry()
        del e["fn"]
        errors = registry.validate_entry("ws", e)
        self.assertTrue(any("fn" in err for err in errors))

    def test_missing_expected_state_returns_error(self) -> None:
        e = _valid_entry()
        del e["expected_state"]
        errors = registry.validate_entry("ws", e)
        self.assertTrue(any("expected_state" in err for err in errors))

    def test_missing_expected_exit_codes_returns_error(self) -> None:
        e = _valid_entry()
        del e["expected_exit_codes"]
        errors = registry.validate_entry("ws", e)
        self.assertTrue(any("expected_exit_codes" in err for err in errors))

    def test_exit_codes_missing_check_returns_error(self) -> None:
        e = _valid_entry()
        e["expected_exit_codes"] = {"inspect": 0}
        errors = registry.validate_entry("ws", e)
        self.assertTrue(any("check" in err for err in errors))

    def test_exit_codes_missing_inspect_returns_error(self) -> None:
        e = _valid_entry()
        e["expected_exit_codes"] = {"check": 0}
        errors = registry.validate_entry("ws", e)
        self.assertTrue(any("inspect" in err for err in errors))

    def test_exit_codes_non_dict_returns_error(self) -> None:
        e = _valid_entry()
        e["expected_exit_codes"] = "bad"
        errors = registry.validate_entry("ws", e)
        self.assertTrue(len(errors) > 0)

    def test_expected_findings_none_is_valid(self) -> None:
        e = _valid_entry()
        e["expected_findings"] = None
        self.assertEqual([], registry.validate_entry("ws", e))

    def test_expected_findings_list_is_valid(self) -> None:
        e = _valid_entry()
        e["expected_findings"] = ["a.md", "b.md"]
        self.assertEqual([], registry.validate_entry("ws", e))

    def test_expected_findings_non_list_returns_error(self) -> None:
        e = _valid_entry()
        e["expected_findings"] = "bad"
        errors = registry.validate_entry("ws", e)
        self.assertTrue(any("expected_findings" in err for err in errors))

    def test_error_message_includes_workspace_name(self) -> None:
        e = _valid_entry()
        del e["desc"]
        errors = registry.validate_entry("my-workspace", e)
        self.assertTrue(any("my-workspace" in err for err in errors))


class TestValidateWorkspaceDict(unittest.TestCase):
    def test_empty_dict_is_valid(self) -> None:
        self.assertEqual([], registry.validate_workspace_dict({}))

    def test_skip_missing_meta_skips_entries_without_exit_codes(self) -> None:
        workspaces = {
            "no-meta": {"desc": "x", "fn": None, "expected_state": "installed"},
        }
        errors = registry.validate_workspace_dict(workspaces, skip_missing_meta=True)
        self.assertEqual([], errors)

    def test_skip_missing_meta_false_reports_incomplete_entries(self) -> None:
        workspaces = {
            "no-meta": {"desc": "x", "fn": None, "expected_state": "installed"},
        }
        errors = registry.validate_workspace_dict(workspaces, skip_missing_meta=False)
        self.assertTrue(len(errors) > 0)

    def test_multiple_invalid_entries_all_reported(self) -> None:
        workspaces = {
            "ws-a": {"desc": "a"},
            "ws-b": {"fn": None},
        }
        errors = registry.validate_workspace_dict(workspaces)
        names = [e for e in errors if "ws-a" in e or "ws-b" in e]
        self.assertTrue(len(names) >= 2)


class TestCoreWorkspacesRegistry(unittest.TestCase):
    def test_all_core_entries_are_valid(self) -> None:
        errors = registry.validate_workspace_dict(CORE_WORKSPACES)
        self.assertEqual([], errors, "Registry errors:\n" + "\n".join(errors))

    def test_core_workspaces_all_not_installed(self) -> None:
        for name, entry in CORE_WORKSPACES.items():
            with self.subTest(name=name):
                self.assertEqual("not-installed", entry["expected_state"])

    def test_core_workspaces_check_exit_code_is_7(self) -> None:
        for name, entry in CORE_WORKSPACES.items():
            with self.subTest(name=name):
                self.assertEqual(7, entry["expected_exit_codes"]["check"])

    def test_core_workspaces_inspect_exit_code_is_0(self) -> None:
        for name, entry in CORE_WORKSPACES.items():
            with self.subTest(name=name):
                self.assertEqual(0, entry["expected_exit_codes"]["inspect"])

    def test_core_workspaces_findings_are_lists(self) -> None:
        for name, entry in CORE_WORKSPACES.items():
            with self.subTest(name=name):
                self.assertIsInstance(entry["expected_findings"], list)

    def test_core_workspaces_count_includes_new_scenarios(self) -> None:
        self.assertGreaterEqual(len(CORE_WORKSPACES), 21)


class TestPackWorkspacesRegistry(unittest.TestCase):
    def test_all_pack_entries_are_valid(self) -> None:
        errors = registry.validate_workspace_dict(PACK_WORKSPACES)
        self.assertEqual([], errors, "\n".join(errors))

    def test_pack_workspaces_all_installed(self) -> None:
        for name, entry in PACK_WORKSPACES.items():
            with self.subTest(name=name):
                self.assertEqual("installed", entry["expected_state"])

    def test_pack_workspaces_check_exit_code_is_0(self) -> None:
        for name, entry in PACK_WORKSPACES.items():
            with self.subTest(name=name):
                self.assertEqual(0, entry["expected_exit_codes"]["check"])

    def test_pack_workspaces_count(self) -> None:
        self.assertEqual(17, len(PACK_WORKSPACES))


class TestControlWorkspacesRegistry(unittest.TestCase):
    def test_all_control_entries_are_valid(self) -> None:
        errors = registry.validate_workspace_dict(CONTROL_WORKSPACES)
        self.assertEqual([], errors, "\n".join(errors))

    def test_control_workspaces_all_installed(self) -> None:
        for name, entry in CONTROL_WORKSPACES.items():
            with self.subTest(name=name):
                self.assertEqual("installed", entry["expected_state"])

    def test_control_workspaces_check_exit_code_is_0(self) -> None:
        for name, entry in CONTROL_WORKSPACES.items():
            with self.subTest(name=name):
                self.assertEqual(0, entry["expected_exit_codes"]["check"])

    def test_control_workspaces_count(self) -> None:
        self.assertEqual(3, len(CONTROL_WORKSPACES))


if __name__ == "__main__":
    unittest.main()
