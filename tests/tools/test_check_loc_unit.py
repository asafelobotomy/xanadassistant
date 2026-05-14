"""Direct unit tests for scripts/check_loc.py — covers functions missed by subprocess tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import scripts.check_loc as check_loc


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_lines(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join("x\n" for _ in range(count)), encoding="utf-8")


class CheckLocCountLinesTests(unittest.TestCase):
    def test_count_lines_returns_correct_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.py"
            path.write_text("line1\nline2\nline3\n", encoding="utf-8")
            self.assertEqual(3, check_loc.count_lines(path))

    def test_count_lines_single_line_no_newline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.py"
            path.write_text("only line", encoding="utf-8")
            self.assertEqual(1, check_loc.count_lines(path))

    def test_count_lines_empty_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.py"
            path.write_text("", encoding="utf-8")
            self.assertEqual(0, check_loc.count_lines(path))

    def test_count_lines_handles_missing_file(self) -> None:
        self.assertEqual(0, check_loc.count_lines(Path("/nonexistent/file.py")))


class CheckLocWarningLimitTests(unittest.TestCase):
    def test_warning_limit_for_default_path(self) -> None:
        limit = check_loc.warning_limit_for(Path("scripts/some_script.py"))
        self.assertEqual(check_loc.WARN_LIMIT, limit)

    def test_warning_limit_for_mcp_hook_override_from_repo_root(self) -> None:
        # When running from the repo root (as CI does), the override path resolves correctly.
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(str(REPO_ROOT))
            path = Path("hooks/scripts/xanadWorkspaceMcp.py")
            limit = check_loc.warning_limit_for(path)
            self.assertEqual(380, limit)
        finally:
            os.chdir(original_cwd)

    def test_warning_limit_for_sequential_thinking_override(self) -> None:
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(str(REPO_ROOT))
            path = Path("hooks/scripts/mcpSequentialThinkingServer.py")
            limit = check_loc.warning_limit_for(path)
            self.assertEqual(260, limit)
        finally:
            os.chdir(original_cwd)

    def test_warning_limit_for_git_mcp_override(self) -> None:
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(str(REPO_ROOT))
            path = Path("hooks/scripts/gitMcp.py")
            limit = check_loc.warning_limit_for(path)
            self.assertEqual(380, limit)
        finally:
            os.chdir(original_cwd)

    def test_warning_limit_for_sandbox_core_workspaces_override(self) -> None:
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(str(REPO_ROOT))
            path = Path("scripts/_sandbox_core_workspaces.py")
            limit = check_loc.warning_limit_for(path)
            self.assertEqual(380, limit)
        finally:
            os.chdir(original_cwd)

    def test_warning_limit_for_unknown_path_outside_cwd(self) -> None:
        # An absolute path that can't be relativized to cwd falls back to the key as-is.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "totally" / "unrelated.py"
            limit = check_loc.warning_limit_for(path)
            self.assertEqual(check_loc.WARN_LIMIT, limit)


class CheckLocCollectFilesTests(unittest.TestCase):
    def test_collect_files_with_explicit_py_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.py"
            path.write_text("content\n", encoding="utf-8")
            result = check_loc.collect_files([str(path)])
            self.assertEqual([path], result)

    def test_collect_files_with_explicit_md_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "README.md"
            path.write_text("# Hi\n", encoding="utf-8")
            result = check_loc.collect_files([str(path)])
            self.assertEqual([path], result)

    def test_collect_files_skips_nonexistent_path(self) -> None:
        result = check_loc.collect_files(["/nonexistent/file.py"])
        self.assertEqual([], result)

    def test_collect_files_skips_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = check_loc.collect_files([tmp])
            self.assertEqual([], result)

    def test_collect_files_no_args_uses_git_ls_files(self) -> None:
        """Calling collect_files([]) triggers the git ls-files path."""
        import os
        orig_cwd = os.getcwd()
        try:
            import subprocess
            repo_root = Path(__file__).resolve().parents[2]
            os.chdir(repo_root)
            result = check_loc.collect_files([])
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            for p in result:
                self.assertIsInstance(p, Path)
        finally:
            os.chdir(orig_cwd)


class CheckLocMainTests(unittest.TestCase):
    def test_main_returns_zero_for_clean_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clean.py"
            path.write_text("short\n", encoding="utf-8")
            self.assertEqual(0, check_loc.main([str(path)]))

    def test_main_returns_zero_for_warning_threshold_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "warn.py"
            _write_lines(path, 260)
            self.assertEqual(0, check_loc.main([str(path)]))

    def test_main_returns_one_for_hard_limit_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "big.py"
            _write_lines(path, 401)
            self.assertEqual(1, check_loc.main([str(path)]))

    def test_main_hard_only_skips_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "warn.py"
            _write_lines(path, 260)
            self.assertEqual(0, check_loc.main(["--hard-only", str(path)]))

    def test_main_hard_only_still_fails_at_hard_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "big.py"
            _write_lines(path, 401)
            self.assertEqual(1, check_loc.main(["--hard-only", str(path)]))

    def test_main_multiple_files_one_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.py"
            clean.write_text("short\n", encoding="utf-8")
            big = Path(tmp) / "big.py"
            _write_lines(big, 401)
            self.assertEqual(1, check_loc.main([str(clean), str(big)]))
