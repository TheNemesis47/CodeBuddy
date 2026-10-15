"""A canned model for end-to-end runs without Claude (`buddy serve --stub TEXT`): CI, demos."""

import asyncio
from collections.abc import AsyncIterator

from buddy.models import Done, ModelEvent, TextDelta
from buddy.prompting import Prompt

CHUNK_CHARS = 12
CHUNK_DELAY_S = 0.02


class StubModel:
    is_local = False

    def __init__(self, text: str, *, delay_s: float = CHUNK_DELAY_S) -> None:
        self.name = "stub"
        self.text = text
        self._delay_s = delay_s

    async def stream(self, prompt: Prompt) -> AsyncIterator[ModelEvent]:
        for start in range(0, len(self.text), CHUNK_CHARS):
            await asyncio.sleep(self._delay_s)
            yield TextDelta(self.text[start : start + CHUNK_CHARS])
        yield Done("stub", prompt.estimated_tokens(), len(self.text) // 4)
