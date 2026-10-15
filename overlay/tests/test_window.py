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
