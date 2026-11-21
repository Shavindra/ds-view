"""Check source selection and first-run failures for the desktop reader."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_reader


class BuildReaderTests(unittest.TestCase):
    def test_build_reads_main_again_after_an_unreleased_change(self):
        with tempfile.TemporaryDirectory() as work, patch.dict(os.environ):
            root = Path(work)
            os.environ.pop("DS_VIEW_CI_SHACL_PY_COMMIT", None)
            git = [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=DS View",
                "-c",
                "user.email=test@example.org",
            ]
            subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
            (root / "pyproject.toml").write_text(
                '[project]\nversion = "0.4.1b1"\n', encoding="utf-8"
            )
            with patch.object(build_reader, "READER_REPO", root.as_uri()):
                commits = []
                for code in ("first", "second"):
                    (root / "reader.txt").write_text(code, encoding="utf-8")
                    subprocess.run([*git, "add", "."], check=True)
                    subprocess.run([*git, "commit", "-qm", code], check=True)
                    commits.append(build_reader.main_commit())
                    self.assertEqual(
                        commits[-1],
                        subprocess.check_output(
                            [*git, "rev-parse", "HEAD"], text=True
                        ).strip(),
                    )
                self.assertNotEqual(*commits)
                subprocess.run([*git, "branch", "-m", "other"], check=True)
                with self.assertRaisesRegex(
                    SystemExit, "Could not fetch shacl-py/main"
                ):
                    build_reader.main_commit()

    def test_installed_mode_rejects_an_older_reader_without_running_pip(self):
        with (
            patch.object(subprocess, "check_output", return_value="1" * 40),
            patch.object(subprocess, "run") as run,
        ):
            with self.assertRaisesRegex(SystemExit, "Rerun without --installed"):
                build_reader.reader_python(Path("."), "2" * 40, installed_only=True)
            run.assert_not_called()

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
