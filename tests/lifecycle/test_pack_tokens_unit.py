"""Unit tests for scripts/lifecycle/_xanad/_pack_tokens.py — pack token loading and resolution."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._pack_tokens import load_pack_tokens
from scripts.lifecycle._xanad._conditions import resolve_token_values

REPO_ROOT = Path(__file__).resolve().parents[2]

_MINIMAL_POLICY = {
    "tokenRules": [
        {"token": "{{WORKSPACE_NAME}}", "required": False},
        {"token": "{{pack:commit-style}}", "required": False},
        {"token": "{{pack:output-style}}", "required": False},
    ]
}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class LoadPackTokensNoCoreTests(unittest.TestCase):
    """load_pack_tokens returns empty dict when no pack token files exist."""

    def test_no_files_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = load_pack_tokens(Path(tmp), [])
        self.assertEqual({}, result)

    def test_selected_packs_without_files_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = load_pack_tokens(Path(tmp), ["lean"])
        self.assertEqual({}, result)


class LoadPackTokensCoreOnlyTests(unittest.TestCase):
    """Core defaults are loaded when no packs are selected."""

    def test_core_defaults_wrapped_in_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {
                "pack:commit-style": "Conventional Commits.",
                "pack:output-style": "Thorough.",
            })
            result = load_pack_tokens(root, [])
        self.assertEqual("Conventional Commits.", result["{{pack:commit-style}}"])
        self.assertEqual("Thorough.", result["{{pack:output-style}}"])

    def test_keys_use_double_brace_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:plan-format": "Full plan."})
            result = load_pack_tokens(root, [])
        self.assertIn("{{pack:plan-format}}", result)
        self.assertNotIn("pack:plan-format", result)


class LoadPackTokensPackOverrideTests(unittest.TestCase):
    """Selected pack values override core defaults."""

    def test_lean_overrides_core_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:commit-style": "Full message."})
            _write_json(root / "packs" / "lean" / "tokens.json", {"pack:commit-style": "One-liner."})
            result = load_pack_tokens(root, ["lean"])
        self.assertEqual("One-liner.", result["{{pack:commit-style}}"])

    def test_pack_does_not_add_unknown_tokens_from_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:review-depth": "All severities."})
            _write_json(root / "packs" / "lean" / "tokens.json", {"pack:commit-style": "Terse."})
            result = load_pack_tokens(root, ["lean"])
        self.assertEqual("All severities.", result["{{pack:review-depth}}"])
        self.assertEqual("Terse.", result["{{pack:commit-style}}"])

    def test_pack_only_token_not_in_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "lean" / "tokens.json", {"pack:extra": "Extra value."})
            result = load_pack_tokens(root, ["lean"])
        self.assertEqual("Extra value.", result["{{pack:extra}}"])


class LoadPackTokensResilienceTests(unittest.TestCase):
    """Malformed or absent files are silently skipped."""

    def test_malformed_core_json_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core_path = root / "packs" / "core" / "tokens.json"
            core_path.parent.mkdir(parents=True)
            core_path.write_text("not valid json", encoding="utf-8")
            result = load_pack_tokens(root, [])
        self.assertEqual({}, result)

    def test_malformed_pack_json_skipped_core_still_loads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:commit-style": "Good."})
            bad = root / "packs" / "lean" / "tokens.json"
            bad.parent.mkdir(parents=True)
            bad.write_text("{bad json", encoding="utf-8")
            result = load_pack_tokens(root, ["lean"])
        self.assertEqual("Good.", result["{{pack:commit-style}}"])

    def test_non_string_values_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {
                "pack:commit-style": "Valid.",
                "pack:bad-value": 42,
                "pack:also-bad": None,
            })
            result = load_pack_tokens(root, [])
        self.assertEqual("Valid.", result["{{pack:commit-style}}"])
        self.assertNotIn("{{pack:bad-value}}", result)
        self.assertNotIn("{{pack:also-bad}}", result)


class ResolveTokenValuesPackIntegrationTests(unittest.TestCase):
    """resolve_token_values merges pack tokens when package_root is provided."""

    def test_no_package_root_no_pack_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:commit-style": "Core default."})
            result = resolve_token_values(_MINIMAL_POLICY, root, {})
        self.assertNotIn("{{pack:commit-style}}", result)

    def test_package_root_without_packs_selected_uses_core_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:commit-style": "Core default."})
            result = resolve_token_values(_MINIMAL_POLICY, root, {}, package_root=root)
        self.assertEqual("Core default.", result["{{pack:commit-style}}"])

    def test_lean_pack_selected_overrides_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:commit-style": "Full message."})
            _write_json(root / "packs" / "lean" / "tokens.json", {"pack:commit-style": "One-liner."})
            result = resolve_token_values(
                _MINIMAL_POLICY, root, {"packs.selected": ["lean"]}, package_root=root
            )
        self.assertEqual("One-liner.", result["{{pack:commit-style}}"])

    def test_workspace_tokens_coexist_with_pack_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_json(root / "packs" / "core" / "tokens.json", {"pack:output-style": "Thorough."})
            result = resolve_token_values(_MINIMAL_POLICY, root, {}, package_root=root)
        self.assertEqual(root.name, result["{{WORKSPACE_NAME}}"])
        self.assertEqual("Thorough.", result["{{pack:output-style}}"])

    def test_real_repo_pack_tokens_resolve(self) -> None:
        """Core defaults and lean overrides load correctly from the real packs/ tree."""
        result_no_lean = resolve_token_values(
            _MINIMAL_POLICY, REPO_ROOT, {}, package_root=REPO_ROOT
        )
        result_lean = resolve_token_values(
            _MINIMAL_POLICY, REPO_ROOT, {"packs.selected": ["lean"]}, package_root=REPO_ROOT
        )
        self.assertIn("{{pack:commit-style}}", result_no_lean)
        self.assertIn("{{pack:commit-style}}", result_lean)
        self.assertNotEqual(
            result_no_lean["{{pack:commit-style}}"],
            result_lean["{{pack:commit-style}}"],
            "Lean pack should override core commit-style token",
        )


if __name__ == "__main__":
    unittest.main()
