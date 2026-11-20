"""Install the generated artefact temporarily and run the real reader from it."""
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
        app = next(p for p in helper.parent.glob("*.exe") if p != helper and "uninstall" not in p.name.lower())
    else:
        with (helper.parent.parent / "Info.plist").open("rb") as stream:
            app = helper.with_name(plistlib.load(stream)["CFBundleExecutable"])
    proc = subprocess.Popen([str(app), str(tmp / "data set å")])
    try:
        time.sleep(6)
        if proc.poll() is not None:
            raise RuntimeError(f"Desktop application exited at launch: {proc.returncode}")
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
            subprocess.run(["hdiutil", "attach", str(dmg), "-mountpoint", str(install), "-nobrowse"], check=True)
            try:
                smoke(install, tmp)
            finally:
                subprocess.run(["hdiutil", "detach", str(install)], check=True)
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
