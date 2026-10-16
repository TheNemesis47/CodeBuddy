"""Run one answer: stream a model and emit protocol messages (answer_start/delta/end or error)."""

import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from buddy.models import Done, Model, ModelError, TextDelta
from buddy.prompting import Prompt

type Message = dict[str, Any]
type Emit = Callable[[Message], Awaitable[None]]
type AnswerKind = Literal["question", "theory", "hint", "review"]

TITLE_CHARS = 80


async def run_answer(
    model: Model, prompt: Prompt, *, id: str, kind: AnswerKind, title: str, emit: Emit
) -> Message:
    """Emit the whole answer and return the final message (answer_end or error)."""
    started = time.monotonic()
    first_token_ms: int | None = None
    done: Done | None = None
    await emit(
        {"v": 0, "type": "answer_start", "id": id, "kind": kind, "title": title[:TITLE_CHARS]}
    )
    try:
        async for event in model.stream(prompt):
            if isinstance(event, TextDelta) and event.text:
                if first_token_ms is None:
                    first_token_ms = _ms_since(started)
                await emit({"v": 0, "type": "answer_delta", "id": id, "text": event.text})
            elif isinstance(event, Done):
                done = event
    except ModelError as error:
        final: Message = {"v": 0, "type": "error", "id": id, "message": str(error)}
        await emit(final)
        return final
    final = {
        "v": 0,
        "type": "answer_end",
        "id": id,
        "model": done.model if done else model.name,
        "first_token_ms": first_token_ms,
        "total_ms": _ms_since(started),
        "tokens": {
            "in": done.input_tokens if done else prompt.estimated_tokens(),
            "out": done.output_tokens if done else 0,
        },
    }
    await emit(final)
    return final


def _ms_since(start: float) -> int:
    return round((time.monotonic() - start) * 1000)
