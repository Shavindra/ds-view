"""Install the pinned reader and build the native Tauri sidecar on this host."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "git+https://github.com/Shavindra/shacl-py.git@4a90d5b926df53c4cc08303493676e171e292567"


def git_options():
    # Dugite verifies its platform archive against the hash in its locked manifest.
    package = ROOT / "node_modules/dugite"
    portable = package / "git"
    executable = portable / ("ucrt64/bin/git.exe" if os.name == "nt" else "bin/git")
    if not executable.is_file():
        subprocess.run(["node", str(package / "script/download-git.js")], check=True)

    options = ["--runtime-hook", str(ROOT / "reader/git_runtime.py")]
    if os.name == "nt":
        # The local Git commands used by MetaLad are built into git.exe. Keep its
        # four non-system DLLs alongside it without changing their signed bytes.
        for name in (
            "git.exe",
            "libiconv-2.dll",
            "libintl-8.dll",
            "libpcre2-8-0.dll",
            "zlib1.dll",
        ):
            options.extend(["--add-data", f"{executable.parent / name}:ds-git"])
        options.extend(
            [
                "--add-data",
                f"{portable / 'LICENSE.txt'}:ds-git",
                "--add-data",
                f"{portable / 'ucrt64/share/licenses'}:ds-git/licenses",
            ]
        )
    else:
        options.extend(["--add-binary", f"{executable}:ds-git"])
    return options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--installed",
        action="store_true",
        help="Use the dependencies already installed in this environment",
    )
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        parser.error("Build with Python 3.14.")
    if not args.installed:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(ROOT / "reader/requirements.txt"),
            ],
            check=True,
        )
        # Install only the reader's dependencies. Streamlit belongs to the web viewer.
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", UPSTREAM], check=True
        )
    target = subprocess.check_output(
        ["rustc", "--print", "host-tuple"], text=True
    ).strip()
    build = ROOT / ".reader-build"
    suffix = ".exe" if os.name == "nt" else ""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        "ds-reader",
        *git_options(),
        "--distpath",
        str(build / "dist"),
        "--workpath",
        str(build / "work"),
        "--specpath",
        str(build),
        "--additional-hooks-dir",
        str(ROOT / "reader/hooks"),
        "--collect-data",
        "shacl_py",
        "--copy-metadata",
        "shacl-py",
        "--recursive-copy-metadata",
        "datalad-metalad",
        "--collect-data",
        "datalad",
        "--collect-data",
        "datalad_metalad",
        "--collect-data",
        "dataladmetadatamodel",
        "--copy-metadata",
        "datalad-deprecated",
        "--exclude-module",
        "streamlit",
        "--exclude-module",
        "pytest",
        str(ROOT / "reader/main.py"),
    ]
    subprocess.run(cmd, check=True)
    dest = ROOT / "src-tauri/binaries" / f"ds-reader-{target}{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(build / "dist" / f"ds-reader{suffix}", dest)
    print(dest)


if __name__ == "__main__":
    main()
