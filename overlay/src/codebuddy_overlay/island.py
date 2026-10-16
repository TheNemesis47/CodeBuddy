"""Timers and the 3-state island machine: hidden → peek → expanded.

A port of `IslandStateMachine.swift` and `Scheduler.swift`, whose MIT origin is credited in
THIRD_PARTY.md. Timers go through a `Scheduler`, so tests run on a manual clock.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ScheduledWork:
    def __init__(self, on_cancel: Callable[[], None] = lambda: None) -> None:
        self.cancelled = False
        self._on_cancel = on_cancel

    def cancel(self) -> None:
        if not self.cancelled:
            self.cancelled = True
            self._on_cancel()


class Scheduler(Protocol):
    def schedule(self, after_s: float, action: Callable[[], None]) -> ScheduledWork: ...


@dataclass(order=True)
class _Entry:
    due: float
    seq: int
    work: ScheduledWork = field(compare=False)
    action: Callable[[], None] = field(compare=False)


class ManualScheduler:
    """Test clock: nothing runs until `advance`."""

    def __init__(self) -> None:
        self.now = 0.0
        self._entries: list[_Entry] = []
        self._seq = 0

    def schedule(self, after_s: float, action: Callable[[], None]) -> ScheduledWork:
        work = ScheduledWork()
        self._seq += 1
        self._entries.append(_Entry(self.now + after_s, self._seq, work, action))
        return work

    @property
    def pending(self) -> int:
        return sum(not e.work.cancelled for e in self._entries)

    def advance(self, seconds: float) -> None:
        target = self.now + seconds
        while due := [e for e in self._entries if not e.work.cancelled and e.due <= target]:
            entry = min(due)
            self._entries.remove(entry)
            self.now = entry.due
            entry.action()
        self.now = target
        self._entries = [e for e in self._entries if not e.work.cancelled]


class State(StrEnum):
    HIDDEN = "hidden"  # a small pill at the top of the screen
    PEEK = "peek"  # Sprout and a one-line status (or a hint's preview)
    EXPANDED = "expanded"  # the panel with the answer


class IslandStateMachine:
    def __init__(
        self, scheduler: Scheduler, expanded_to_peek_s: float = 20, peek_to_hidden_s: float = 8
    ) -> None:
        self.state = State.HIDDEN
        self.mouse_inside = False
        # An explicit answer has started but has nothing to read yet: it opens on its first token.
        self.waiting_to_open = False
        self.expanded_to_peek_s = expanded_to_peek_s
        self.peek_to_hidden_s = peek_to_hidden_s
        self.on_transition: Callable[[State, State], None] | None = None
        self._scheduler = scheduler
        self._held_open = False
        self._hide: ScheduledWork | None = None
        self._collapse: ScheduledWork | None = None

    @property
    def held_open(self) -> bool:
        """While true (an answer is streaming), timers never collapse or hide the island."""
        return self._held_open

    @held_open.setter
    def held_open(self, value: bool) -> None:
        was = self._held_open
        self._held_open = value
        if was and not value and not self.mouse_inside:
            if self.state is State.EXPANDED:
                self._schedule_collapse()
            if self.state is State.PEEK:
                self._schedule_hide()

    # Inputs

    def mouse_entered(self) -> None:
        self.mouse_inside = True
        if self.state is State.HIDDEN:
            self._cancel_timers()
            self._transition(State.PEEK)
        elif self.state is State.PEEK:
            self._cancel_hide()
        else:
            self._cancel_collapse()

    def mouse_left(self) -> None:
        self.mouse_inside = False
        if self._held_open:
            return
        if self.state is State.PEEK:
            self._schedule_hide()
        elif self.state is State.EXPANDED:
            self._schedule_collapse()

    def click(self) -> None:
        """A click opens the island from any closed state."""
        self.waiting_to_open = False
        if self.state is not State.EXPANDED:
            self._cancel_timers()
            self._transition(State.EXPANDED)

    def collapse(self) -> None:
        """The close button: fold to peek right away."""
        self.waiting_to_open = False
        if self.state is State.EXPANDED:
            self._cancel_timers()
            self._transition(State.PEEK)
            if not self.mouse_inside:
                self._schedule_hide()

    def answer_started(self, explicit: bool) -> None:
        """Any answer first peeks (Sprout thinking). An explicit one opens the panel at its first
        token (`answer_has_content`), so an empty panel never covers the code; a hint or a review
        only peeks. An open panel stays open."""
        self._cancel_timers()
        self.held_open = True
        if self.state is State.HIDDEN:
            self._transition(State.PEEK)
        self.waiting_to_open = explicit and self.state is not State.EXPANDED

    def answer_has_content(self) -> None:
        """The answer has something to read: its first token, its error, or its end."""
        if not self.waiting_to_open:
            return
        self.waiting_to_open = False
        self._cancel_timers()
        self._transition(State.EXPANDED)

    def answer_finished(self) -> None:
        self.held_open = False

    # Timers

    def _schedule_hide(self) -> None:
        self._cancel_hide()

        def hide() -> None:
            if self.state is State.PEEK and not self._held_open and not self.mouse_inside:
                self._transition(State.HIDDEN)

        self._hide = self._scheduler.schedule(self.peek_to_hidden_s, hide)

    def _schedule_collapse(self) -> None:
        self._cancel_collapse()

        def collapse() -> None:
            if self.state is State.EXPANDED and not self._held_open and not self.mouse_inside:
                self._transition(State.PEEK)
                self._schedule_hide()

        self._collapse = self._scheduler.schedule(self.expanded_to_peek_s, collapse)

    def _cancel_hide(self) -> None:
        if self._hide:
            self._hide.cancel()
        self._hide = None

    def _cancel_collapse(self) -> None:
        if self._collapse:
            self._collapse.cancel()
        self._collapse = None

    def _cancel_timers(self) -> None:
        self._cancel_hide()
        self._cancel_collapse()

    def _transition(self, new: State) -> None:
        if new is self.state:
            return
        old, self.state = self.state, new
        if self.on_transition:
            self.on_transition(old, new)
