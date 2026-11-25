"""Build the native Tauri sidecar from the current shacl-py main commit."""

import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READER_REPO = "https://github.com/Shavindra/shacl-py.git"


def main_commit():
    # A single checkout selects the same upstream revision for both CI runners.
    commit = os.environ.get("DS_VIEW_CI_SHACL_PY_COMMIT")
    if commit is None:
        try:
            ref = subprocess.check_output(
                ["git", "ls-remote", "--exit-code", READER_REPO, "refs/heads/main"],
                text=True,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            raise SystemExit("Install Git to fetch shacl-py/main.") from None
        except subprocess.CalledProcessError as error:
            raise SystemExit(
                f"Could not fetch shacl-py/main. {error.stderr.strip()}"
            ) from None
        commit, _, name = ref.strip().partition("\t")
        if name != "refs/heads/main":
            raise SystemExit("Git did not return refs/heads/main for shacl-py.")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise SystemExit("Expected a full Git commit for shacl-py/main.")
    return commit


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


def desktop_assets(build):
    rules = []
    for package, family, weights in (
        ("ibm-plex-sans", "IBM Plex Sans", (400, 500, 600)),
        ("ibm-plex-mono", "IBM Plex Mono", (400,)),
        ("source-serif-4", "Source Serif 4", (500, 600)),
    ):
        fonts = ROOT / "node_modules/@fontsource" / package / "files"
        for weight in weights:
            data = (fonts / f"{package}-latin-{weight}-normal.woff2").read_bytes()
            encoded = base64.b64encode(data).decode("ascii")
            rules.append(
                f"@font-face {{font-family:'{family}';font-weight:{weight};"
                f"font-style:normal;src:url(data:font/woff2;base64,{encoded}) format('woff2');}}"
            )
    css = build / "desktop-fonts.css"
    css.write_text("\n".join(rules), encoding="ascii")
    return [
        arg
        for path in (
            css,
            ROOT / "reader/desktop_app.py",
            ROOT / "reader/desktop_controls.js",
        )
        for arg in ("--add-data", f"{path}:.")
    ]


def reader_python(build, commit, *, installed_only):
    env = build / "venv"
    python = (
        Path(sys.executable)
        if installed_only
        else env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    pip = [str(python), "-I", "-m", "pip", "install"]
    if not installed_only:
        subprocess.run([sys.executable, "-I", "-m", "venv", str(env)], check=True)
        subprocess.run([*pip, "-r", str(ROOT / "reader/requirements.txt")], check=True)
    installed = subprocess.check_output(
        [str(python), "-I", str(ROOT / "reader/shacl_revision.py")], text=True
    ).strip()
    if installed != commit:
        if installed_only:
            raise SystemExit(
                f"This interpreter does not have shacl-py commit {commit}. Rerun without --installed to use the project's build environment."
            )
        # Two upstream commits can declare the same package version.
        subprocess.run(
            [
                *pip,
                "--no-deps",
                "--force-reinstall",
                f"shacl-py @ git+{READER_REPO}@{commit}",
            ],
            check=True,
        )
    return python


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--installed",
        action="store_true",
        help="Use this interpreter's dependencies if its shacl-py commit matches main",
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
    commit = main_commit()
    print(f"Building with shacl-py/main at {commit}", flush=True)
    git_args = git_options()
    build = ROOT / ".reader-build"
    python = reader_python(build, commit, installed_only=args.installed)
    stamp = build / "shacl-py-commit.txt"
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
        *desktop_assets(build),
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
        "--collect-data",
        "streamlit",
        "--collect-submodules",
        "streamlit",
        "--recursive-copy-metadata",
        "streamlit",
        "--hidden-import",
        "shacl_py.app",
        "--exclude-module",
        "pytest",
    ]
    if not stamp.is_file() or stamp.read_text(encoding="ascii").strip() != commit:
        cmd.append("--clean")
    cmd.append(str(ROOT / "reader/main.py"))
    subprocess.run(cmd, check=True)
    frozen = build / "dist" / f"ds-reader{suffix}"
    actual = subprocess.check_output(
        [str(frozen), "--shacl-py-commit"], text=True
    ).strip()
    if actual != commit:
        raise SystemExit(
            f"The reader reports shacl-py commit {actual!r}. Expected {commit}."
        )
    dest = ROOT / "src-tauri/binaries" / f"ds-reader-{target}{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(frozen, dest)
    stamp.write_text(commit + "\n", encoding="ascii")
    print(f"Bundled shacl-py {actual} in {dest}")


if __name__ == "__main__":
    main()
