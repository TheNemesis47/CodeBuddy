"""brain → overlay messages from protocol v0 (`protocol/schemas`). Anything else decodes to
`Ignored`, so a newer brain never crashes an older overlay (as `BrainMessage.swift`)."""

import json
from dataclasses import dataclass
from enum import StrEnum

PROTOCOL_VERSION = 0
CLIENT = "codebuddy-overlay/0.1.2"


class AnswerKind(StrEnum):
    QUESTION = "question"
    THEORY = "theory"
    HINT = "hint"
    REVIEW = "review"

    @property
    def is_explicit(self) -> bool:
        """Explicit requests open the panel; a hint and the review after a save only peek."""
        return self in (AnswerKind.QUESTION, AnswerKind.THEORY)


@dataclass(frozen=True)
class Welcome:
    brain: str


@dataclass(frozen=True)
class AnswerStart:
    id: str
    kind: AnswerKind
    title: str


@dataclass(frozen=True)
class AnswerDelta:
    id: str
    text: str


@dataclass(frozen=True)
class AnswerEnd:
    id: str
    model: str
    first_token_ms: int | None
    total_ms: int


@dataclass(frozen=True)
class Error:
    id: str | None
    message: str


@dataclass(frozen=True)
class Ignored:
    pass


type BrainMessage = Welcome | AnswerStart | AnswerDelta | AnswerEnd | Error | Ignored


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def decode(raw: str | bytes) -> BrainMessage:
    try:
        obj = json.loads(raw)
    except ValueError:
        return Ignored()
    if not isinstance(obj, dict) or _int(obj.get("v")) != PROTOCOL_VERSION:
        return Ignored()
    kind = obj.get("type")
    id = obj.get("id") if isinstance(obj.get("id"), str) else None
    match kind:
        case "welcome":
            return Welcome(str(obj.get("brain", "?")))
        case "answer_start" if id is not None:
            try:
                answer_kind = AnswerKind(obj.get("kind"))
            except ValueError:
                return Ignored()
            title = obj.get("title")
            return AnswerStart(id, answer_kind, title if isinstance(title, str) else "")
        case "answer_delta" if id is not None and isinstance(obj.get("text"), str):
            return AnswerDelta(id, obj["text"])
        case "answer_end" if id is not None:
            model = obj.get("model")
            return AnswerEnd(
                id,
                model if isinstance(model, str) else "",
                _int(obj.get("first_token_ms")),
                _int(obj.get("total_ms")) or 0,
            )
        case "error":
            message = obj.get("message")
            return Error(id, message if isinstance(message, str) else "error")
        case _:
            return Ignored()


def hello(token: str) -> str:
    """The first frame: protocol `hello` as a notch-role client (a text frame)."""
    return json.dumps(
        {"v": PROTOCOL_VERSION, "type": "hello", "role": "notch", "token": token, "client": CLIENT},
        sort_keys=True,
    )
