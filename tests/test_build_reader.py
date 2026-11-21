"""Check the first-run build failure before it can touch the user's environment."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BuildReaderTests(unittest.TestCase):
    def test_missing_rust_stops_before_installing_dependencies(self):
        source = Path(__file__).resolve().parents[1] / "scripts/build_reader.py"
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            scripts = root / "scripts"
            scripts.mkdir()
            script = shutil.copy2(source, scripts)
            pip_log = root / "pip.log"
            result = subprocess.run(
                [sys.executable, str(script)],
                check=False,
                cwd=root,
                env={
                    **os.environ,
                    "PATH": str(root),
                    "PIP_LOG": str(pip_log),
                    "PIP_NO_INDEX": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("rustc", result.stderr)
            self.assertIn("https://rustup.rs", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(pip_log.exists())
            self.assertFalse((root / ".reader-build").exists())
