"""Install the generated artefact temporarily and run the real reader from it."""

import json
import os
import plistlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_reader import check_store


def smoke(install, tmp):
    win = os.name == "nt"
    helper = next(install.rglob("ds-reader.exe" if win else "ds-reader"))
    check_store(helper, tmp)
    if win:
        app = next(
            p
            for p in helper.parent.glob("*.exe")
            if p != helper and "uninstall" not in p.name.lower()
        )
    else:
        with (helper.parent.parent / "Info.plist").open("rb") as stream:
            app = helper.with_name(plistlib.load(stream)["CFBundleExecutable"])
    # Only the launched desktop app gets this trace. The store read proves that
    # its actual webview crossed the Tauri IPC boundary and called MetaLad.
    trace = tmp / "desktop-git-trace.jsonl"
    proc = subprocess.Popen(
        [str(app), str(tmp / "data set å")],
        env={**os.environ, "GIT_TRACE2_EVENT": str(trace)},
    )
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"Desktop application exited at launch: {proc.returncode}"
                )
            if trace.exists():
                lines = trace.read_bytes().split(b"\n")[:-1]
                started = [
                    row.get("argv", [])
                    for raw in lines
                    if raw and (row := json.loads(raw)).get("event") == "start"
                ]
                if any(
                    "refs/datalad/dataset-uuid-set" in args for args in started
                ) and any("cat-file" in args for args in started):
                    print(
                        "Installed desktop app opened the project through DataLad MetaLad."
                    )
                    break
            time.sleep(0.25)
        else:
            raise RuntimeError(
                "The installed desktop app did not read the test MetaLad store."
            )
    finally:
        if win:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], check=False)
        else:
            proc.terminate()
        proc.wait(timeout=20)


def main():
    bundle = ROOT / "src-tauri/target/release/bundle"
    with tempfile.TemporaryDirectory() as work:
        tmp = Path(work)
        install = tmp / "DS View"
        if sys.platform == "darwin":
            dmg = next((bundle / "dmg").glob("*.dmg"))
            mount = tmp / "disk-image"
            subprocess.run(
                [
                    "hdiutil",
                    "attach",
                    str(dmg),
                    "-mountpoint",
                    str(mount),
                    "-nobrowse",
                    "-readonly",
                ],
                check=True,
            )
            try:
                # Match drag-to-Applications installation and eject before launching.
                subprocess.run(
                    [
                        "ditto",
                        str(next(mount.glob("*.app"))),
                        str(install / "DS View.app"),
                    ],
                    check=True,
                )
            finally:
                subprocess.run(["hdiutil", "detach", str(mount)], check=True)
            smoke(install, tmp)
        elif os.name == "nt":
            installer = next((bundle / "nsis").glob("*-setup.exe"))
            # NSIS requires /D to be the final argument and unquoted, including spaces.
            cmd = f'"{installer}" /S /D={install}'
            subprocess.run(cmd, check=True, timeout=180)
            smoke(install, tmp)
        else:
            raise SystemExit("Run the installer check on macOS or Windows.")


if __name__ == "__main__":
    main()
