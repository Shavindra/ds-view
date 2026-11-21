"""Install the pinned reader and build the native Tauri sidecar on this host."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READER_PACKAGE = "shacl-py==0.4.1b1"


def git_options():
    # Dugite verifies its platform archive against the hash in its locked manifest.
    package = ROOT / "node_modules/dugite"
    portable = package / "git"
    executable = portable / ("ucrt64/bin/git.exe" if os.name == "nt" else "bin/git")
    if not executable.is_file():
        downloader = package / "script/download-git.js"
        if not downloader.is_file():
            raise SystemExit(
                "Run 'npm ci' in the ds-view checkout before building the reader."
            )
        subprocess.run(["node", str(downloader)], check=True)

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


def install_reader(build):
    env = build / "venv"
    subprocess.run([sys.executable, "-I", "-m", "venv", str(env)], check=True)
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pip = [str(python), "-I", "-m", "pip", "install"]
    subprocess.run([*pip, "-r", str(ROOT / "reader/requirements.txt")], check=True)
    # Streamlit belongs to the web viewer. The desktop reader uses the dependencies above.
    subprocess.run([*pip, "--no-deps", READER_PACKAGE], check=True)
    return python


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--installed",
        action="store_true",
        help="Build with this interpreter and its existing dependencies, skipping installation",
    )
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 14):
        parser.error("Build with Python 3.14.")
    try:
        target = subprocess.check_output(
            ["rustc", "--print", "host-tuple"], stderr=subprocess.PIPE, text=True
        ).strip()
    except FileNotFoundError:
        parser.error(
            "The Rust compiler (rustc) is missing from PATH. Install stable Rust from "
            "https://rustup.rs or load your existing toolchain, then check 'rustc --version'."
        )
    except subprocess.CalledProcessError as error:
        parser.error(
            f"Could not determine the Rust host target. {error.stderr.strip()}"
        )
    git_args = git_options()
    build = ROOT / ".reader-build"
    python = sys.executable if args.installed else install_reader(build)
    suffix = ".exe" if os.name == "nt" else ""
    cmd = [
        str(python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        "ds-reader",
        *git_args,
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
