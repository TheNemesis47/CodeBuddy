"""Build the installer for this OS: brain (+ overlay or notch), launchers, docs, plugin.

  uv run --project overlay python packaging/build.py [--plugin ide-pycharm/build/distributions/x.zip]
      [--installer] [--appimagetool PATH]

Output in dist/:
- Windows: CodeBuddy-windows-<v>/ + .zip, and with --installer CodeBuddy-Setup-<v>.exe (Inno Setup).
- Linux:   CodeBuddy-linux-<v>/ + .tar.gz, and with --installer CodeBuddy-<v>-x86_64.AppImage
           (appimagetool: --appimagetool PATH or on PATH).
- macOS:   CodeBuddy.app (the Swift notch + the brain) in CodeBuddy-macos-<v>.dmg (dmgbuild).
Unsigned (macOS: ad-hoc signed only); signing is human (docs/gaps.md G15).
"""

import argparse
import os
import platform
import plistlib
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "packaging"
ASSETS = HERE / "assets"
VERSION = "0.2.0"
SYSTEM = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}[platform.system()]
EXE = ".exe" if SYSTEM == "windows" else ""
SEP = ";" if SYSTEM == "windows" else ":"
DEMO_SHOTS = 9  # overlay and notch demos: one PNG per state (app.py / main.swift)


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def pyinstaller(
    project: str, entry: Path, name: str, work: Path, extra: list[str]
) -> Path:
    """One onedir bundle built inside that project's own environment."""
    run(
        ["uv", "run", "--project", str(ROOT / project), "--with", "pyinstaller>=6.22",
         "pyinstaller", "--noconfirm", "--clean", "--onedir", "--name", name,
         "--distpath", str(work / "dist"), "--workpath", str(work / "build"),
         "--specpath", str(work), *extra, str(entry)]
    )  # fmt: skip
    return work / "dist" / name


def qt(script: str, *args: str) -> None:
    """Run a few lines of Qt (the overlay's PySide6) for image work: no Pillow needed."""
    prelude = (
        "import os,sys; os.environ.setdefault('QT_QPA_PLATFORM','offscreen');"
        "from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor;"
        "from PySide6.QtCore import Qt; app=QGuiApplication([]);"
    )
    run(
        [
            "uv",
            "run",
            "--project",
            str(ROOT / "overlay"),
            "python",
            "-c",
            prelude + script,
            *args,
        ]
    )


def icon_png(target: Path, size: int) -> None:
    """The app icon at `size` px: packaging/assets/icon.png, else Sprout drawn by the overlay."""
    source = ASSETS / "icon.png"
    if source.exists():
        qt("QImage(sys.argv[1]).scaled(int(sys.argv[3]),int(sys.argv[3]),"
           "Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)"
           ".save(sys.argv[2])", str(source), str(target), str(size))  # fmt: skip
        return
    qt("from codebuddy_overlay.sprout import draw_sprout; from codebuddy_overlay.model import Mood;"
       "n=int(sys.argv[2]); img=QImage(n,n,QImage.Format.Format_ARGB32); img.fill(QColor(0,0,0,0));"
       "p=QPainter(img); p.scale(n/100,n/100); draw_sprout(p, Mood.HAPPY, 1.0); p.end();"
       "img.save(sys.argv[1])", str(target), str(size))  # fmt: skip


def write_ico(pngs: list[Path], target: Path) -> None:
    """A Windows .ico holding PNG images (Vista+ reads them), one entry per size."""
    blobs = [p.read_bytes() for p in pngs]
    sizes = [
        struct.unpack(">II", b[16:24]) for b in blobs
    ]  # width, height from the IHDR
    offset = 6 + 16 * len(blobs)
    header = struct.pack("<HHH", 0, 1, len(blobs))
    entries = b""
    for (w, h), blob in zip(sizes, blobs, strict=True):
        entries += struct.pack(
            "<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(blob), offset
        )
        offset += len(blob)
    target.write_bytes(header + entries + b"".join(blobs))


def bmp(source: Path, target: Path, width: int, height: int) -> None:
    """Inno Setup's wizard images: 24-bit BMP, cropped to fill width × height."""
    qt("i=QImage(sys.argv[1]).scaled(int(sys.argv[3]),int(sys.argv[4]),"
       "Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation);"
       "x=(i.width()-int(sys.argv[3]))//2; y=(i.height()-int(sys.argv[4]))//2;"
       "i.copy(x,y,int(sys.argv[3]),int(sys.argv[4])).convertToFormat(QImage.Format.Format_RGB888)"
       ".save(sys.argv[2],'BMP')", str(source), str(target), str(width), str(height))  # fmt: skip


