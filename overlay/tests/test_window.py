"""The Qt side, on a real QApplication (offscreen, or xcb under Xvfb on Linux CI)."""

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from codebuddy_overlay import app as overlay_app
from codebuddy_overlay.geometry import layout, top_center
from codebuddy_overlay.island import ManualScheduler, State
from codebuddy_overlay.model import Connection, OverlayModel
from codebuddy_overlay.protocol import AnswerDelta, AnswerEnd, AnswerKind, AnswerStart
from codebuddy_overlay.window import OverlayWindow


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    existing = QApplication.instance()
    return existing if isinstance(existing, QApplication) else QApplication(sys.argv[:1])


@pytest.fixture
def window(qapp: QApplication):
    clock = ManualScheduler()
    model = OverlayModel(clock)
    model.set_connection(Connection.CONNECTED)
    w = OverlayWindow(model)
    w.show()
    qapp.processEvents()
    yield w, model, clock
    w.close()


def test_window_is_frameless_on_top_and_never_takes_focus(window) -> None:
    from PySide6.QtCore import Qt

    w, _, _ = window
    flags = w.windowFlags()
    for flag in (
        Qt.WindowType.FramelessWindowHint,
        Qt.WindowType.WindowStaysOnTopHint,
        Qt.WindowType.WindowDoesNotAcceptFocus,
    ):
        assert flags & flag


def test_size_follows_the_state_and_sits_at_the_top_centre(window, qapp: QApplication) -> None:
    w, model, _ = window
    area = qapp.primaryScreen().availableGeometry()
    for state, action in [
        (State.HIDDEN, lambda: None),
        (State.PEEK, lambda: model.pointer(True)),
        (State.EXPANDED, model.click),
    ]:
        action()
        qapp.processEvents()
        size = layout(state)
        assert (w.width(), w.height()) == (size.width, size.height)
        assert (w.x(), w.y()) == top_center(area.x(), area.y(), area.width(), size)


def test_sprout_is_visible_in_every_state(window, qapp: QApplication) -> None:
    w, model, _ = window
    for action in (lambda: None, lambda: model.pointer(True), model.click, model.close):
        action()
        qapp.processEvents()
        assert w.sprout.isVisible(), model.state


def test_a_streamed_answer_fills_the_panel_and_the_footer(window, qapp: QApplication) -> None:
    w, model, _ = window
    model.handle(AnswerStart("a", AnswerKind.QUESTION, "perché?"))
    model.handle(AnswerDelta("a", "Il file **non** viene chiuso."))
    qapp.processEvents()
    assert w.body.isVisible() and "non viene chiuso" in w.body.toPlainText()
    assert w.title.text() == "perché?" and w.kind.text() == "DOMANDA"
    model.handle(AnswerEnd("a", "claude-sonnet-5-5", 1500, 6000))
    qapp.processEvents()
    assert w.footer.text() == "claude-sonnet-5-5 · primo token 1500 ms · totale 6000 ms"


