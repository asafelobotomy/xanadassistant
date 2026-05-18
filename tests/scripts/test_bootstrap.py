from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_bootstrap():
    spec = importlib.util.spec_from_file_location("xanadBootstrap", _REPO_ROOT / "xanadBootstrap.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load xanadBootstrap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_bootstrap = _load_bootstrap()


class CacheKeyTests(unittest.TestCase):
    def test_cache_key_avoids_collision_between_slash_and_hyphen_ref(self) -> None:
        key_slash = _bootstrap._cache_key("feature/x")
        key_hyphen = _bootstrap._cache_key("feature-x")
        self.assertNotEqual(key_slash, key_hyphen)

    def test_cache_key_produces_readable_slug_prefix(self) -> None:
        key = _bootstrap._cache_key("feature/my-branch")
        # Slug must not start with a digest-only string; human-readable prefix expected
        self.assertTrue(key.startswith("feature-my-branch-"))

    def test_cache_key_appends_twelve_char_hex_digest(self) -> None:
        key = _bootstrap._cache_key("main")
        parts = key.rsplit("-", 1)
        self.assertEqual(len(parts), 2)
        digest = parts[1]
        self.assertEqual(len(digest), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in digest))

    def test_cache_key_is_deterministic(self) -> None:
        self.assertEqual(_bootstrap._cache_key("v1.0.0"), _bootstrap._cache_key("v1.0.0"))

    def test_cache_key_sanitises_special_characters(self) -> None:
        key = _bootstrap._cache_key("refs/heads/feat@2024")
        # No raw slashes or @ characters in the key
        self.assertNotIn("/", key)
        self.assertNotIn("@", key)


if __name__ == "__main__":
    unittest.main()
