"""Build the tester package for this OS: brain + overlay as PyInstaller folders, launchers, docs.

  uv run --project overlay python packaging/build.py [--plugin ide-pycharm/build/distributions/x.zip]

Output: dist/CodeBuddy-<os>-<version>/ and its archive (.zip on Windows, .tar.gz elsewhere). macOS
testers keep using the Swift notch; a macOS build here exists only to test this script.
"""

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "packaging"
VERSION = "0.1.1"
SYSTEM = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}[platform.system()]
EXE = ".exe" if SYSTEM == "windows" else ""
SEP = ";" if SYSTEM == "windows" else ":"


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def pyinstaller(project: str, entry: Path, name: str, work: Path, extra: list[str]) -> Path:
    """One onedir bundle built inside that project's own environment."""
    run(
        ["uv", "run", "--project", str(ROOT / project), "--with", "pyinstaller>=6.22",
         "pyinstaller", "--noconfirm", "--clean", "--onedir", "--name", name,
         "--distpath", str(work / "dist"), "--workpath", str(work / "build"),
         "--specpath", str(work), *extra, str(entry)]
    )  # fmt: skip
    return work / "dist" / name


def sprout_icon(target: Path) -> None:
    """A 256 px icon drawn by the overlay's own Sprout code, so there is no image to maintain."""
    run(
        ["uv", "run", "--project", str(ROOT / "overlay"), "python", "-c",
         "import os,sys; os.environ.setdefault('QT_QPA_PLATFORM','offscreen');"
         "from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor;"
         "from codebuddy_overlay.sprout import draw_sprout; from codebuddy_overlay.model import Mood;"
         "app=QGuiApplication([]); img=QImage(256,256,QImage.Format.Format_ARGB32);"
         "img.fill(QColor(0,0,0,0)); p=QPainter(img); p.scale(2.56,2.56);"
         "draw_sprout(p, Mood.HAPPY, 1.0); p.end(); img.save(sys.argv[1])", str(target)]
    )  # fmt: skip


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", type=Path, help="the PyCharm plugin zip to include")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()

    name = f"CodeBuddy-{SYSTEM}-{VERSION}"
    work = args.out / "work"
    package = args.out / name
    shutil.rmtree(package, ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
    package.mkdir(parents=True)

    brain = pyinstaller(
        "brain", HERE / "buddy_main.py", "buddy", work / "brain",
        ["--console", "--collect-data", "buddy", "--collect-submodules", "uvicorn",
         "--collect-submodules", "websockets", "--collect-all", "jsonschema",
         "--collect-all", "jsonschema_specifications", "--copy-metadata", "buddy",
         "--add-data", f"{ROOT / 'protocol' / 'schemas'}{SEP}protocol/schemas"],
    )  # fmt: skip
    overlay = pyinstaller(
        "overlay", HERE / "overlay_main.py", "codebuddy-overlay", work / "overlay",
        ["--windowed" if SYSTEM == "windows" else "--console",
         "--collect-submodules", "websockets"],
    )  # fmt: skip
    shutil.copytree(brain, package / "brain")
    shutil.copytree(overlay, package / "overlay")

    shutil.copy(ROOT / "INSTALL.md", package / "INSTALL.md")
    shutil.copy(ROOT / f"docs/install/{SYSTEM}.md", package / f"INSTALL-{SYSTEM}.md")
    if args.plugin and args.plugin.exists():
        shutil.copy(args.plugin, package / args.plugin.name)
    if SYSTEM == "windows":
        shutil.copy(HERE / "CodeBuddy.cmd", package / "CodeBuddy.cmd")
    else:
        for script in ("codebuddy.sh", "install-desktop-entry.sh"):
            shutil.copy(HERE / script, package / script)
            mode = (package / script).stat().st_mode
            (package / script).chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        shutil.copy(HERE / "codebuddy.desktop", package / "codebuddy.desktop")
        sprout_icon(package / "codebuddy.png")

    # Smoke test the bundles before archiving them.
    run([str(package / "brain" / f"buddy{EXE}"), "--help"])
    env = {**os.environ, "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen")}
    shots = args.out / f"bundle-snapshots-{SYSTEM}"
    print("+ overlay --demo --snapshots", shots, flush=True)
    subprocess.run(
        [str(package / "overlay" / f"codebuddy-overlay{EXE}"), "--demo", "--snapshots", str(shots)],
        check=True, env=env, timeout=120,
    )  # fmt: skip
    if len(list(shots.glob("demo-*.png"))) != 8:
        raise SystemExit("bundle smoke test: the overlay did not save 8 snapshots")

    if SYSTEM == "windows":
        archive = args.out / f"{name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(package.rglob("*")):
                zf.write(path, Path(name) / path.relative_to(package))
    else:
        archive = args.out / f"{name}.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(package, arcname=name)
    print(f"built {archive} ({archive.stat().st_size // (1024 * 1024)} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
