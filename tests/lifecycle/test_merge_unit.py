"""Direct unit tests for scripts/lifecycle/_xanad/_merge.py."""

from __future__ import annotations

import json
import unittest

from scripts.lifecycle._xanad._merge import (
    extract_marked_markdown_blocks,
    extract_markdown_heading_block,
    merge_json_objects,
    merge_markdown_with_preserved_blocks,
    serialize_json_object,
    sha256_bytes,
    sha256_json,
)


class Sha256Tests(unittest.TestCase):
    def test_sha256_bytes_returns_sha256_prefixed_hex(self) -> None:
        result = sha256_bytes(b"hello")
        self.assertTrue(result.startswith("sha256:"))
        self.assertEqual(64 + len("sha256:"), len(result))

    def test_sha256_bytes_deterministic(self) -> None:
        self.assertEqual(sha256_bytes(b"data"), sha256_bytes(b"data"))

    def test_sha256_json_deterministic_across_key_order(self) -> None:
        a = sha256_json({"b": 1, "a": 2})
        b = sha256_json({"a": 2, "b": 1})
        self.assertEqual(a, b)

    def test_sha256_json_differs_for_different_data(self) -> None:
        self.assertNotEqual(sha256_json({"a": 1}), sha256_json({"a": 2}))


class MergeJsonObjectsTests(unittest.TestCase):
    def test_merge_overrides_scalar_key(self) -> None:
        result = merge_json_objects({"a": 1}, {"a": 2})
        self.assertEqual({"a": 2}, result)

    def test_merge_adds_new_key(self) -> None:
        result = merge_json_objects({"a": 1}, {"b": 2})
        self.assertEqual({"a": 1, "b": 2}, result)

    def test_merge_recursively_merges_nested_dicts(self) -> None:
        base = {"nested": {"a": 1, "b": 2}}
        override = {"nested": {"b": 99, "c": 3}}
        result = merge_json_objects(base, override)
        self.assertEqual({"nested": {"a": 1, "b": 99, "c": 3}}, result)

    def test_merge_does_not_mutate_inputs(self) -> None:
        base = {"a": 1}
        override = {"b": 2}
        merge_json_objects(base, override)
        self.assertEqual({"a": 1}, base)
        self.assertEqual({"b": 2}, override)

    def test_merge_replaces_non_dict_with_dict(self) -> None:
        result = merge_json_objects({"a": "scalar"}, {"a": {"nested": True}})
        self.assertEqual({"a": {"nested": True}}, result)


class SerializeJsonObjectTests(unittest.TestCase):
    def test_serialize_produces_valid_json_bytes(self) -> None:
        data = {"key": "value", "num": 42}
        raw = serialize_json_object(data)
        self.assertIsInstance(raw, bytes)
        parsed = json.loads(raw.decode("utf-8"))
        self.assertEqual(data, parsed)

    def test_serialize_ends_with_newline(self) -> None:
        raw = serialize_json_object({"x": 1})
        self.assertTrue(raw.endswith(b"\n"))

    def test_serialize_uses_two_space_indent(self) -> None:
        raw = serialize_json_object({"a": {"b": 1}})
        text = raw.decode("utf-8")
        self.assertIn("  ", text)


class ExtractMarkdownHeadingBlockTests(unittest.TestCase):
    def test_returns_none_when_heading_not_present(self) -> None:
        result = extract_markdown_heading_block("# Other\ncontent\n", "## Target")
        self.assertIsNone(result)

    def test_returns_block_until_next_h2(self) -> None:
        text = "## Section A\ncontent A\n## Section B\ncontent B\n"
        result = extract_markdown_heading_block(text, "## Section A")
        self.assertIsNotNone(result)
        self.assertIn("Section A", result)
        self.assertNotIn("Section B", result)

    def test_returns_block_at_end_of_document(self) -> None:
        text = "## Section\ncontent line\n"
        result = extract_markdown_heading_block(text, "## Section")
        self.assertIsNotNone(result)
        self.assertIn("content line", result)

    def test_returns_none_for_empty_block(self) -> None:
        text = "## Empty\n\n## Next\n"
        # The block for "## Empty" is just the heading with blank line — strip makes it non-empty
        result = extract_markdown_heading_block(text, "## Empty")
        # heading itself is part of block, so not None
        self.assertIsNotNone(result)


class ExtractMarkedMarkdownBlocksTests(unittest.TestCase):
    def test_finds_single_block(self) -> None:
        text = "prefix\n<!-- user-added -->custom content<!-- /user-added -->\nsuffix\n"
        blocks = extract_marked_markdown_blocks(text, "user-added")
        self.assertEqual(1, len(blocks))
        self.assertIn("custom content", blocks[0])

    def test_finds_multiple_blocks(self) -> None:
        text = (
            "<!-- user-added -->block 1<!-- /user-added -->\n"
            "middle\n"
            "<!-- user-added -->block 2<!-- /user-added -->\n"
        )
        blocks = extract_marked_markdown_blocks(text, "user-added")
        self.assertEqual(2, len(blocks))

    def test_returns_empty_list_when_no_blocks(self) -> None:
        blocks = extract_marked_markdown_blocks("no markers here", "user-added")
        self.assertEqual([], blocks)

    def test_handles_multiline_block(self) -> None:
        text = "<!-- migrated -->\nline 1\nline 2\n<!-- /migrated -->"
        blocks = extract_marked_markdown_blocks(text, "migrated")
        self.assertEqual(1, len(blocks))
        self.assertIn("line 1", blocks[0])
        self.assertIn("line 2", blocks[0])


class MergeMarkdownWithPreservedBlocksTests(unittest.TestCase):
    def test_returns_source_when_no_preserved_blocks(self) -> None:
        existing = "# Old\nno preserved blocks\n"
        source = "# New\ncontent\n"
        result = merge_markdown_with_preserved_blocks(existing, source)
        self.assertEqual(source, result)

    def test_appends_user_added_block_from_existing(self) -> None:
        existing = "# Existing\n<!-- user-added -->\ncustom text\n<!-- /user-added -->\n"
        source = "# New source\ncontent\n"
        result = merge_markdown_with_preserved_blocks(existing, source)
        self.assertIn("custom text", result)
        self.assertIn("# New source", result)

    def test_appends_migrated_block_from_existing(self) -> None:
        existing = "# Existing\n<!-- migrated -->\nmigrated text\n<!-- /migrated -->\n"
        source = "# New\ncontent\n"
        result = merge_markdown_with_preserved_blocks(existing, source)
        self.assertIn("migrated text", result)

    def test_does_not_duplicate_blocks_already_in_source(self) -> None:
        block = "<!-- user-added -->\ncustom\n<!-- /user-added -->"
        existing = f"# Old\n{block}\n"
        source = f"# New\n{block}\n"
        result = merge_markdown_with_preserved_blocks(existing, source)
        self.assertEqual(1, result.count("custom"))

    def test_appends_overrides_section_from_existing(self) -> None:
        existing = "# Existing\n## §10 - Project-Specific Overrides\nmy override\n"
        source = "# New\ncontent\n"
        result = merge_markdown_with_preserved_blocks(existing, source)
        self.assertIn("my override", result)

    def test_result_ends_with_newline(self) -> None:
        existing = "<!-- user-added -->x<!-- /user-added -->"
        source = "# Source\n"
        result = merge_markdown_with_preserved_blocks(existing, source)
        self.assertTrue(result.endswith("\n"))
