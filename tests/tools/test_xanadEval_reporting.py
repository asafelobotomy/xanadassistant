"""Tests for xanadEval reporting commands: compare (git-ref diff) and report (HTML)."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xanadEval_test_support import xe, _MINIMAL_SKILL


class CompareCommandTests(unittest.TestCase):
    """Tests for cmd_compare — git-ref token diffing."""

    def _setup_git_repo(self, tmp: Path, content_v1: str, content_v2: str) -> tuple[Path, str]:
        """Create a minimal git repo with two commits; return (skill_path, baseline_ref)."""
        import subprocess as sp
        sp.run(["git", "init", str(tmp)], check=True, capture_output=True)
        sp.run(["git", "-C", str(tmp), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        sp.run(["git", "-C", str(tmp), "config", "user.name", "T"], check=True, capture_output=True)

        skill_dir = tmp / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(content_v1, encoding="utf-8")
        sp.run(["git", "-C", str(tmp), "add", "."], check=True, capture_output=True)
        sp.run(["git", "-C", str(tmp), "commit", "-m", "v1"], check=True, capture_output=True)

        # Get the commit hash of v1 (our baseline)
        result = sp.run(["git", "-C", str(tmp), "rev-parse", "HEAD"],
                        capture_output=True, text=True, check=True)
        baseline_ref = result.stdout.strip()

        # Write v2
        skill_file.write_text(content_v2, encoding="utf-8")
        return skill_file, baseline_ref

    def _compare(self, skill_file: Path, ref: str, **kwargs) -> tuple[str, int]:
        old_cwd = os.getcwd()
        try:
            os.chdir(skill_file.parent.parent.parent)  # repo root
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_compare(
                    ref=ref,
                    paths=[str(skill_file)],
                    skills=False,
                    threshold=kwargs.get("threshold"),
                    strict=kwargs.get("strict", False),
                    fmt=kwargs.get("fmt", "json"),
                )
        finally:
            os.chdir(old_cwd)
        return buf.getvalue(), code

    def test_compare_detects_growth(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1 = "---\nname: my-skill\n---\n\nShort.\n"
            v2 = v1 + "word " * 500
            skill_file, ref = self._setup_git_repo(Path(d), v1, v2)
            output, _ = self._compare(skill_file, ref, fmt="json")
        data = json.loads(output)
        entry = data["files"][0]
        self.assertGreater(entry["new_tokens"], entry["old_tokens"])
        self.assertGreater(entry["delta_pct"], 0)

    def test_compare_exits_1_when_threshold_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1 = "---\nname: my-skill\n---\n\nShort.\n"
            v2 = v1 + "word " * 500
            skill_file, ref = self._setup_git_repo(Path(d), v1, v2)
            _, code = self._compare(skill_file, ref, threshold=5, fmt="json")
        self.assertEqual(code, 1)

    def test_compare_exits_0_when_under_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            v1 = "---\nname: my-skill\n---\n\n" + "word " * 1000
            v2 = v1 + "word "  # trivially larger
            skill_file, ref = self._setup_git_repo(Path(d), v1, v2)
            _, code = self._compare(skill_file, ref, threshold=50, fmt="json")
        self.assertEqual(code, 0)

    def test_compare_new_file_has_null_old_tokens(self) -> None:
        """A file that doesn't exist in the ref gets status=new and null old_tokens."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            import subprocess as sp
            sp.run(["git", "init", str(tmp)], check=True, capture_output=True)
            sp.run(["git", "-C", str(tmp), "config", "user.email", "t@t.com"], check=True, capture_output=True)
            sp.run(["git", "-C", str(tmp), "config", "user.name", "T"], check=True, capture_output=True)
            # Commit a placeholder so HEAD exists
            (tmp / "README.md").write_text("hi\n")
            sp.run(["git", "-C", str(tmp), "add", "."], check=True, capture_output=True)
            sp.run(["git", "-C", str(tmp), "commit", "-m", "init"], check=True, capture_output=True)
            ref = sp.run(["git", "-C", str(tmp), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()

            skill_dir = tmp / "skills" / "my-skill"
            skill_dir.mkdir(parents=True)
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text("---\nname: my-skill\n---\n\nNew file.\n", encoding="utf-8")

            buf = io.StringIO()
            old = os.getcwd(); os.chdir(tmp)
            try:
                with redirect_stdout(buf):
                    xe.cmd_compare(ref, [str(skill_file)], False, None, False, "json")
            finally:
                os.chdir(old)
        data = json.loads(buf.getvalue())
        entry = data["files"][0]
        self.assertEqual(entry["status"], "new")
        self.assertIsNone(entry["old_tokens"])

    def test_compare_no_git_repo_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            old = os.getcwd(); os.chdir(d)
            try:
                err_buf = io.StringIO()
                with redirect_stderr(err_buf):
                    code = xe.cmd_compare("main", [], False, None, False, "text")
            finally:
                os.chdir(old)
        self.assertEqual(code, 2)

    def test_compare_no_paths_and_no_skills_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            err_buf = io.StringIO()
            with redirect_stderr(err_buf):
                code = xe.cmd_compare("main", [], False, None, False, "text")
        self.assertEqual(code, 2)


class ReportCommandTests(unittest.TestCase):
    """Tests for cmd_report — self-contained HTML generation."""

    def _report(self, paths: list[str], output: str | None = None) -> tuple[str, int]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = xe.cmd_report(paths, output)
        return buf.getvalue(), code

    def _make_skill_file(self, d: Path, name: str = "test-skill") -> Path:
        skill_dir = d / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        p = skill_dir / "SKILL.md"
        p.write_text(_MINIMAL_SKILL.replace("test-skill", name), encoding="utf-8")
        return p

    def test_report_writes_html_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._make_skill_file(Path(d))
            out = str(Path(d) / "report.html")
            _, code = self._report([str(p)], output=out)
            self.assertEqual(code, 0)
            self.assertTrue(Path(out).exists())

    def test_report_html_is_valid_structure(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._make_skill_file(Path(d))
            out = str(Path(d) / "report.html")
            self._report([str(p)], output=out)
            html = Path(out).read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("xanadEval Report", html)
        self.assertIn("spec-frontmatter", html)

    def test_report_embeds_json_data(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._make_skill_file(Path(d))
            out = str(Path(d) / "report.html")
            self._report([str(p)], output=out)
            html = Path(out).read_text(encoding="utf-8")
        self.assertIn('"spec-frontmatter"', html)
        self.assertIn('"pass"', html)

    def test_report_covers_multiple_skills(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p1 = self._make_skill_file(root, "alpha")
            p2 = self._make_skill_file(root, "beta")
            out = str(root / "report.html")
            _, code = self._report([str(p1), str(p2)], output=out)
            html = Path(out).read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertIn("alpha", html)
        self.assertIn("beta", html)

    def test_report_default_output_filename(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._make_skill_file(Path(d))
            old = os.getcwd(); os.chdir(d)
            try:
                _, code = self._report([str(p)], output=None)
                self.assertEqual(code, 0)
                self.assertTrue((Path(d) / "xanadEval-report.html").exists())
            finally:
                os.chdir(old)

    def test_report_empty_paths_returns_1(self) -> None:
        err_buf = io.StringIO()
        with redirect_stderr(err_buf):
            code = xe.cmd_report([], None)
        self.assertEqual(code, 1)

    def test_report_via_main(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = self._make_skill_file(Path(d))
            out = str(Path(d) / "report.html")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.main(["report", str(p), "--output", out])
            self.assertEqual(code, 0)
            self.assertTrue(Path(out).exists())

    def test_report_script_injection_escaped(self) -> None:
        """Data embedded in the <script> block must not contain raw </script>."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            skill_dir = root / "skills" / "test-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            evil = _MINIMAL_SKILL.replace(
                "name: test-skill",
                'name: "test</script><script>alert(1)</script>"',
            )
            p = skill_dir / "SKILL.md"
            p.write_text(evil, encoding="utf-8")
            out = str(root / "report.html")
            with redirect_stdout(io.StringIO()):
                xe.cmd_report([str(p)], output=out)
            html = Path(out).read_text(encoding="utf-8")
        self.assertNotIn("</script><script>alert", html)

    def test_report_write_failure_returns_2(self) -> None:
        """An OSError writing the HTML output file returns exit 2."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            skill_dir = root / "skills" / "test-skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            p = skill_dir / "SKILL.md"
            p.write_text(_MINIMAL_SKILL, encoding="utf-8")
            out = str(root / "report.html")
            with mock.patch.object(Path, "write_text",
                                   side_effect=OSError("Permission denied")):
                err_buf = io.StringIO()
                with redirect_stderr(err_buf):
                    code = xe.cmd_report([str(p)], out)
        self.assertEqual(code, 2)
        self.assertIn("cannot write", err_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
