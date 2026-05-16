from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle._xanad._inspect_helpers import collect_unmanaged_files


class CollectUnmanagedFilesTests(unittest.TestCase):
    def _minimal_manifest(self) -> dict:
        return {"retiredFiles": [], "files": []}

    def test_pycache_files_are_not_reported_as_unmanaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            hooks_dir = workspace / ".github" / "hooks" / "scripts"
            hooks_dir.mkdir(parents=True)

            managed = hooks_dir / "gitMcp.py"
            managed.write_text("# managed\n")
            managed_target = ".github/hooks/scripts/gitMcp.py"

            pycache_dir = hooks_dir / "__pycache__"
            pycache_dir.mkdir()
            (pycache_dir / "gitMcp.cpython-314.pyc").write_bytes(b"\x00")

            result = collect_unmanaged_files(
                workspace,
                self._minimal_manifest(),
                {managed_target},
            )

        self.assertNotIn(".github/hooks/scripts/__pycache__/gitMcp.cpython-314.pyc", result)
        self.assertEqual(result, [])

    def test_genuine_unmanaged_files_are_still_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            hooks_dir = workspace / ".github" / "hooks" / "scripts"
            hooks_dir.mkdir(parents=True)

            managed = hooks_dir / "gitMcp.py"
            managed.write_text("# managed\n")
            managed_target = ".github/hooks/scripts/gitMcp.py"

            lookalike = hooks_dir / "myCustomScript.py"
            lookalike.write_text("# not managed\n")

            result = collect_unmanaged_files(
                workspace,
                self._minimal_manifest(),
                {managed_target},
            )

        self.assertIn(".github/hooks/scripts/myCustomScript.py", result)