def test_a_hint_peeks_with_its_preview_and_a_click_opens_it(window, qapp: QApplication) -> None:
    w, model, _ = window
    model.handle(AnswerStart("h", AnswerKind.HINT, "load.py:6"))
    model.handle(AnswerDelta("h", "Guarda la riga 6: chi chiude il file?"))
    qapp.processEvents()
    assert model.state is State.PEEK
    assert w.preview.isVisible() and w.preview.text() == "Guarda la riga 6: chi chiude il file?"
    assert w.height() == layout(State.PEEK, preview=True).height
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(10, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(w, press)
    qapp.processEvents()
    assert model.state is State.EXPANDED
    w.close_button.click()
    assert model.state is State.PEEK


def test_offline_brain_shows_off_and_a_worried_sprout(window, qapp: QApplication) -> None:
    w, model, _ = window
    model.set_connection(Connection.OFFLINE)
    model.pointer(True)
    qapp.processEvents()
    assert w.status.text() == "off"
    assert w.sprout.mood.value == "worried"


def test_demo_snapshots_save_one_png_per_state(qapp: QApplication, tmp_path: Path) -> None:
    assert overlay_app.demo_snapshots(qapp, tmp_path) == 0
    names = sorted(p.name for p in tmp_path.glob("*.png"))
    assert names == [
        "demo-1-hidden.png",
        "demo-2-peek.png",
        "demo-2b-thinking.png",
        "demo-3-expanded-streaming.png",
        "demo-4-expanded-done.png",
        "demo-5-peek-after.png",
        "demo-6-hidden-after.png",
        "demo-7-hint-peek.png",
        "demo-8-hint-open.png",
    ]
    assert all(p.stat().st_size > 200 for p in tmp_path.glob("*.png"))


def test_right_click_offers_quit(window) -> None:
    w, _, _ = window
    actions = [a.text() for a in w.quit_menu().actions()]
    assert actions == ["Esci da CodeBuddy"]


def test_start_brain_runs_the_command_and_stop_ends_it() -> None:
    import shlex

    command = shlex.join([sys.executable, "-c", "import time; time.sleep(30)"])
    if sys.platform == "win32":
        command = f'"{sys.executable}" -c "import time; time.sleep(30)"'
    process = overlay_app.start_brain(command)
    assert process.poll() is None
    overlay_app.stop_brain(process)
    assert process.poll() is not None


def test_main_starts_the_brain_and_stops_it_on_quit(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through `main()` as the launchers call it: --start-brain, then quit after a moment."""
    started: list[str] = []
    stopped: list[object] = []
    monkeypatch.setenv("BUDDY_HOME", str(tmp_path))  # no token: the client just stays offline
    monkeypatch.setenv("BUDDY_PORT", "1")
    monkeypatch.setattr(overlay_app, "start_brain", lambda cmd: started.append(cmd) or "proc")
    monkeypatch.setattr(overlay_app, "stop_brain", stopped.append)
    assert overlay_app.main(["--start-brain", "buddy serve", "--quit-after", "0.2"]) == 0
    assert started == ["buddy serve"]
    assert stopped == ["proc"]


def test_code_gets_a_real_monospace_font(window, qapp: QApplication) -> None:
    w, model, _ = window
    model.handle(AnswerStart("a", AnswerKind.QUESTION, "q"))
    model.handle(AnswerDelta("a", "usa `with`:\n\n```python\nwith open(p) as f:\n    pass\n```\n"))
    qapp.processEvents()
    document = w.body.document()
    code = []
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.text().strip() in ("with", "with open(p) as f:"):
                code.append(fragment.charFormat().fontFamilies())
            iterator += 1
        block = block.next()
    assert code and all(families and families[0] == "Menlo" for families in code)


def test_a_bar_the_desktop_hides_pushes_every_state_down(qapp: QApplication) -> None:
    """Hyprland + XWayland: Qt sees the whole screen free, the compositor reserves 30 px."""
    from codebuddy_overlay.desktop import Panel, TopPlacement

    model = OverlayModel(ManualScheduler())
    model.set_connection(Connection.CONNECTED)
    w = OverlayWindow(model, Panel(top=TopPlacement(reserved=30)))
    w.show()
    screen = qapp.primaryScreen()
    area, top = (
        screen.availableGeometry(),
        max(screen.availableGeometry().y(), screen.geometry().y() + 30),
    )
    try:
        for state, action in [
            (State.HIDDEN, lambda: None),
            (State.PEEK, lambda: model.pointer(True)),
            (State.EXPANDED, model.click),
        ]:
            action()
            qapp.processEvents()
            size = layout(state)
            assert (w.x(), w.y()) == top_center(area.x(), top, area.width(), size)
            assert w.y() >= screen.geometry().y() + 30
    finally:
        w.close()


def test_the_app_places_the_panel_with_the_config_file(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through `app.placement`, the call the app makes: 0.1.1 read the file in tests only."""
    from codebuddy_overlay.desktop import TopPlacement

    config = tmp_path / "config.toml"
    config.write_text("[overlay]\ntop_offset = 64\n", encoding="utf-8")
    monkeypatch.setenv("BUDDY_CONFIG", str(config))
    monkeypatch.delenv("BUDDY_TOP_OFFSET", raising=False)
    for variable in ("HYPRLAND_INSTANCE_SIGNATURE", "SWAYSOCK", "WAYLAND_DISPLAY"):
        monkeypatch.delenv(variable, raising=False)  # never ask the machine running the tests
    assert overlay_app.placement(qapp).top == TopPlacement(explicit=64)
    monkeypatch.setenv("BUDDY_TOP_OFFSET", "12")
    assert overlay_app.placement(qapp).top == TopPlacement(explicit=12)


def test_the_panel_follows_the_screen_it_was_given_by_name(qapp: QApplication) -> None:
    """XWayland's X11 layout need not match the compositor's, so the monitor is matched by its
    connector name; an unknown one falls back to Qt's primary (0.1.1 report, bug 7)."""
    from codebuddy_overlay.desktop import Panel

    model = OverlayModel(ManualScheduler())
    wanted = qapp.screens()[-1]
    for panel, expected in (
        (Panel(screen=wanted.name()), wanted),
        (Panel(screen="DP-404"), qapp.primaryScreen()),
        (Panel(), qapp.primaryScreen()),
    ):
        w = OverlayWindow(model, panel)
        try:
            assert w._screen() is expected
        finally:
            w.close()


def test_a_dock_panel_is_a_dock_before_it_shows(qapp: QApplication) -> None:
    """Hyprland: `_NET_WM_WINDOW_TYPE_DOCK` instead of override-redirect. Checked on a real X
    server where there is one (Linux CI: xcb under Xvfb); elsewhere no X11 call is made."""
    from PySide6.QtCore import Qt

    from codebuddy_overlay import x11

    model = OverlayModel(ManualScheduler())
    w = OverlayWindow(model, x11_kind="dock")
    try:
        assert not w.windowFlags() & Qt.WindowType.X11BypassWindowManagerHint
        if qapp.platformName() == "xcb":
            assert x11.window_types(int(w.winId())) == [x11.DOCK]
            w.show()
            qapp.processEvents()
            assert x11.window_types(int(w.winId())) == [x11.DOCK]  # Qt kept it on map
    finally:
        w.close()
