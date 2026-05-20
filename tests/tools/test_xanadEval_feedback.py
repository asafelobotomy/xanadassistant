"""Tests for xanadEval feedback commands: quality, dev."""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xanadEval_test_support import (
    xe, DynamicTestBase, _MOCK_QUALITY_REPLY, _MOCK_DEV_REPLY,
)


class QualityCommandTests(DynamicTestBase, unittest.TestCase):
    """Tests for cmd_quality — LLM-as-judge skill scoring."""

    def test_quality_requires_token(self) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {}, clear=False):
            for key in ("GITHUB_TOKEN", "GH_TOKEN"):
                os.environ.pop(key, None)
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_quality(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 2)
        self.assertIn("GITHUB_TOKEN", err.getvalue())

    @mock.patch("xanadEval._call_model", return_value=_MOCK_QUALITY_REPLY)
    def test_quality_text_output(self, _mock) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_quality(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("clarity", out)
        self.assertIn("overall", out)

    @mock.patch("xanadEval._call_model", return_value=_MOCK_QUALITY_REPLY)
    def test_quality_json_output(self, _mock) -> None:
        import json
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_quality(path, "gpt-4o-mini", "json")
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("scores", data)
        self.assertIn("clarity", data["scores"])

    @mock.patch("xanadEval._call_model", return_value="I cannot provide scores.")
    def test_quality_bad_model_response_returns_1(self, _mock) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_quality(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 1)

    @mock.patch(
        "xanadEval._call_model",
        return_value='{"clarity": null, "completeness": 0.9, "trigger_precision": 0.7, '
                     '"scope_coverage": 0.8, "anti_patterns": 0.9, "overall": 0.82, '
                     '"summary": "ok"}',
    )
    def test_quality_non_numeric_score_returns_1(self, _mock) -> None:
        """cmd_quality must return 1 with an error when a score field is non-numeric."""
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_quality(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 1)
        self.assertIn("non-numeric", err.getvalue())


class DevCommandTests(DynamicTestBase, unittest.TestCase):
    """Tests for cmd_dev — skill improvement suggestions."""

    def test_dev_requires_token(self) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {}, clear=False):
            for key in ("GITHUB_TOKEN", "GH_TOKEN"):
                os.environ.pop(key, None)
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_dev(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 2)

    @mock.patch("xanadEval._call_model", return_value=_MOCK_DEV_REPLY)
    def test_dev_surfaces_improvements(self, _mock) -> None:
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = xe.cmd_dev(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("improvements", out)
        self.assertIn("Add examples", out)

    @mock.patch(
        "xanadEval._call_model",
        return_value='{"clarity": "n/a", "completeness": 0.7, "trigger_precision": 0.5, '
                     '"scope_coverage": 0.6, "anti_patterns": 0.8, "overall": 0.64, '
                     '"improvements": ["x"], "summary": "needs work"}',
    )
    def test_dev_non_numeric_score_returns_1(self, _mock) -> None:
        """cmd_dev must return 1 with an error when a score field is non-numeric."""
        path = self._skill_tmpfile()
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
            err = io.StringIO()
            with redirect_stderr(err):
                code = xe.cmd_dev(path, "gpt-4o-mini", "text")
        self.assertEqual(code, 1)
        self.assertIn("non-numeric", err.getvalue())


if __name__ == "__main__":
    unittest.main()
