import pytest

from buddy.answers import run_answer
from buddy.models import Done, TextDelta
from buddy.prompting import Prompt
from buddy.protocol import validate
from buddy.stub import StubModel


@pytest.mark.anyio
async def test_stub_streams_its_text_in_chunks_then_done() -> None:
    events = [
        e async for e in StubModel("Ciao dal modello finto.", delay_s=0).stream(Prompt("", ""))
    ]
    deltas = [e.text for e in events if isinstance(e, TextDelta)]
    assert "".join(deltas) == "Ciao dal modello finto."
    assert len(deltas) > 1
    assert isinstance(events[-1], Done) and events[-1].model == "stub"


@pytest.mark.anyio
async def test_stub_answers_follow_the_protocol() -> None:
    sent: list[dict] = []

    async def emit(message: dict) -> None:
        sent.append(validate(message))

    final = await run_answer(
        StubModel("Risposta.", delay_s=0),
        Prompt("s", "u"),
        id="a",
        kind="question",
        title="t",
        emit=emit,
    )
    assert final["type"] == "answer_end" and final["model"] == "stub"
