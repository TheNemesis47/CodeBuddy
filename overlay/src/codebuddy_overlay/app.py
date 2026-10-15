"""`codebuddy-overlay`: connect to the brain, or play `--demo`; `--snapshots DIR` saves PNGs."""

import argparse
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from codebuddy_overlay import demo
from codebuddy_overlay.answers import Status
from codebuddy_overlay.client import ConnectionLoop, Endpoint, start_in_background
from codebuddy_overlay.island import ManualScheduler, ScheduledWork
from codebuddy_overlay.model import Connection, OverlayModel
from codebuddy_overlay.protocol import AnswerEnd, BrainMessage, Error
from codebuddy_overlay.window import OverlayWindow

SNAPSHOT_TIME = 1.0  # Sprout's clock in snapshots: eyes open, no blink


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] overlay: {message}", file=sys.stderr, flush=True)


class QtScheduler:
    """Real time on the Qt event loop."""

    def schedule(self, after_s: float, action: Callable[[], None]) -> ScheduledWork:
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(action)
        timer.start(int(after_s * 1000))
        work = ScheduledWork(on_cancel=timer.stop)
        work.timer = timer  # type: ignore[attr-defined]  # keep it alive until it fires
        return work


def save(window: OverlayWindow, path: Path) -> None:
    QApplication.processEvents()
    window.sprout.frozen_at = SNAPSHOT_TIME
    window.grab().save(str(path))
    window.sprout.frozen_at = None
    log(f"saved {path}")


def apply_step(model: OverlayModel, step: demo.Step) -> None:
    match step:
        case demo.Hover(inside=inside):
            model.pointer(inside)
        case demo.Click():
            model.click()
        case message:
            model.handle(message)


def demo_snapshots(app: QApplication, out: Path) -> int:
    """Play the demo on a manual clock and save one PNG per state, like the notch's
    `--demo --snapshots`: deterministic, no real pointer, no waiting."""
    clock = ManualScheduler()
    model = OverlayModel(clock, expanded_to_peek_s=6, peek_to_hidden_s=3)
    model.set_connection(Connection.CONNECTED)
    window = OverlayWindow(model)
    window.show()
    for at, step in demo.steps():
        clock.schedule(at, lambda step=step: apply_step(model, step))
    shots = {
        0.5: "1-hidden",
        2.0: "2-peek",
        6.0: "3-expanded-streaming",
        9.0: "4-expanded-done",
        14.5: "5-peek-after",
        17.5: "6-hidden-after",
        23.5: "7-hint-peek",
        24.1: "8-hint-open",
    }
    out.mkdir(parents=True, exist_ok=True)
    now = 0.0
    for at, name in sorted(shots.items()):
        clock.advance(at - now)
        now = at
        save(window, out / f"demo-{name}.png")
        log(f"{name}: state {model.state} mood {model.mood}")
    window.close()
    app.quit()
    return 0


def run_demo(model: OverlayModel) -> None:
    model.set_connection(Connection.CONNECTED)
    for at, step in demo.steps():
        QTimer.singleShot(int(at * 1000), lambda step=step: apply_step(model, step))


def run_brain(
    app: QApplication, model: OverlayModel, window: OverlayWindow, shots: Path | None
) -> None:
    def on_message(message: BrainMessage) -> None:
        model.handle(message)
        current = model.answers.current
        if isinstance(message, AnswerEnd | Error) and current and current.id == message.id:
            if current.status is Status.DONE:
                log(
                    f"answer_end id={current.id} model={current.model} "
                    f"first_token_ms={current.first_token_ms} total_ms={current.total_ms}"
                )
            else:
                log(f"answer failed id={current.id}: {current.failure}")
            if shots is not None:
                shots.mkdir(parents=True, exist_ok=True)
                target = shots / f"answer-{current.id}.png"
                QTimer.singleShot(300, lambda: save(window, target))

    def on_status(status: Connection) -> None:
        if status is not model.connection:
            log(f"brain {status}")
        model.set_connection(status)

    bridge = _Bridge(on_message, on_status)
    loop = ConnectionLoop(Endpoint.from_env(), bridge.message, bridge.status)
    start_in_background(loop)
    app.aboutToQuit.connect(loop.stop)


class _Bridge:
    """Hands messages from the network thread to the Qt thread (queued signal)."""

    def __init__(
        self, on_message: Callable[[BrainMessage], None], on_status: Callable[[Connection], None]
    ) -> None:
        from PySide6.QtCore import QObject, Signal

        class Relay(QObject):
            message_signal = Signal(object)
            status_signal = Signal(object)

        self._relay = Relay()
        self._relay.message_signal.connect(on_message)
        self._relay.status_signal.connect(on_status)

    def message(self, message: BrainMessage) -> None:
        self._relay.message_signal.emit(message)

    def status(self, status: Connection) -> None:
        self._relay.status_signal.emit(status)


def start_brain(command: str) -> subprocess.Popen[bytes]:
    """The packaged launchers start the brain with the overlay (`--start-brain "…/buddy serve"`),
    and quitting the overlay stops it. With no console window on Windows."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if sys.platform == "win32":  # non-POSIX split keeps the quotes around quoted paths
        args = [part.strip('"') for part in shlex.split(command, posix=False)]
    else:
        args = shlex.split(command)
    log(f"starting the brain: {args[0]}")
    return subprocess.Popen(args, creationflags=flags)


def stop_brain(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codebuddy-overlay", description="CodeBuddy overlay")
    parser.add_argument("--demo", action="store_true", help="play every state, no brain needed")
    parser.add_argument("--snapshots", type=Path, metavar="DIR", help="save PNGs into DIR")
    parser.add_argument(
        "--quit-after", type=float, metavar="S", help="exit after S seconds (tests)"
    )
    parser.add_argument(
        "--start-brain",
        metavar="COMMAND",
        help="start the brain with this command; stop it on exit",
    )
    args = parser.parse_args(argv)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    assert isinstance(app, QApplication)
    app.setQuitOnLastWindowClosed(False)
    if args.demo and args.snapshots:
        return demo_snapshots(app, args.snapshots)

    brain = start_brain(args.start_brain) if args.start_brain and not args.demo else None
    if brain is not None:
        app.aboutToQuit.connect(lambda: stop_brain(brain))
    model = OverlayModel(QtScheduler())
    window = OverlayWindow(model)
    window.show()
    if args.demo:
        run_demo(model)
    else:
        run_brain(app, model, window, args.snapshots)
    if args.quit_after:
        QTimer.singleShot(int(args.quit_after * 1000), app.quit)
    log(f"started ({'demo' if args.demo else Endpoint.from_env().url}) at {time.strftime('%X')}")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
