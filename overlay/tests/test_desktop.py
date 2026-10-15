"""Placing the panel on Linux desktops that hide their bar from Qt (Wayland + layer-shell bars)."""

import json
from collections.abc import Sequence

import pytest
from PySide6.QtCore import Qt

from codebuddy_overlay.desktop import (
    TopPlacement,
    child_env,
    hyprland_tops,
    parse_offset,
    qt_platform_for,
    sway_tops,
    top_for_screen,
    top_placement,
    x11_window_kind,
)
from codebuddy_overlay.window import window_flags

# `hyprctl -j monitors` on Omarchy (Hyprland 0.56.2): a 30 px bar on the primary monitor, and a
# rotated second monitor with none (docs: the Wayland report, 2026-10-15).
HYPRLAND_MONITORS = [
    {
        "id": 0,
        "name": "DP-2",
        "x": 0,
        "y": 0,
        "width": 2560,
        "height": 1440,
        "reserved": [0, 30, 0, 0],
    },
    {
        "id": 1,
        "name": "DP-3",
        "x": 2560,
        "y": 0,
        "width": 1920,
        "height": 1080,
        "reserved": [0, 0, 0, 0],
    },
]
SWAY_OUTPUTS = [
    {"name": "HEADLESS-1", "active": True, "rect": {"x": 0, "y": 0, "width": 1920, "height": 1080}},
    {"name": "HDMI-A-1", "active": False, "rect": {"x": 0, "y": 0, "width": 0, "height": 0}},
]
SWAY_WORKSPACES = [
    {
        "name": "1",
        "visible": True,
        "output": "HEADLESS-1",
        "rect": {"x": 0, "y": 22, "width": 1920, "height": 1058},
    },
    {
        "name": "2",
        "visible": False,
        "output": "HEADLESS-1",
        "rect": {"x": 0, "y": 0, "width": 1920, "height": 1080},
    },
]


class FakeCompositor:
    """Answers the compositor CLIs the way Hyprland and Sway do; records what was asked."""

    def __init__(self, answers: dict[str, object | None]) -> None:
        self.answers = answers
        self.asked: list[list[str]] = []

    def __call__(self, command: Sequence[str]) -> str | None:
        self.asked.append(list(command))
        answer = self.answers.get(command[-1])
        return None if answer is None else json.dumps(answer)


WAYLAND = {"WAYLAND_DISPLAY": "wayland-1", "DISPLAY": ":0"}
HYPRLAND = {**WAYLAND, "HYPRLAND_INSTANCE_SIGNATURE": "abc"}
SWAY = {**WAYLAND, "SWAYSOCK": "/run/user/1000/sway-ipc.sock"}


@pytest.mark.parametrize(
    ("env", "platform", "expected"),
    [
        (WAYLAND, "linux", "xcb"),
        ({"WAYLAND_DISPLAY": "wayland-1"}, "linux", None),  # no XWayland: leave Qt alone
        ({**WAYLAND, "QT_QPA_PLATFORM": "wayland"}, "linux", None),  # the user chose
        ({**WAYLAND, "QT_QPA_PLATFORM": "xcb"}, "linux", None),  # already X11
        ({**WAYLAND, "QT_QPA_PLATFORM": ""}, "linux", "xcb"),
        # Qt's fallback chain, set session-wide by distros (Omarchy: "wayland;xcb")
        ({**WAYLAND, "QT_QPA_PLATFORM": "wayland;xcb"}, "linux", "xcb"),
        ({**WAYLAND, "QT_QPA_PLATFORM": "wayland;xcb;offscreen"}, "linux", "xcb"),
        ({**WAYLAND, "QT_QPA_PLATFORM": " wayland ; xcb "}, "linux", "xcb"),
        ({**WAYLAND, "QT_QPA_PLATFORM": "wayland;offscreen"}, "linux", None),  # never X11
        ({"WAYLAND_DISPLAY": "wayland-1", "QT_QPA_PLATFORM": "wayland;xcb"}, "linux", None),
        ({"DISPLAY": ":0"}, "linux", None),  # plain X11 already is xcb
        (WAYLAND, "win32", None),
        (WAYLAND, "darwin", None),
    ],
)
def test_wayland_sessions_use_xwayland_unless_the_user_chose(env, platform, expected) -> None:
    assert qt_platform_for(env, platform) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("30", 30),
        (" 42 ", 42),
        (0, 0),
        (12, 12),
        ("auto", None),
        ("", None),
        ("-3", None),
        (-1, None),
        (None, None),
        (True, None),
        ("3.5", None),
    ],
)
def test_offsets_are_non_negative_pixel_counts(value, expected) -> None:
    assert parse_offset(value) == expected


