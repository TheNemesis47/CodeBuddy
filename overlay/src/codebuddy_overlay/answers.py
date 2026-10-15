"""The answer on screen (as `AnswerStore.swift`). One at a time: a new answer_start replaces the
old one, and deltas for any other id are dropped."""

from dataclasses import dataclass
from enum import StrEnum

from codebuddy_overlay.protocol import (
    AnswerDelta,
    AnswerEnd,
    AnswerKind,
    AnswerStart,
    BrainMessage,
    Error,
)


class Status(StrEnum):
    STREAMING = "streaming"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Answer:
    id: str
    kind: AnswerKind
    title: str
    text: str = ""
    status: Status = Status.STREAMING
    model: str = ""
    first_token_ms: int | None = None
    total_ms: int = 0
    failure: str = ""


class Event(StrEnum):
    STARTED_EXPLICIT = "started_explicit"
    STARTED_HINT = "started_hint"
    UPDATED = "updated"
    FINISHED = "finished"


class AnswerStore:
    def __init__(self) -> None:
        self.current: Answer | None = None
        self.notice: str | None = None  # a brain-level problem not tied to an answer

    def _streaming(self, id: str) -> Answer | None:
        current = self.current
        return (
            current if current and current.id == id and current.status is Status.STREAMING else None
        )

    def apply(self, message: BrainMessage) -> Event | None:
        match message:
            case AnswerStart(id=id, kind=kind, title=title):
                self.current = Answer(id, kind, title)
                self.notice = None
                return Event.STARTED_EXPLICIT if kind.is_explicit else Event.STARTED_HINT
            case AnswerDelta(id=id, text=text):
                if answer := self._streaming(id):
                    answer.text += text
                    return Event.UPDATED
                return None
            case AnswerEnd(id=id, model=model, first_token_ms=first, total_ms=total):
                if answer := self._streaming(id):
                    answer.status = Status.DONE
                    answer.model, answer.first_token_ms, answer.total_ms = model, first, total
                    return Event.FINISHED
                return None
            case Error(id=None, message=text):
                self.notice = text
                return Event.UPDATED
            case Error(id=str(id), message=text):
                if answer := self._streaming(id):
                    answer.status = Status.FAILED
                    answer.failure = text
                    return Event.FINISHED
                return None
            case _:
                return None
