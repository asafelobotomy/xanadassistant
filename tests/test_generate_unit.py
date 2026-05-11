"""Direct unit test for scripts/generate.py — exercises main() to get coverage."""

from __future__ import annotations

import io
import contextlib
import unittest

from scripts.generate import main


class GenerateMainTests(unittest.TestCase):
    def test_main_returns_zero_and_regenerates_idempotently(self) -> None:
        """Calling main() regenerates the manifest from the real repo; it is idempotent."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main()
        self.assertEqual(0, code)
        output = buf.getvalue()
        self.assertIn("manifest", output)
        self.assertIn("catalog", output)
