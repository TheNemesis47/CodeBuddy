"""Where the panel goes on Linux desktops that don't tell Qt the truth (docs/install/linux.md).

Three problems, all solved here and not in user config:

1. On Wayland a client can't place itself, and wlroots compositors (Hyprland, Sway, river…) also
   ignore its resizes, so the panel would stay a pill wherever the compositor dropped it. Under
   XWayland its own geometry code works: `qt_platform_for` picks `xcb` when the user didn't pick
   one platform and XWayland is there.
2. A layer-shell bar (Waybar, Omarchy's bar, swaybar…) is drawn over normal windows and takes the
   clicks in its strip, but XWayland is never told it is there: Qt reports the whole screen as
   available and the panel would open under the bar. `panel_placement` asks the compositor how
   much it reserves at the top; `BUDDY_TOP_OFFSET` (or `[overlay] top_offset` in the config file)
   is the manual answer for any other desktop.
3. XWayland publishes an X11 layout of its own, which need not match the compositor's: on two
   monitors Qt's "primary" can be the wrong one, and its origins can be shifted. Centring on Qt's
   primary then put the panel off every screen. `panel_placement` picks the monitor the compositor
   calls focused (or `BUDDY_MONITOR`) and the panel follows the Qt screen with that name, so the
   two layouts are only ever matched by connector name, never by coordinates.

How the window manager treats the panel under X11 is chosen here too (`x11_window_kind`).

Pure functions on the environment and on the compositor's JSON, plus `_run`, which runs the
compositor's CLI with a short timeout and the caller's own library path. Nothing here is needed on
macOS or Windows.
"""

import json
import os
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeIs

import platformdirs

from codebuddy_overlay.log import log

PROBE_TIMEOUT_S = 1.0

type Run = Callable[[Sequence[str]], str | None]


def qt_platform_for(env: Mapping[str, str], platform: str) -> str | None:
    """`xcb` on a Linux Wayland session with XWayland, unless the user picked one Qt platform.

    A list like "wayland;xcb" is Qt's fallback chain, which distros set for the whole session
    (Omarchy, many KDE and uwsm setups): it is not a choice to stay on Wayland."""
    if platform != "linux" or not env.get("WAYLAND_DISPLAY") or not env.get("DISPLAY"):
        return None
    chosen = [name.strip() for name in env.get("QT_QPA_PLATFORM", "").split(";") if name.strip()]
    if len(chosen) == 1:  # one platform: the user means it
        return None
    if chosen and "xcb" not in chosen:  # a chain that never gives X11
        return None
    return "xcb"


type X11WindowKind = Literal["dock", "override"]


def x11_window_kind(env: Mapping[str, str]) -> X11WindowKind:
    """How the panel escapes the window manager on X11 and XWayland, so no WM tiles, moves,
    resizes or decorates it and nobody writes per-WM rules.

    `override` (override-redirect, the WM never sees the window) works on X11 and on most XWayland
    compositors (Sway, KDE, GNOME). Hyprland gives an override-redirect XWayland window no pointer
    events, so there the panel is a `dock` (_NET_WM_WINDOW_TYPE_DOCK): still never tiled, resized
    or decorated, and clickable. A dock is tied to one workspace there, so it is also pinned (see
    `pin_commands`). `BUDDY_X11_WINDOW` picks one by hand."""
    match env.get("BUDDY_X11_WINDOW", "").strip().lower():
        case "dock":
            return "dock"
        case "override":
            return "override"
        case _:
            pass
    return "dock" if env.get("HYPRLAND_INSTANCE_SIGNATURE") else "override"


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


@dataclass(frozen=True)
class Monitor:
    """One monitor as the compositor sees it.

    `name` is the connector (`DP-2`, `eDP-1`, `HEADLESS-1`), and it is the only trustworthy link
    to Qt's screens: XWayland publishes its own X11 layout, whose origins and order need not match
    the compositor's, so matching by coordinates lands the panel on the wrong monitor or outside
    every one of them. `QScreen.name()` is the same connector name under xcb and wayland."""

    name: str
    top: int = 0  # pixels reserved at its top edge: the bar
    focused: bool = False


def hyprland_monitors(monitors: object) -> list[Monitor]:
    """`hyprctl -j monitors`: each monitor has `name`, `focused` and `reserved` = [l, t, r, b]."""
    found: list[Monitor] = []
    for monitor in monitors if isinstance(monitors, list) else []:
        reserved = monitor.get("reserved") if isinstance(monitor, dict) else None
        if not isinstance(monitor, dict) or not isinstance(reserved, list) or len(reserved) != 4:
            continue
        name, top = monitor.get("name"), reserved[1]
        if isinstance(name, str) and name and _is_int(top):
            found.append(Monitor(name, max(0, top), bool(monitor.get("focused"))))
    return found


def sway_monitors(outputs: object, workspaces: object) -> list[Monitor]:
    """`swaymsg -t get_outputs` / `get_workspaces`: a visible workspace's rect is its output's rect
    minus what bars reserve, so the difference at the top is the bar."""
    screens: dict[str, dict[str, Any]] = {}
    for output in outputs if isinstance(outputs, list) else []:
        if (
            isinstance(output, dict)
            and output.get("active")
            and isinstance(output.get("rect"), dict)
        ):
            screens[str(output.get("name"))] = output
    found: list[Monitor] = []
    for workspace in workspaces if isinstance(workspaces, list) else []:
        if not isinstance(workspace, dict) or not workspace.get("visible"):
            continue
        name = str(workspace.get("output"))
        rect, output = workspace.get("rect"), screens.get(name)
        if not isinstance(rect, dict) or output is None:
            continue
        try:
            top = max(0, int(rect["y"]) - int(output["rect"]["y"]))
        except KeyError, TypeError, ValueError:
            continue
        found.append(Monitor(name, top, bool(output.get("focused"))))
    return found


