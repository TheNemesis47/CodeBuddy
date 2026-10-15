"""The local engine client against a fake OpenAI-compatible HTTP server on loopback."""

import pytest
from conftest import CODER, FakeEngine

from buddy.local import LocalModel, chunk_text, detect_local_model, parse_sse_line, pick_model
from buddy.models import Done, ModelError, TextDelta
from buddy.prompting import Prompt

PROMPT = Prompt("system", "user")


@pytest.mark.anyio
async def test_detects_an_engine_that_is_up(engine: FakeEngine) -> None:
    model = await detect_local_model([engine.url])
    assert model is not None
    assert model.is_local
    assert model.name == CODER
    assert model.base_url == engine.url


@pytest.mark.anyio
async def test_no_engine_up_means_no_model(closed_url: str) -> None:
    assert await detect_local_model([closed_url]) is None


@pytest.mark.anyio
async def test_falls_through_to_the_second_engine(closed_url: str, engine: FakeEngine) -> None:
    model = await detect_local_model([closed_url, engine.url])
    assert model is not None and model.base_url == engine.url


@pytest.mark.anyio
@pytest.mark.parametrize(
    "models",
    [b"<html>not json</html>", {"data": []}, {"oops": 1}, {"data": [{"name": "x"}]}],
    ids=["not-json", "no-models", "no-data", "no-ids"],
)
async def test_a_server_that_is_not_an_engine_is_ignored(engine: FakeEngine, models) -> None:
    engine.models = models
    assert await detect_local_model([engine.url]) is None


def test_prefers_qwen3_coder_when_the_engine_serves_several() -> None:
    assert pick_model(["gemma-4", CODER]) == CODER
    assert pick_model(["gemma-4", "llama"]) == "gemma-4"


@pytest.mark.anyio
async def test_streams_text_then_done_with_usage(engine: FakeEngine) -> None:
    events = [e async for e in LocalModel(engine.url, CODER).stream(PROMPT)]
    assert events == [TextDelta("Guarda "), TextDelta("la riga 5."), Done(CODER, 120, 9)]
    request = engine.requests[0]
    assert request["stream"] is True
    assert request["model"] == CODER
    assert request["max_tokens"] <= 200  # a hint is a nudge, not an essay
    assert request["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
    ]


@pytest.mark.anyio
async def test_http_error_becomes_a_model_error(engine: FakeEngine) -> None:
    engine.status = 500
    with pytest.raises(ModelError, match="HTTP 500"):
        _ = [e async for e in LocalModel(engine.url, CODER).stream(PROMPT)]


@pytest.mark.anyio
async def test_engine_gone_becomes_a_model_error(closed_url: str) -> None:
    with pytest.raises(ModelError, match="local engine"):
        _ = [e async for e in LocalModel(closed_url, CODER).stream(PROMPT)]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ('data: {"choices":[{"delta":{"content":"x"}}]}', "x"),
        ("data: [DONE]", None),
        (": keep-alive", None),
        ("data: {broken", None),
        ("", None),
    ],
)
def test_parse_sse_line(line: str, expected: str | None) -> None:
    chunk = parse_sse_line(line)
    assert (chunk_text(chunk) if chunk else None) == expected
