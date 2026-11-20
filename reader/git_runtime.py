"""Put the reader's private Git first before DataLad initialises its config."""

import os
import sys
from pathlib import Path

git_dir = Path(sys._MEIPASS) / "ds-git"
inherited = os.environ.get("PATH", "")
os.environ["PATH"] = str(git_dir) + (os.pathsep + inherited if inherited else "")