def target_monitor(monitors: Sequence[Monitor], wanted: str) -> Monitor | None:
    """The monitor the panel belongs on: the one asked for by name, else the focused one, else
    the first. None when the compositor told us nothing."""
    for monitor in monitors:
        if wanted and monitor.name.lower() == wanted.strip().lower():
            return monitor
    for monitor in monitors:
        if monitor.focused:
            return monitor
    return monitors[0] if monitors else None


_LOADER_VARS = ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "LD_PRELOAD")


def child_env(env: Mapping[str, str], frozen: bool) -> dict[str, str]:
    """The environment for a program we start (the compositor's CLI, the brain).

    A packaged build (PyInstaller) points LD_LIBRARY_PATH at its own bundled libraries, where a
    system `hyprctl` or `swaymsg` can't start (an older libstdc++). PyInstaller keeps the caller's
    value as <VAR>_ORIG: give it back, or drop the variable if there was none."""
    child = dict(env)
    for var in _LOADER_VARS:
        original = child.pop(f"{var}_ORIG", None)
        if original is not None:
            child[var] = original
        elif frozen:
            child.pop(var, None)
    return child


def _run(command: Sequence[str]) -> str | None:
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_S,
            check=False,
            env=child_env(os.environ, getattr(sys, "frozen", False)),
        )
    except (OSError, subprocess.SubprocessError) as error:
        log(f"{command[0]} failed: {error}")
        return None
    if result.returncode != 0:
        # Without this line a broken probe looks like "this desktop reserves nothing".
        reason = result.stderr.strip().splitlines()[-1:] or ["no output"]
        log(f"{command[0]} failed (exit {result.returncode}): {reason[0]}")
        return None
    return result.stdout


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


def compositor_monitors(env: Mapping[str, str], run: Run = _run) -> tuple[str, list[Monitor]]:
    """The running compositor's monitors, if we know how to ask it. ("", []) when we don't."""
    if env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "hyprland", hyprland_monitors(_json(run(["hyprctl", "-j", "monitors"])))
    if env.get("SWAYSOCK"):
        outputs = _json(run(["swaymsg", "-r", "-t", "get_outputs"]))
        workspaces = _json(run(["swaymsg", "-r", "-t", "get_workspaces"]))
        return "sway", sway_monitors(outputs, workspaces)
    return "", []


@dataclass(frozen=True)
class Panel:
    """Where the panel goes: on the screen with this name (empty = Qt's primary), that far down."""

    screen: str = ""
    top: TopPlacement = TopPlacement()


def panel_placement(
    env: Mapping[str, str], configured: object, run: Run = _run
) -> tuple[Panel, str]:
    """Where to put the panel on this desktop, and a line for the log saying why.

    The screen comes from the compositor: `BUDDY_MONITOR`, else the focused monitor. Qt's primary
    screen is no help — under XWayland it can be any monitor, and here it was the vertical one
    nobody works on. The offset from the top comes from `BUDDY_TOP_OFFSET`, then `configured`
    (`configured_top_offset`, the config file), then that monitor's reserved strip, then Qt's own
    available area. `configured` has no default, so a caller can't forget the config file."""
    monitors: list[Monitor] = []
    where = ""
    if env.get("WAYLAND_DISPLAY"):
        where, monitors = compositor_monitors(env, run)
    monitor = target_monitor(monitors, env.get("BUDDY_MONITOR", ""))
    screen = monitor.name if monitor else ""
    on = f" on {screen}" if screen else ""
    for source, value in (
        ("BUDDY_TOP_OFFSET", env.get("BUDDY_TOP_OFFSET")),
        ("config", configured),
    ):
        explicit = parse_offset(value)
        if explicit is not None:
            return Panel(screen, TopPlacement(explicit=explicit)), (
                f"top offset {explicit} px ({source}){on}"
            )
    if monitor is not None:
        return Panel(screen, TopPlacement(reserved=monitor.top)), (
            f"top offset {monitor.top} px (from {where}){on}"
        )
    return Panel(), "top offset from the desktop's work area"


def pin_commands(pid: int) -> tuple[list[str], list[str]]:
    """Hyprland: show the panel on every workspace. Even a dock window is tied to the workspace it
    was mapped on, and the EWMH ways of asking otherwise (`_NET_WM_DESKTOP = 0xFFFFFFFF`,
    `_NET_WM_STATE_STICKY`) are ignored, so ask the compositor itself.

    Two spellings: Hyprland 0.5x dispatches Lua, older ones take the flat form, where `pin` is a
    toggle — which is why the caller only sends it while the panel is not pinned yet."""
    lua = f'hl.dsp.window.pin({{ action = "on", window = "pid:{pid}" }})'
    return ["hyprctl", "dispatch", lua], ["hyprctl", "dispatch", "pin", f"pid:{pid}"]


def pinned_for_pid(clients: object, pid: int) -> bool | None:
    """Whether our window is pinned, from `hyprctl clients -j`. None: it isn't mapped yet."""
    for client in clients if isinstance(clients, list) else []:
        if isinstance(client, dict) and client.get("pid") == pid:
            return bool(client.get("pinned"))
    return None


def pin_state(env: Mapping[str, str], pid: int, run: Run = _run) -> bool | None:
    if not env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return True  # nothing to do here, so nothing to wait for
    return pinned_for_pid(_json(run(["hyprctl", "clients", "-j"])), pid)


def ask_to_pin(env: Mapping[str, str], pid: int, run: Run = _run) -> None:
    if not env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return
    lua, flat = pin_commands(pid)
    if run(lua) is None:
        run(flat)
