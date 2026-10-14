import pytest
from conftest import FakeModel

from buddy.answers import run_answer
from buddy.prompting import Prompt
from buddy.protocol import validate

PROMPT = Prompt("s", "u")


async def _run(model: FakeModel, title: str = "domanda") -> tuple[list[dict], dict]:
    sent: list[dict] = []

    async def emit(message: dict) -> None:
        sent.append(validate(message))  # every emitted message must follow the protocol

    final = await run_answer(model, PROMPT, id="a1", kind="question", title=title, emit=emit)
    return sent, final


@pytest.mark.anyio
async def test_answer_streams_start_deltas_end() -> None:
    sent, final = await _run(FakeModel(("Ciao ", "", "mondo")))
    assert [m["type"] for m in sent] == [
        "answer_start",
        "answer_delta",
        "answer_delta",
        "answer_end",
    ]
    assert "".join(m["text"] for m in sent if m["type"] == "answer_delta") == "Ciao mondo"
    assert final["model"] == "fake-1"
    assert final["tokens"] == {"in": 10, "out": 2}
    assert final["first_token_ms"] is not None
    assert final["first_token_ms"] <= final["total_ms"]


@pytest.mark.anyio
async def test_model_error_becomes_an_error_message() -> None:
    sent, final = await _run(FakeModel(("parziale",), fail="quota finita"))
    assert [m["type"] for m in sent] == ["answer_start", "answer_delta", "error"]
    assert final == {"v": 0, "type": "error", "id": "a1", "message": "quota finita"}


@pytest.mark.anyio
async def test_long_titles_are_cut() -> None:
    sent, _ = await _run(FakeModel(), title="x" * 500)
    assert len(sent[0]["title"]) == 80
