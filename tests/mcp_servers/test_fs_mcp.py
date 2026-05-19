from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tests.mcp_servers._mcp_module_loader import load_mcp_script_module

SOURCE_MODULE = load_mcp_script_module("mcp/scripts/fsMcp.py", "test_fsMcp_source", "fsMcp.py")
# Managed copy does not exist yet until the mirror is synced; skip gracefully.
try:
    MANAGED_MODULE = load_mcp_script_module(
        ".github/mcp/scripts/fsMcp.py", "test_fsMcp_managed", "fsMcp.py"
    )
    _MODULES = (SOURCE_MODULE, MANAGED_MODULE)
except FileNotFoundError:
    _MODULES = (SOURCE_MODULE,)


def _set_root(module, root: Path) -> None:
    module.ALLOWED_ROOT = root


class DiscoverRootTests(unittest.TestCase):
    def test_discovers_parent_with_github_dir(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            workspace = Path(d)
            (workspace / ".github").mkdir()
            script = workspace / "mcp" / "scripts" / "fsMcp.py"
            script.parent.mkdir(parents=True)
            script.write_text("# stub\n", encoding="utf-8")
            self.assertEqual(SOURCE_MODULE._discover_root(script), workspace)

    def test_get_allowed_root_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            old = os.environ.get("FS_ALLOWED_ROOT")
            try:
                os.environ["FS_ALLOWED_ROOT"] = d
                result = SOURCE_MODULE._get_allowed_root()
                self.assertEqual(result, Path(d).resolve())
            finally:
                if old is None:
                    os.environ.pop("FS_ALLOWED_ROOT", None)
                else:
                    os.environ["FS_ALLOWED_ROOT"] = old


class PathSafetyTests(unittest.TestCase):
    def test_resolve_accepts_path_inside_root(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    p = module._resolve(str(Path(d) / "subdir" / "file.txt"))
                    self.assertEqual(p, Path(d).resolve() / "subdir" / "file.txt")

    def test_resolve_rejects_path_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d) / "workspace")
                    with self.assertRaisesRegex(ValueError, "outside the allowed root"):
                        module._resolve("/tmp/__outside__")

    def test_resolve_rejects_empty_path(self) -> None:
        for module in _MODULES:
            with self.subTest(module=module.__name__):
                with self.assertRaises(ValueError):
                    module._resolve("")

    def test_resolve_rejects_null_byte(self) -> None:
        for module in _MODULES:
            with self.subTest(module=module.__name__):
                with self.assertRaises(ValueError):
                    module._resolve("file\x00.txt")


