"""The overlay on a real Wayland compositor with a top bar: Sway, headless, with swaybar.

This is the setup from the Linux Wayland report (Hyprland + a layer-shell bar), on the wlroots
compositor that runs in CI: XWayland publishes no work area, so Qt alone would put the panel at
y = 0, under the bar. Passes when, during `--demo`, the panel takes all three sizes (pill, ears,
open panel), always centred and always right below the bar, and the overlay logged that the
offset came from Sway. Saves screenshots (grim) of the whole screen per state.

Then the pointer, through the compositor as a real mouse goes (a virtual pointer device,
scripts/wl_pointer.py): over the pill the panel must open its ears, and a click must open it. 0.1.1 shipped a panel Hyprland gave no pointer events to, and no test had ever touched it.

Linux only. Needs: sway, xwayland, grim, x11-utils (xwininfo).
Usage: uv run --project overlay python scripts/e2e_wayland.py OUTDIR
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from wl_pointer import VirtualPointer

ROOT = Path(__file__).resolve().parent.parent
SCREEN = (1920, 1080)
SIZES = {"hidden": (80, 24), "peek": (232, 24), "expanded": (520, 380)}  # overlay geometry.py
SAMPLE_S = 9.0  # the demo's timeline, from the moment the pill shows
START_S = 20.0  # Sway starts XWayland on the first X client: seconds, some runs

CONFIG = """
xwayland enable
output HEADLESS-1 resolution {w}x{h} position 0 0
default_border none
bar {{
    position top
    status_command while date +'%H:%M:%S'; do sleep 1; done
}}
exec {python} {script} inside {out}
"""


def outside(out: Path) -> int:
    """Start Sway headless; it runs `inside` and exits when that is done."""
    for tool in ("sway", "grim", "xwininfo"):
        if shutil.which(tool) is None:
            raise SystemExit(f"e2e-wayland: {tool} is not installed")
    out.mkdir(parents=True, exist_ok=True)
    config = Path(tempfile.mkdtemp(prefix="codebuddy-sway-")) / "config"
    config.write_text(
        CONFIG.format(
            w=SCREEN[0], h=SCREEN[1], python=sys.executable, script=Path(__file__), out=out
        ),
        encoding="utf-8",
    )
    runtime = Path(tempfile.mkdtemp(prefix="xdg-runtime-"))
    runtime.chmod(0o700)
    env = {
        **os.environ,
        "WLR_BACKENDS": "headless",
        "WLR_LIBINPUT_NO_DEVICES": "1",
        "WLR_RENDERER": "pixman",
        "XDG_RUNTIME_DIR": str(runtime),
    }
    for name in ("WAYLAND_DISPLAY", "DISPLAY", "QT_QPA_PLATFORM", "SWAYSOCK"):
        env.pop(name, None)
    with (out / "sway.log").open("wb") as log:
        try:
            subprocess.run(["sway", "-c", str(config)], env=env, stdout=log, stderr=log, timeout=90)
        except subprocess.TimeoutExpired:
            print("e2e-wayland: sway did not exit within 90 s", file=sys.stderr)
    result_file = out / "result.json"
    if not result_file.exists():
        print((out / "sway.log").read_text(errors="replace")[-3000:], file=sys.stderr)
        raise SystemExit("e2e-wayland: no result (see sway.log)")
    result = json.loads(result_file.read_text(encoding="utf-8"))
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def bar_height() -> int:
    workspaces = json.loads(
        subprocess.run(
            ["swaymsg", "-r", "-t", "get_workspaces"], capture_output=True, text=True, check=True
        ).stdout
    )
    return next(int(w["rect"]["y"]) for w in workspaces if w.get("visible"))


GEOMETRY = re.compile(
    r"Absolute upper-left X:\s+(-?\d+).*?Absolute upper-left Y:\s+(-?\d+).*?"
    r"Width:\s+(\d+).*?Height:\s+(\d+)",
    re.S,
)


def panel_geometry() -> tuple[int, int, int, int] | None:
    found = subprocess.run(
        ["xwininfo", "-name", "CodeBuddy"], capture_output=True, text=True, check=False
    )
    match = GEOMETRY.search(found.stdout)
    return tuple(int(v) for v in match.groups()) if match else None  # type: ignore[return-value]


def wait_for_size(size: tuple[int, int], within_s: float) -> tuple[int, int, int, int] | None:
    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        geometry = panel_geometry()
        if geometry is not None and geometry[2:] == size:
            return geometry
        time.sleep(0.1)
    return None


def pointer_phase(out: Path, env: dict[str, str], bar: int) -> list[str]:
    """No brain (it stays "off"): hover the pill → ears, click → open panel."""
    home = Path(tempfile.mkdtemp(prefix="codebuddy-home-"))
    overlay = subprocess.Popen(
        [sys.executable, "-m", "codebuddy_overlay.app", "--quit-after", "20"],
        env={**env, "BUDDY_HOME": str(home), "BUDDY_PORT": "1"},
        stdout=(out / "overlay-pointer.log").open("wb"),
        stderr=subprocess.STDOUT,
    )
    problems = []
    mouse = None
    try:
        hidden = wait_for_size(SIZES["hidden"], 8)
        if hidden is None:
            return ["pointer: the pill never showed"]
        # A headless Sway has no pointer device: a virtual one gives the seat (and XWayland) one.
        mouse = VirtualPointer(*SCREEN)
        mouse.move_to(SCREEN[0] // 2, SCREEN[1] // 2)  # away from the panel first
        time.sleep(0.5)
        x, y, w, h = hidden
        mouse.move_to(x + w // 2, y + h // 2)
        if wait_for_size(SIZES["peek"], 4) is None:
            problems.append("pointer: hovering the pill did not open its ears (no enter event)")
        else:
            subprocess.run(["grim", str(out / "pointer-peek.png")], check=False)
        peek = panel_geometry() or hidden
        mouse.move_to(peek[0] + peek[2] // 2, peek[1] + peek[3] // 2)
        mouse.click()
        if wait_for_size(SIZES["expanded"], 4) is None:
            problems.append("pointer: clicking the pill did not open the panel (no press event)")
        else:
            subprocess.run(["grim", str(out / "pointer-expanded.png")], check=False)
        geometry = panel_geometry()
        if geometry is not None and geometry[1] != bar:
            problems.append(f"pointer: the panel moved to y = {geometry[1]}, expected {bar}")
    except (OSError, RuntimeError) as error:
        problems.append(f"pointer: no virtual mouse ({error})")
    finally:
        overlay.kill()
        if mouse is not None:
            try:
                mouse.close()
            except OSError, RuntimeError:
                pass  # the compositor is about to exit anyway
    return problems


def inside(out: Path) -> None:
    """Runs as a child of Sway: WAYLAND_DISPLAY, SWAYSOCK and DISPLAY are set."""
    result: dict[str, object] = {"ok": False}
    overlay = None
    try:
        time.sleep(1.5)  # let swaybar map and reserve its strip
        bar = bar_height()
        result["bar_height"] = bar
        result["env"] = {k: os.environ.get(k) for k in ("WAYLAND_DISPLAY", "DISPLAY", "SWAYSOCK")}
        # Qt's fallback chain, as distros set it session-wide (Omarchy): the panel still picks xcb.
        env = {**os.environ, "QT_QPA_PLATFORM": "wayland;xcb"}
        log_path = out / "overlay.log"
        overlay = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "codebuddy_overlay.app",
                "--demo",
                "--quit-after",
                str(START_S + SAMPLE_S),
            ],
            env=env,
            stdout=log_path.open("wb"),
            stderr=subprocess.STDOUT,
        )
        seen: dict[tuple[int, int, int, int], float] = {}
        shots: dict[str, str] = {}
        launched = time.monotonic()
        while panel_geometry() is None and time.monotonic() - launched < START_S:
            time.sleep(0.1)
        started = time.monotonic()
        result["start_s"] = round(started - launched, 2)
        while time.monotonic() - started < SAMPLE_S:
            geometry = panel_geometry()
            if geometry is not None and geometry not in seen:
                seen[geometry] = round(time.monotonic() - started, 2)
                state = next((s for s, size in SIZES.items() if size == geometry[2:]), None)
                if state and state not in shots:
                    time.sleep(0.3)  # let it paint
                    shot = out / f"wayland-{state}.png"
                    subprocess.run(["grim", str(shot)], check=False)
                    shots[state] = shot.name
            time.sleep(0.1)
        overlay.kill()  # the demo is over; its log lines are flushed as they are written
        overlay.wait(timeout=10)
        log = log_path.read_text(errors="replace")
        problems = []
        for state, (w, h) in SIZES.items():
            matching = [g for g in seen if (g[2], g[3]) == (w, h)]
            if not matching:
                problems.append(f"{state}: the panel never took its {w}x{h} size")
            for x, y, _, _ in matching:
                if y != bar:
                    problems.append(f"{state}: y = {y}, expected {bar} (right below the bar)")
                if x != (SCREEN[0] - w) // 2:
                    problems.append(f"{state}: x = {x}, not centred")
        if "from sway" not in log:
            problems.append("the overlay did not take the offset from Sway (see overlay.log)")
        if "using XWayland" not in log:
            problems.append("the overlay did not switch to XWayland (see overlay.log)")
        problems += pointer_phase(out, env, bar)
        result.update(
            ok=not problems,
            problems=problems,
            geometries=[{"at_s": t, "geometry": list(g)} for g, t in seen.items()],
            screenshots=shots,
        )
    except Exception as error:
        result["problems"] = [f"{type(error).__name__}: {error}"]
    finally:
        if overlay is not None and overlay.poll() is None:
            overlay.kill()
        (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        subprocess.run(["swaymsg", "exit"], check=False)


def main() -> int:
    if sys.platform != "linux":
        raise SystemExit("e2e-wayland: Linux only")
    if len(sys.argv) == 3 and sys.argv[1] == "inside":
        inside(Path(sys.argv[2]))
        return 0
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    return outside(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    sys.exit(main())