def test_the_panel_goes_below_whichever_is_lower_the_work_area_or_the_bar() -> None:
    assert TopPlacement().y(screen_y=0, available_y=0) == 0
    assert TopPlacement(reserved=30).y(screen_y=0, available_y=0) == 30  # Hyprland + XWayland
    assert TopPlacement(reserved=30).y(screen_y=0, available_y=32) == 32  # Qt knew: no double
    assert TopPlacement(reserved=30).y(screen_y=100, available_y=100) == 130  # lower screen


def test_an_explicit_offset_is_measured_from_the_screen_top_and_wins() -> None:
    assert TopPlacement(explicit=42, reserved=30).y(screen_y=0, available_y=32) == 42
    assert TopPlacement(explicit=0).y(screen_y=0, available_y=32) == 0


def test_hyprland_reserved_top_per_monitor() -> None:
    assert hyprland_tops(HYPRLAND_MONITORS) == {(0, 0): 30, (2560, 0): 0}


@pytest.mark.parametrize(
    "monitors",
    [
        None,
        "nope",
        [{"x": 0}],
        [{"x": 0, "y": 0, "reserved": [0, 30]}],
        [{"x": "0", "y": 0, "reserved": [0, 30, 0, 0]}],
    ],
)
def test_odd_hyprland_output_means_no_reserved_strip(monitors) -> None:
    assert hyprland_tops(monitors) == {}


def test_sway_reserved_top_is_the_visible_workspace_below_its_output() -> None:
    assert sway_tops(SWAY_OUTPUTS, SWAY_WORKSPACES) == {(0, 0): 22}
    assert sway_tops(None, SWAY_WORKSPACES) == {}
    assert sway_tops(SWAY_OUTPUTS, [{"visible": True, "output": "HEADLESS-1"}]) == {}


def test_the_strip_is_the_screens_own_else_the_largest() -> None:
    tops = {(0, 0): 30, (2560, 0): 0}
    assert top_for_screen(tops, 0, 0) == 30
    assert top_for_screen(tops, 2560, 0) == 0
    assert top_for_screen(tops, 0, 1440) == 30  # Qt's layout differs from the compositor's
    assert top_for_screen({}, 0, 0) == 0


def test_on_hyprland_the_bar_comes_from_hyprctl() -> None:
    run = FakeCompositor({"monitors": HYPRLAND_MONITORS})
    placement, source = top_placement(HYPRLAND, 0, 0, None, run=run)
    assert placement == TopPlacement(reserved=30)
    assert run.asked == [["hyprctl", "-j", "monitors"]]
    assert "hyprland" in source


def test_on_sway_the_bar_comes_from_swaymsg() -> None:
    run = FakeCompositor({"get_outputs": SWAY_OUTPUTS, "get_workspaces": SWAY_WORKSPACES})
    placement, _ = top_placement(SWAY, 0, 0, None, run=run)
    assert placement == TopPlacement(reserved=22)


def test_the_user_wins_over_the_config_file_and_the_compositor() -> None:
    # 0.1.1 shipped with app.py not passing the config file: `configured` has no default now.
    run = FakeCompositor({"monitors": HYPRLAND_MONITORS})
    placement, source = top_placement({**HYPRLAND, "BUDDY_TOP_OFFSET": "44"}, 0, 0, "12", run=run)
    assert placement == TopPlacement(explicit=44) and "BUDDY_TOP_OFFSET" in source
    placement, source = top_placement(HYPRLAND, 0, 0, 12, run=run)
    assert placement == TopPlacement(explicit=12) and "config" in source
    assert run.asked == []  # an explicit offset never runs the compositor's CLI
    placement, _ = top_placement({**HYPRLAND, "BUDDY_TOP_OFFSET": "auto"}, 0, 0, "auto", run=run)
    assert placement == TopPlacement(reserved=30)