class ReadFileTests(unittest.TestCase):
    def test_reads_full_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "hello.txt"
            f.write_text("line1\nline2\nline3\n", encoding="utf-8")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.read_file(str(f))
                    self.assertIn("line1", result)
                    self.assertIn("line3", result)

    def test_reads_line_range(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "multi.txt"
            f.write_text("a\nb\nc\nd\n", encoding="utf-8")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.read_file(str(f), start_line=2, end_line=3)
                    self.assertIn("b", result)
                    self.assertIn("c", result)
                    self.assertNotIn("a", result)
                    self.assertNotIn("d", result)

    def test_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    with self.assertRaises(FileNotFoundError):
                        module.read_file(str(Path(d) / "no_such_file.txt"))

    def test_rejects_binary_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "data.bin"
            f.write_bytes(b"\x00\x01\x02\x03")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    with self.assertRaisesRegex(ValueError, "binary"):
                        module.read_file(str(f))

    def test_rejects_directory_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "subdir"
            sub.mkdir()
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    with self.assertRaises(ValueError):
                        module.read_file(str(sub))

    def test_is_binary_detection(self) -> None:
        for module in _MODULES:
            with self.subTest(module=module.__name__):
                self.assertTrue(module._is_binary(b"hello\x00world"))
                self.assertFalse(module._is_binary(b"plain text"))


class WriteFileTests(unittest.TestCase):
    def test_creates_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "new.txt"
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.write_file(str(dest), "hello world")
                    self.assertIn("hello world", dest.read_text())
                    self.assertIn("characters", result)

    def test_overwrites_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "existing.txt"
            dest.write_text("old content", encoding="utf-8")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    module.write_file(str(dest), "new content")
                    self.assertEqual(dest.read_text(), "new content")

    def test_create_dirs_makes_parents(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "a" / "b" / "file.txt"
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    module.write_file(str(dest), "content", create_dirs=True)
                    self.assertTrue(dest.exists())

    def test_rejects_missing_parent_without_create_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "missing_parent" / "file.txt"
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    with self.assertRaises(FileNotFoundError):
                        module.write_file(str(dest), "content")


class ListDirectoryTests(unittest.TestCase):
    def test_lists_flat_directory(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.txt").write_text("x")
            (Path(d) / "b.txt").write_text("x")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.list_directory(d)
                    self.assertIn("a.txt", result)
                    self.assertIn("b.txt", result)

    def test_glob_filter(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "script.py").write_text("x")
            (Path(d) / "note.md").write_text("x")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.list_directory(d, pattern="*.py")
                    self.assertIn("script.py", result)
                    self.assertNotIn("note.md", result)

    def test_recursive_finds_nested_files(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "sub"
            sub.mkdir()
            (sub / "deep.txt").write_text("x")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.list_directory(d, recursive=True)
                    self.assertIn("deep.txt", result)

    def test_empty_directory_returns_message(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            empty = Path(d) / "empty"
            empty.mkdir()
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.list_directory(str(empty))
                    self.assertIn("no entries", result)


class SearchFilesTests(unittest.TestCase):
    def test_finds_literal_match(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "code.py").write_text("def hello_world():\n    pass\n")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.search_files(d, "hello_world", include_pattern="*.py")
                    self.assertIn("hello_world", result)
                    self.assertIn("code.py", result)

    def test_regex_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "code.py").write_text("error_code = 404\n")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.search_files(d, r"\d{3}", use_regex=True, include_pattern="*.py")
                    self.assertIn("404", result)

    def test_no_match_returns_message(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "file.txt").write_text("nothing here\n")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.search_files(d, "xyzzy_not_here", include_pattern="*.txt")
                    self.assertIn("no matches", result)

    def test_empty_pattern_raises(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    with self.assertRaises(ValueError):
                        module.search_files(d, "")


class FileInfoTests(unittest.TestCase):
    def test_returns_metadata_for_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "data.txt"
            f.write_text("some content", encoding="utf-8")
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.file_info(str(f))
                    self.assertIn("file", result)
                    self.assertIn("bytes", result)
                    self.assertIn("modified", result)

    def test_returns_metadata_for_directory(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "mydir"
            sub.mkdir()
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.file_info(str(sub))
                    self.assertIn("directory", result)

    def test_raises_for_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    with self.assertRaises(FileNotFoundError):
                        module.file_info(str(Path(d) / "ghost.txt"))


class CreateDirectoryTests(unittest.TestCase):
    def test_creates_nested_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "a" / "b" / "c"
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.create_directory(str(target))
                    self.assertTrue(target.is_dir())
                    self.assertIn("ready", result)

    def test_idempotent_on_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    module.create_directory(d)  # already exists — must not raise


class MoveFileTests(unittest.TestCase):
    def test_renames_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "old.txt"
            src.write_text("data")
            dst = Path(d) / "new.txt"
            for module in _MODULES:
                src.write_text("data")
                dst.unlink(missing_ok=True)
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.move_file(str(src), str(dst))
                    self.assertTrue(dst.exists())
                    self.assertFalse(src.exists())
                    self.assertIn("→", result)

    def test_rejects_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    with self.assertRaises(FileNotFoundError):
                        module.move_file(str(Path(d) / "ghost.txt"), str(Path(d) / "out.txt"))


class DeleteFileTests(unittest.TestCase):
    def test_deletes_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "target.txt"
            for module in _MODULES:
                f.write_text("bye")
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    result = module.delete_file(str(f))
                    self.assertFalse(f.exists())
                    self.assertIn("Deleted", result)

    def test_rejects_directory(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "subdir"
            sub.mkdir()
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    with self.assertRaisesRegex(ValueError, "directory"):
                        module.delete_file(str(sub))

    def test_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            for module in _MODULES:
                with self.subTest(module=module.__name__):
                    _set_root(module, Path(d))
                    with self.assertRaises(FileNotFoundError):
                        module.delete_file(str(Path(d) / "nope.txt"))


if __name__ == "__main__":
    unittest.main()
