"""Where the panel goes on Linux desktops that don't tell Qt the truth (docs/install/linux.md).

Two problems, both solved here and not in user config:

1. On Wayland a client can't place itself, and wlroots compositors (Hyprland, Sway, river…) also
   ignore its resizes, so the panel would stay a pill wherever the compositor dropped it. Under
   XWayland its own geometry code works: `qt_platform_for` picks `xcb` when the user didn't pick
   a platform and XWayland is there.
2. A layer-shell bar (Waybar, Omarchy's bar, swaybar…) is drawn over normal windows and takes the
   clicks in its strip, but XWayland is never told it is there: Qt reports the whole screen as
   available and the panel would open under the bar. `top_placement` asks the compositor how much
   it reserves at the top; `BUDDY_TOP_OFFSET` (or `[overlay] top_offset` in the config file) is
   the manual answer for any other desktop.

Pure functions on the environment and on the compositor's JSON, plus one `probe` that runs the
compositor's CLI with a short timeout. Nothing here is needed on macOS or Windows.
"""

import json
import subprocess
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeIs

import platformdirs

PROBE_TIMEOUT_S = 1.0

type Run = Callable[[Sequence[str]], str | None]
type Tops = dict[tuple[int, int], int]  # monitor's top-left corner → pixels reserved at its top


def qt_platform_for(env: Mapping[str, str], platform: str) -> str | None:
    """`xcb` on a Linux Wayland session with XWayland, unless the user chose a Qt platform."""
    if platform != "linux" or env.get("QT_QPA_PLATFORM") or not env.get("WAYLAND_DISPLAY"):
        return None
    return "xcb" if env.get("DISPLAY") else None


def parse_offset(value: object) -> int | None:
    """A pixel count ≥ 0, or None for "auto", empty, negative or garbage."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        try:
            number = int(value.strip())
        except ValueError:
            return None
        return number if number >= 0 else None
    return None


@dataclass(frozen=True)
class TopPlacement:
    """How far from the top of the screen the panel sits.

    `explicit` (from the user) is measured from the screen's top edge and wins. Otherwise the panel
    goes below whatever is lower: the area Qt says is free, or the strip the compositor reserves.
    """

    explicit: int | None = None
    reserved: int = 0

    def y(self, screen_y: int, available_y: int) -> int:
        if self.explicit is not None:
            return screen_y + self.explicit
        return max(available_y, screen_y + self.reserved)


def _is_int(value: object) -> TypeIs[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def hyprland_tops(monitors: object) -> Tops:
    """`hyprctl -j monitors`: each monitor has `x`, `y`, `reserved` = [left, top, right, bottom]."""
    tops: Tops = {}
    for monitor in monitors if isinstance(monitors, list) else []:
        reserved = monitor.get("reserved") if isinstance(monitor, dict) else None
        if not isinstance(reserved, list) or len(reserved) != 4:
            continue
        x, y, top = monitor.get("x"), monitor.get("y"), reserved[1]
        if _is_int(x) and _is_int(y) and _is_int(top):
            tops[(x, y)] = max(0, top)
    return tops


def sway_tops(outputs: object, workspaces: object) -> Tops:
    """`swaymsg -t get_outputs` / `get_workspaces`: a visible workspace's rect is its output's rect
    minus what bars reserve, so the difference at the top is the bar."""
    output_rects: dict[str, dict[str, Any]] = {}
    for output in outputs if isinstance(outputs, list) else []:
        if (
            isinstance(output, dict)
            and output.get("active")
            and isinstance(output.get("rect"), dict)
        ):
            output_rects[str(output.get("name"))] = output["rect"]
    tops: Tops = {}
    for workspace in workspaces if isinstance(workspaces, list) else []:
        if not isinstance(workspace, dict) or not workspace.get("visible"):
            continue
        rect, screen = workspace.get("rect"), output_rects.get(str(workspace.get("output")))
        if not isinstance(rect, dict) or screen is None:
            continue
        try:
            tops[(int(screen["x"]), int(screen["y"]))] = max(0, int(rect["y"]) - int(screen["y"]))
        except KeyError, TypeError, ValueError:
            continue
    return tops


def top_for_screen(tops: Tops, screen_x: int, screen_y: int) -> int:
    """The strip above this screen; when the compositor's monitor positions don't match Qt's, the
    largest one: a strip too tall is harmless, one too short leaves the panel under the bar."""
    if (screen_x, screen_y) in tops:
        return tops[(screen_x, screen_y)]
    return max(tops.values(), default=0)


def _run(command: Sequence[str]) -> str | None:
    try:
        result = subprocess.run(
            list(command), capture_output=True, text=True, timeout=PROBE_TIMEOUT_S, check=False
        )
    except OSError, subprocess.SubprocessError:
        return None
    return result.stdout if result.returncode == 0 else None


def _json(text: str | None) -> object:
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def config_path(env: Mapping[str, str]) -> Path:
    """The brain's settings file (brain/src/buddy/settings.py: same rule)."""
    if path := env.get("BUDDY_CONFIG"):
        return Path(path)
    folder = platformdirs.user_config_dir("CodeBuddy", appauthor=False, roaming=False)
    return Path(folder) / "config.toml"


def configured_top_offset(env: Mapping[str, str]) -> object:
    """`[overlay] top_offset` from the settings file, or None. A missing or broken file is not
    the panel's problem: the brain reports it."""
    try:
        data = tomllib.loads(config_path(env).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    overlay = data.get("overlay")
    return overlay.get("top_offset") if isinstance(overlay, dict) else None


def compositor_tops(env: Mapping[str, str], run: Run = _run) -> tuple[str, Tops] | None:
    """Ask the running compositor what it reserves at the top of each monitor, if we know how."""
    if env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "hyprland", hyprland_tops(_json(run(["hyprctl", "-j", "monitors"])))
    if env.get("SWAYSOCK"):
        outputs = _json(run(["swaymsg", "-r", "-t", "get_outputs"]))
        workspaces = _json(run(["swaymsg", "-r", "-t", "get_workspaces"]))
        return "sway", sway_tops(outputs, workspaces)
    return None


def top_placement(
    env: Mapping[str, str],
    screen_x: int,
    screen_y: int,
    configured: object = None,
    run: Run = _run,
) -> tuple[TopPlacement, str]:
    """The placement for this desktop, and a line for the log saying where it came from.

    Order: `BUDDY_TOP_OFFSET`, then `configured` (the config file), then the compositor (Wayland
    only), then Qt's own available area."""
    for source, value in (
        ("BUDDY_TOP_OFFSET", env.get("BUDDY_TOP_OFFSET")),
        ("config", configured),
    ):
        explicit = parse_offset(value)
        if explicit is not None:
            return TopPlacement(explicit=explicit), f"top offset {explicit} px ({source})"
    if env.get("WAYLAND_DISPLAY"):
        found = compositor_tops(env, run)
        if found is not None:
            name, tops = found
            reserved = top_for_screen(tops, screen_x, screen_y)
            return TopPlacement(reserved=reserved), f"top offset {reserved} px (from {name})"
    return TopPlacement(), "top offset from the desktop's work area"
