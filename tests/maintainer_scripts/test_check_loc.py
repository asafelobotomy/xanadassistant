from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from scripts import check_loc


class CheckLocTests(unittest.TestCase):
    def test_collect_files_uses_explicit_roots_and_filters_to_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file_path = root / "example.py"
            dir_path = root / "folder"
            file_path.write_text("print('x')\n", encoding="utf-8")
            dir_path.mkdir()

            result = check_loc.collect_files([str(file_path), str(dir_path)])

        self.assertEqual(result, [file_path])

    def test_collect_files_uses_git_ls_files_and_falls_back_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fallback_py = root / "fallback.py"
            fallback_md = root / "readme.md"
            ignored_txt = root / "notes.txt"
            fallback_py.write_text("print('x')\n", encoding="utf-8")
            fallback_md.write_text("hello\n", encoding="utf-8")
            ignored_txt.write_text("ignore\n", encoding="utf-8")

            with mock.patch("scripts.check_loc.subprocess.run", return_value=mock.Mock(stdout="a.py\nb.md\nnotes.txt\n", returncode=0)):
                git_result = check_loc.collect_files([])

            with mock.patch("scripts.check_loc.subprocess.run", side_effect=check_loc.subprocess.CalledProcessError(1, ["git"])), mock.patch(
                "scripts.check_loc.Path.rglob",
                return_value=[fallback_py, fallback_md, ignored_txt],
            ):
                fallback_result = check_loc.collect_files([])

        self.assertEqual(git_result, [Path("a.py"), Path("b.md")])
        self.assertEqual(fallback_result, [fallback_py, fallback_md])

    def test_count_lines_and_limit_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "mcp" / "scripts" / "memoryMcp.py"
            target.parent.mkdir(parents=True)
            target.write_text("one\ntwo\n", encoding="utf-8")

            with mock.patch("scripts.check_loc.REPO_ROOT", root):
                self.assertEqual(check_loc.count_lines(target), 2)
                self.assertEqual(check_loc.warning_limit_for(target), 600)
                self.assertEqual(check_loc.hard_limit_for(target), 450)

    def test_main_reports_warnings_and_violations(self) -> None:
        stderr = io.StringIO()
        files = [Path("warn.py"), Path("error.py")]

        with mock.patch("scripts.check_loc.collect_files", return_value=files), mock.patch(
            "scripts.check_loc.count_lines",
            side_effect=[check_loc.WARN_LIMIT + 1, check_loc.HARD_LIMIT + 1],
        ), mock.patch("scripts.check_loc.warning_limit_for", return_value=check_loc.WARN_LIMIT), mock.patch(
            "scripts.check_loc.hard_limit_for",
            return_value=check_loc.HARD_LIMIT,
        ), redirect_stderr(stderr):
            exit_code = check_loc.main([])

        output = stderr.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("WARN", output)
        self.assertIn("ERROR", output)
        self.assertIn("LOC gate FAILED", output)

    def test_main_hard_only_suppresses_warnings(self) -> None:
        stderr = io.StringIO()

        with mock.patch("scripts.check_loc.collect_files", return_value=[Path("warn.py")]), mock.patch(
            "scripts.check_loc.count_lines",
            return_value=check_loc.WARN_LIMIT + 1,
        ), redirect_stderr(stderr):
            exit_code = check_loc.main(["--hard-only"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")

    def test_collect_files_excludes_github_paths(self) -> None:
        """Managed mirrors under .github/ must not be counted by the LOC gate."""
        with mock.patch(
            "scripts.check_loc.subprocess.run",
            return_value=mock.Mock(stdout=".github/agents/foo.agent.md\nagents/foo.agent.md\n", returncode=0),
        ):
            result = check_loc.collect_files([])
        paths_str = [str(p) for p in result]
        self.assertNotIn(".github/agents/foo.agent.md", paths_str)
        self.assertIn("agents/foo.agent.md", paths_str)

    def test_collect_files_catches_oserror_from_git_binary_missing(self) -> None:
        """OSError from subprocess (git binary missing) must trigger the rglob fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fallback_py = root / "example.py"
            github_py = root / ".github" / "agents" / "foo.agent.md"
            fallback_py.write_text("pass\n", encoding="utf-8")
            github_py.parent.mkdir(parents=True)
            github_py.write_text("# agent\n", encoding="utf-8")

            with mock.patch("scripts.check_loc.subprocess.run", side_effect=OSError("no such file")), mock.patch(
                "scripts.check_loc.Path.rglob",
                return_value=[fallback_py, github_py],
            ):
                result = check_loc.collect_files([])

        self.assertIn(fallback_py, result)
        self.assertNotIn(github_py, result)

    def test_unreadable_file_reported_as_error_and_fails(self) -> None:
        """An unreadable file must be reported and cause a non-zero exit."""
        stderr = io.StringIO()
        with mock.patch("scripts.check_loc.collect_files", return_value=[Path("locked.py")]), \
             mock.patch("scripts.check_loc.count_lines", side_effect=OSError("permission denied")), \
             redirect_stderr(stderr):
            exit_code = check_loc.main([])
        self.assertEqual(exit_code, 1)
        self.assertIn("unreadable", stderr.getvalue())
        self.assertIn("LOC gate FAILED", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()