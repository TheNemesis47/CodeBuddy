"""The local engine client against a fake OpenAI-compatible HTTP server on loopback."""

import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from buddy.local import LocalModel, chunk_text, detect_local_model, parse_sse_line, pick_model
from buddy.models import Done, ModelError, TextDelta
from buddy.prompting import Prompt

CODER = "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"


class FakeEngine(ThreadingHTTPServer):
    """`/v1/models` and a streaming `/v1/chat/completions`, like llama-server."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), Handler)
        self.models: object = {"object": "list", "data": [{"id": CODER, "object": "model"}]}
        self.chunks = ["Guarda ", "la riga 5."]
        self.status = 200
        self.requests: list[dict] = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


class Handler(BaseHTTPRequestHandler):
    server: FakeEngine

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/v1/models":
            self._send(404, b"{}", "application/json")
            return
        models = self.server.models
        body = models if isinstance(models, bytes) else json.dumps(models).encode()
        self._send(200, body, "application/json")

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        self.server.requests.append(json.loads(self.rfile.read(length)))
        if self.server.status != 200:
            self._send(self.server.status, b'{"error":"boom"}', "application/json")
            return
        events: list[dict[str, object]] = [{"choices": [{"delta": {"role": "assistant"}}]}]
        events.extend({"choices": [{"delta": {"content": c}}]} for c in self.server.chunks)
        events.append({"choices": [], "usage": {"prompt_tokens": 120, "completion_tokens": 9}})
        body = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
        self._send(200, body.encode(), "text/event-stream")


@pytest.fixture
def engine() -> Iterator[FakeEngine]:
    server = FakeEngine()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def closed_url() -> str:
    """A loopback port nobody listens on."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}"


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