def brain_bundle(work: Path) -> Path:
    return pyinstaller(
        "brain", HERE / "buddy_main.py", "buddy", work / "brain",
        ["--console", "--collect-data", "buddy", "--collect-submodules", "uvicorn",
         "--collect-submodules", "websockets", "--collect-all", "jsonschema",
         "--collect-all", "jsonschema_specifications", "--copy-metadata", "buddy",
         "--add-data", f"{ROOT / 'protocol' / 'schemas'}{SEP}protocol/schemas"],
    )  # fmt: skip


def count_shots(shots: Path) -> None:
    found = len(list(shots.glob("*.png")))
    if found != DEMO_SHOTS:
        raise SystemExit(
            f"bundle smoke test: {found} demo snapshots, expected {DEMO_SHOTS}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", type=Path, help="the PyCharm plugin zip to include")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--installer", action="store_true", help="also build Setup.exe / AppImage"
    )
    parser.add_argument(
        "--appimagetool", type=Path, help="appimagetool (Linux, with --installer)"
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    work = args.out / "work"
    shutil.rmtree(work, ignore_errors=True)
    plugin = args.plugin if args.plugin and args.plugin.exists() else None
    if SYSTEM == "macos":
        return build_macos(args.out, work, plugin)
    package = build_folder(args.out, work, plugin)
    if SYSTEM == "windows":
        archive(package, args.out / f"{package.name}.zip")
        if args.installer:
            windows_setup(package, args.out, work)
    else:
        archive(package, args.out / f"{package.name}.tar.gz")
        if args.installer:
            appimage(package, args.out, work, args.appimagetool)
    return 0


def build_folder(out: Path, work: Path, plugin: Path | None) -> Path:
    """Linux/Windows: brain + overlay as PyInstaller folders, launchers, docs, plugin, smoke test."""
    package = out / f"CodeBuddy-{SYSTEM}-{VERSION}"
    shutil.rmtree(package, ignore_errors=True)
    package.mkdir(parents=True)
    brain = brain_bundle(work)
    overlay = pyinstaller(
        "overlay", HERE / "overlay_main.py", "codebuddy-overlay", work / "overlay",
        ["--windowed" if SYSTEM == "windows" else "--console",
         "--collect-submodules", "websockets"],
    )  # fmt: skip
    shutil.copytree(brain, package / "brain")
    shutil.copytree(overlay, package / "overlay")
    shutil.copy(ROOT / "INSTALL.md", package / "INSTALL.md")
    shutil.copy(ROOT / f"docs/install/{SYSTEM}.md", package / f"INSTALL-{SYSTEM}.md")
    if plugin:
        shutil.copy(plugin, package / plugin.name)
    if SYSTEM == "windows":
        shutil.copy(HERE / "CodeBuddy.cmd", package / "CodeBuddy.cmd")
    else:
        for script in ("codebuddy.sh", "install-desktop-entry.sh"):
            shutil.copy(HERE / script, package / script)
            mode = (package / script).stat().st_mode
            (package / script).chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        shutil.copy(HERE / "codebuddy.desktop", package / "codebuddy.desktop")
        icon_png(package / "codebuddy.png", 256)

    run([str(package / "brain" / f"buddy{EXE}"), "--help"])
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen"),
    }
    shots = out / f"bundle-snapshots-{SYSTEM}"
    shutil.rmtree(shots, ignore_errors=True)
    print("+ overlay --demo --snapshots", shots, flush=True)
    subprocess.run(
        [str(package / "overlay" / f"codebuddy-overlay{EXE}"), "--demo", "--snapshots", str(shots)],
        check=True, env=env, timeout=120,
    )  # fmt: skip
    count_shots(shots)
    return package


def archive(package: Path, target: Path) -> None:
    if target.suffix == ".zip":
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(package.rglob("*")):
                zf.write(path, Path(package.name) / path.relative_to(package))
    else:
        with tarfile.open(target, "w:gz") as tf:
            tf.add(package, arcname=package.name)
    print(f"built {target} ({target.stat().st_size // (1024 * 1024)} MB)")