def test_a_compositor_that_fails_to_answer_leaves_the_work_area() -> None:
    placement, _ = top_placement(HYPRLAND, 0, 0, None, run=FakeCompositor({}))
    assert placement == TopPlacement(reserved=0)


def test_off_wayland_the_compositor_is_never_asked() -> None:
    run = FakeCompositor({"monitors": HYPRLAND_MONITORS})
    placement, _ = top_placement(
        {"DISPLAY": ":0", "HYPRLAND_INSTANCE_SIGNATURE": "x"}, 0, 0, None, run=run
    )
    assert placement == TopPlacement() and run.asked == []


def test_on_x11_and_xwayland_the_window_manager_is_bypassed() -> None:
    assert window_flags("xcb") & Qt.WindowType.X11BypassWindowManagerHint
    for platform in ("offscreen", "windows", "cocoa", "wayland"):
        assert not window_flags(platform) & Qt.WindowType.X11BypassWindowManagerHint


def test_a_dock_is_never_override_redirect() -> None:
    """Hyprland: an override-redirect XWayland window gets no pointer events (0.1.1 report)."""
    assert not window_flags("xcb", "dock") & Qt.WindowType.X11BypassWindowManagerHint
    assert window_flags("xcb", "dock") & Qt.WindowType.WindowStaysOnTopHint


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, "override"),
        (SWAY, "override"),
        ({"DISPLAY": ":0"}, "override"),
        (HYPRLAND, "dock"),
        ({**HYPRLAND, "BUDDY_X11_WINDOW": "override"}, "override"),
        ({**SWAY, "BUDDY_X11_WINDOW": " Dock "}, "dock"),
        ({**HYPRLAND, "BUDDY_X11_WINDOW": "boh"}, "dock"),
    ],
)
def test_hyprland_gets_a_dock_everyone_else_override_redirect(env, expected) -> None:
    assert x11_window_kind(env) == expected


def test_programs_we_start_get_the_callers_library_path_back() -> None:
    """PyInstaller points LD_LIBRARY_PATH into the bundle, where system hyprctl can't start."""
    bundle = {
        "LD_LIBRARY_PATH": "/opt/CodeBuddy/overlay/_internal",
        "LD_LIBRARY_PATH_ORIG": "/usr/local/lib",
        "PATH": "/usr/bin",
    }
    assert child_env(bundle, frozen=True) == {
        "LD_LIBRARY_PATH": "/usr/local/lib",
        "PATH": "/usr/bin",
    }
    assert child_env({"LD_LIBRARY_PATH": "/opt/b/_internal"}, frozen=True) == {}  # caller had none
    assert child_env({"LD_LIBRARY_PATH": "/mine"}, frozen=False) == {"LD_LIBRARY_PATH": "/mine"}


def test_a_failing_probe_says_why_and_gets_the_callers_environment(monkeypatch, capsys) -> None:
    import sys

    from codebuddy_overlay import desktop

    fail = [sys.executable, "-c", "import sys; sys.stderr.write('libstdc++ too old'); sys.exit(1)"]
    assert desktop._run(fail) is None
    assert "failed (exit 1): libstdc++ too old" in capsys.readouterr().err

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_PRELOAD_ORIG", "")
    monkeypatch.setenv("LD_PRELOAD", "/opt/CodeBuddy/_internal/libfake.so")
    show = [sys.executable, "-c", "import os; print(repr(os.environ.get('LD_PRELOAD')))"]
    assert desktop._run(show) == "''\n"  # the caller's (empty) value, not the bundle's


def test_the_settings_file_can_set_the_offset(tmp_path) -> None:
    from codebuddy_overlay.desktop import configured_top_offset

    path = tmp_path / "config.toml"
    env = {"BUDDY_CONFIG": str(path)}
    assert configured_top_offset(env) is None  # no file
    path.write_text("[overlay]\ntop_offset = 34\n", encoding="utf-8")
    assert configured_top_offset(env) == 34
    placement, source = top_placement(env, 0, 0, configured_top_offset(env))  # see test_window
    assert placement == TopPlacement(explicit=34) and "config" in source
    path.write_text('[overlay]\ntop_offset = "auto"\n', encoding="utf-8")
    assert parse_offset(configured_top_offset(env)) is None
    path.write_text("[overlay\n", encoding="utf-8")
    assert configured_top_offset(env) is None  # broken file: the brain says so, not the panel
