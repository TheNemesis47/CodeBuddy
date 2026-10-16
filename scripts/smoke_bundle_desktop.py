"""The packaged overlay on a Hyprland-like desktop: what only breaks inside a PyInstaller build.

The 0.1.1 reports (Omarchy/Hyprland) found bugs the source-tree tests could not see: the
bundle's LD_LIBRARY_PATH broke the system `hyprctl` (offset always 0), the distro's
QT_QPA_PLATFORM="wayland;xcb" kept the panel off XWayland, and the config file's `top_offset` was
never read. This runs the built `codebuddy-overlay` with a fake `hyprctl` on PATH (it records the
library path it was started with) and checks the log lines that say what the panel decided.

Linux only, on an X server (CI: xvfb-run). Standard library only.
Usage: python3 scripts/smoke_bundle_desktop.py dist/CodeBuddy-linux-0.2.0 OUTDIR
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FAKE_HYPRCTL = """#!/bin/sh
printf '%s' "${{LD_LIBRARY_PATH:-}}" > {seen}
case "$1" in
  dispatch)
    printf '%s' "$*" > {pinned}
    echo ok ;;
  clients)
    # Pinned only after the panel asked for it: the retry has to stop on its own.
    if [ -s {pinned} ]; then
      printf '[{{"pid": %s, "pinned": true}}]' "$(sed -n 's/.*pid:\\([0-9]*\\).*/\\1/p' {pinned})"
    else
      echo '[]'
    fi ;;
  *)
    echo '[{{"name": "DP-1", "focused": true, "x": 0, "y": 0, "reserved": [0, 30, 0, 0]}}]' ;;
esac
"""


def run(overlay: Path, env: dict[str, str], log: Path) -> str:
    with log.open("wb") as out:
        subprocess.run(
            [str(overlay), "--demo", "--quit-after", "2"],
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
            timeout=60,
            check=False,
        )
    return log.read_text(errors="replace")


def main() -> int:
    if sys.platform != "linux" or len(sys.argv) != 3:
        raise SystemExit(__doc__)
    bundle, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    overlay = bundle / "overlay" / "codebuddy-overlay"
    work = Path(tempfile.mkdtemp(prefix="codebuddy-smoke-"))
    seen = work / "hyprctl-saw-LD_LIBRARY_PATH"
    pinned = work / "hyprctl-pin-dispatch"
    fake_bin = work / "bin"
    fake_bin.mkdir()
    hyprctl = fake_bin / "hyprctl"
    hyprctl.write_text(FAKE_HYPRCTL.format(seen=seen, pinned=pinned), encoding="utf-8")
    hyprctl.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
        "WAYLAND_DISPLAY": "wayland-ci",  # Qt never opens it: the panel picks xcb
        "HYPRLAND_INSTANCE_SIGNATURE": "ci",
        "QT_QPA_PLATFORM": "wayland;xcb",  # what Omarchy sets for the whole session
        "BUDDY_CONFIG": str(work / "no-config.toml"),
        "BUDDY_HOME": str(work / "home"),
    }
    env.pop("BUDDY_TOP_OFFSET", None)
    env.pop("LD_LIBRARY_PATH", None)

    problems = []
    log = run(overlay, env, out / "hyprland.log")
    for expected in (
        "using XWayland",
        "top offset 30 px (from hyprland) on DP-1; Qt platform xcb",
        "X11 window type: dock",
    ):
        if expected not in log:
            problems.append(f"hyprland.log has no {expected!r}")
    pin = pinned.read_text() if pinned.exists() else ""
    if "pin" not in pin or "pid:" not in pin:
        problems.append(f"the panel never asked Hyprland to pin it: {pin!r}")
    if "could not pin" in log:
        problems.append("the panel gave up pinning even though hyprctl said it worked")
    library_path = seen.read_text() if seen.exists() else None
    if library_path is None:
        problems.append("the overlay never ran hyprctl")
    elif str(bundle) in library_path:
        problems.append(f"hyprctl got the bundle's LD_LIBRARY_PATH: {library_path}")

    config = work / "config.toml"
    config.write_text("[overlay]\ntop_offset = 64\n", encoding="utf-8")
    log = run(overlay, {**env, "BUDDY_CONFIG": str(config)}, out / "config.log")
    if "top offset 64 px (config)" not in log:
        problems.append("config.log: the config file's top_offset was not used")

    result = {
        "ok": not problems,
        "problems": problems,
        "hyprctl_LD_LIBRARY_PATH": library_path,
        "pin_dispatch": pin,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
