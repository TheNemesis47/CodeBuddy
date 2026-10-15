import json
import socket
import threading
from collections.abc import AsyncIterator, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from buddy.models import Done, ModelError, ModelEvent, TextDelta
from buddy.prompting import Prompt

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).resolve().parents[2]
CODER = "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"


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


class FakeEngine(ThreadingHTTPServer):
    """`/v1/models` and a streaming `/v1/chat/completions`, like llama-server."""

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), Handler)
        self.models: object = {"object": "list", "data": [{"id": CODER, "object": "model"}]}
        self.chunks = ["Guarda ", "la riga 5."]
        self.status = 200
        self.requests: list[dict] = []
        self.headers_seen: list[dict[str, str]] = []

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
        self.server.headers_seen.append(dict(self.headers))
        if self.path != "/v1/models":
            self._send(404, b"{}", "application/json")
            return
        models = self.server.models
        body = models if isinstance(models, bytes) else json.dumps(models).encode()
        self._send(200, body, "application/json")

    def do_POST(self) -> None:
        self.server.headers_seen.append(dict(self.headers))
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