def windows_setup(package: Path, out: Path, work: Path) -> None:
    """CodeBuddy-Setup-<v>.exe with Inno Setup 6 (per-user, Start menu, optional autostart)."""
    iscc = shutil.which("ISCC") or next(
        (str(p) for p in (Path(os.environ.get(v, "")) / "Inno Setup 6" / "ISCC.exe"
                          for v in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")) if p.is_file()),
        None,
    )  # fmt: skip
    if iscc is None:
        raise SystemExit(
            "--installer: Inno Setup 6 (ISCC.exe) not found; choco install innosetup"
        )
    art = work / "setup-art"
    art.mkdir(parents=True)
    pngs = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon_png(art / f"icon-{size}.png", size)
        pngs.append(art / f"icon-{size}.png")
    write_ico(pngs, art / "codebuddy.ico")
    wizard = (
        ASSETS / "wizard.png"
        if (ASSETS / "wizard.png").exists()
        else art / "icon-256.png"
    )
    bmp(
        wizard, art / "wizard.bmp", 410, 797
    )  # Inno's 200% size of the 164 × 314 side image
    bmp(art / "icon-256.png" if not (ASSETS / "icon.png").exists() else ASSETS / "icon.png",
        art / "wizard-small.bmp", 138, 140)  # fmt: skip
    run([iscc, f"/DVersion={VERSION}", f"/DSource={package}", f"/DAssets={art}", f"/DOut={out}",
         str(HERE / "windows" / "CodeBuddy.iss")])  # fmt: skip
    setup = out / f"CodeBuddy-Setup-{VERSION}.exe"
    print(f"built {setup} ({setup.stat().st_size // (1024 * 1024)} MB)")


def appimage(package: Path, out: Path, work: Path, tool: Path | None) -> None:
    """CodeBuddy-<v>-x86_64.AppImage: one file, double-click to run (FUSE, or it self-extracts)."""
    found = str(tool) if tool else shutil.which("appimagetool")
    if not found:
        raise SystemExit(
            "--installer: appimagetool not found (pass --appimagetool PATH)"
        )
    appdir = work / "CodeBuddy.AppDir"
    lib = appdir / "usr" / "lib" / "codebuddy"
    lib.mkdir(parents=True)
    shutil.copytree(package / "brain", lib / "brain", symlinks=True)
    shutil.copytree(package / "overlay", lib / "overlay", symlinks=True)
    shutil.copy(HERE / "linux" / "AppRun", appdir / "AppRun")
    (appdir / "AppRun").chmod(0o755)
    shutil.copy(HERE / "linux" / "codebuddy.desktop", appdir / "codebuddy.desktop")
    icon_png(appdir / "codebuddy.png", 256)
    target = out / f"CodeBuddy-{VERSION}-x86_64.AppImage"
    env = {**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"}
    subprocess.run(
        [found, "--no-appstream", str(appdir), str(target)], check=True, env=env
    )
    print(f"built {target} ({target.stat().st_size // (1024 * 1024)} MB)")


def build_macos(out: Path, work: Path, plugin: Path | None) -> int:
    """CodeBuddy.app = the Swift notch (Contents/MacOS) + the brain (Contents/Resources/brain),
    in a .dmg with a drag-to-Applications window. Apple Silicon (the runner's and the brain's arch)."""
    notch = ROOT / "notch"
    run(["swift", "build", "-c", "release", "--product", "CodeBuddy"], cwd=notch)
    bin_dir = subprocess.run(["swift", "build", "-c", "release", "--show-bin-path"], cwd=notch,
                             check=True, capture_output=True, text=True).stdout.strip()  # fmt: skip
    app = work / "CodeBuddy.app"
    contents = app / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources").mkdir()
    shutil.copy(Path(bin_dir) / "CodeBuddy", contents / "MacOS" / "CodeBuddy")
    plist = plistlib.loads(
        (HERE / "macos" / "Info.plist")
        .read_bytes()
        .replace(b"@VERSION@", VERSION.encode())
    )
    (contents / "Info.plist").write_bytes(plistlib.dumps(plist))
    shutil.copytree(brain_bundle(work), contents / "Resources" / "brain", symlinks=True)
    shutil.copy(ROOT / "THIRD_PARTY.md", contents / "Resources" / "THIRD_PARTY.md")
    iconset = work / "AppIcon.iconset"
    iconset.mkdir()
    for size in (16, 32, 128, 256, 512):
        icon_png(iconset / f"icon_{size}x{size}.png", size)
        icon_png(iconset / f"icon_{size}x{size}@2x.png", size * 2)
    run(
        [
            "iconutil",
            "-c",
            "icns",
            str(iconset),
            "-o",
            str(contents / "Resources" / "AppIcon.icns"),
        ]
    )
    # One ad-hoc signature over the whole bundle: Apple Silicon runs nothing unsigned.
    run(["codesign", "--force", "--deep", "--sign", "-", str(app)])

    run([str(contents / "Resources" / "brain" / "buddy"), "--help"])
    shots = out / "bundle-snapshots-macos"
    shutil.rmtree(shots, ignore_errors=True)
    subprocess.run([str(contents / "MacOS" / "CodeBuddy"), "--demo", "--snapshots", str(shots)],
                   check=True, timeout=120)  # fmt: skip
    count_shots(shots)

    background = ASSETS / "dmg-background.png"
    if not background.exists():
        raise SystemExit(f"missing {background}")
    dmg = out / f"CodeBuddy-macos-{VERSION}.dmg"
    dmg.unlink(missing_ok=True)
    run(["uv", "run", "--project", str(ROOT / "overlay"), "--with", "dmgbuild>=1.6", "dmgbuild",
         "-s", str(HERE / "macos" / "dmg_settings.py"), "-D", f"app={app}",
         "-D", f"plugin={plugin or ''}", "-D", f"background={background}", "CodeBuddy", str(dmg)])  # fmt: skip
    print(f"built {dmg} ({dmg.stat().st_size // (1024 * 1024)} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
