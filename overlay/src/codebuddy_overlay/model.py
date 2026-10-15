"""Everything the window reads (as `NotchModel.swift`): messages and pointer events go in; island
state, answer and Sprout's mood come out. No Qt here, so it's tested on a manual clock."""

from collections.abc import Callable
from enum import StrEnum

from codebuddy_overlay.answers import AnswerStore, Event, Status
from codebuddy_overlay.island import IslandStateMachine, Scheduler, State
from codebuddy_overlay.markdown import preview
from codebuddy_overlay.protocol import AnswerKind, BrainMessage

PREVIEW_CHARS = 70


class Mood(StrEnum):
    IDLE = "idle"  # a seed, breathing
    THINKING = "thinking"  # sprouting while the answer streams
    HAPPY = "happy"  # fully sprouted: answer done
    WORRIED = "worried"  # something failed, or the brain is offline


class Connection(StrEnum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    OFFLINE = "offline"


class OverlayModel:
    def __init__(
        self, scheduler: Scheduler, expanded_to_peek_s: float = 20, peek_to_hidden_s: float = 8
    ) -> None:
        self.answers = AnswerStore()
        self.connection = Connection.CONNECTING
        self.on_change: Callable[[], None] | None = None
        self._machine = IslandStateMachine(scheduler, expanded_to_peek_s, peek_to_hidden_s)
        self._machine.on_transition = lambda _old, _new: self._changed()

    @property
    def state(self) -> State:
        return self._machine.state

    @property
    def peek_preview(self) -> str | None:
        """A hint's opening words while the island peeks; a click opens the whole hint."""
        current = self.answers.current
        if current is None or current.kind is not AnswerKind.HINT:
            return None
        if current.status is Status.FAILED:
            return None
        return preview(current.text, PREVIEW_CHARS) or "…"

    @property
    def mood(self) -> Mood:
        current = self.answers.current
        if current is None:
            return Mood.IDLE if self.connection is Connection.CONNECTED else Mood.WORRIED
        return {
            Status.STREAMING: Mood.THINKING,
            Status.DONE: Mood.HAPPY,
            Status.FAILED: Mood.WORRIED,
        }[current.status]

    @property
    def peek_status(self) -> str:
        current = self.answers.current
        if current is not None:
            return {Status.STREAMING: "…", Status.DONE: "✓", Status.FAILED: "!"}[current.status]
        return {Connection.CONNECTED: "", Connection.CONNECTING: "…", Connection.OFFLINE: "off"}[
            self.connection
        ]

    def handle(self, message: BrainMessage) -> None:
        event = self.answers.apply(message)
        if event is Event.STARTED_EXPLICIT:
            self._machine.answer_started(explicit=True)
        elif event is Event.STARTED_HINT:
            self._machine.answer_started(explicit=False)
        elif event is Event.FINISHED:
            self._machine.answer_finished()
        if event is not None:
            self._changed()

    def set_connection(self, status: Connection) -> None:
        self.connection = status
        self._changed()

    def pointer(self, inside: bool) -> None:
        if inside:
            self._machine.mouse_entered()
        else:
            self._machine.mouse_left()

    def click(self) -> None:
        self._machine.click()

    def close(self) -> None:
        self._machine.collapse()

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()
