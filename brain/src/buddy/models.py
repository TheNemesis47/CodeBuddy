"""The model interface. Routing code only sees `Model`; providers live in their own modules."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from buddy.prompting import Prompt


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Done:
    model: str
    input_tokens: int
    output_tokens: int


type ModelEvent = TextDelta | Done


class ModelError(Exception):
    """The provider failed; the message is safe to show the user."""


class Model(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def is_local(self) -> bool: ...

    def stream(self, prompt: Prompt) -> AsyncIterator[ModelEvent]:
        """Yield TextDelta chunks, then exactly one Done. Raise ModelError on failure."""
        ...
