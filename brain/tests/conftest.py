from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from buddy.models import Done, ModelError, ModelEvent, TextDelta
from buddy.prompting import Prompt

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).resolve().parents[2]


class FakeModel:
    """Records every prompt it gets and streams canned chunks. No network."""

    def __init__(
        self,
        chunks: tuple[str, ...] = ("Ciao ", "mondo"),
        *,
        fail: str | None = None,
        is_local: bool = False,
    ) -> None:
        self.name = "fake"
        self.is_local = is_local
        self.chunks = chunks
        self.fail = fail
        self.prompts: list[Prompt] = []

    async def stream(self, prompt: Prompt) -> AsyncIterator[ModelEvent]:
        self.prompts.append(prompt)
        for chunk in self.chunks:
            yield TextDelta(chunk)
        if self.fail:
            raise ModelError(self.fail)
        yield Done("fake-1", 10, 2)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
