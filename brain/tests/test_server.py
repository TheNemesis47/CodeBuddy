import json
from collections.abc import Iterator
from contextlib import contextmanager

import anyio
import pytest
from conftest import REPO, FakeModel
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect, WebSocketState

from buddy import server
from buddy.protocol import validate

TOKEN = "t" * 64


def example(name: str) -> dict:
    message = json.loads((REPO / "protocol" / "examples" / f"{name}.json").read_text())
    return message | ({"token": TOKEN} if message["type"] == "hello" else {})


@pytest.fixture
def cloud() -> FakeModel:
    return FakeModel(("Perché ", "manca `with`."))


@pytest.fixture
def client(cloud: FakeModel) -> Iterator[TestClient]:
    with TestClient(server.create_app(cloud, TOKEN)) as test_client:
        yield test_client


@contextmanager
def connect(client: TestClient, role: str) -> Iterator[WebSocketTestSession]:
    """An authenticated session. Closed even when the test fails, so a failure never hangs."""
    with client.websocket_connect("/ws") as session:
        session.send_json(example(f"hello.{role}"))
        assert validate(session.receive_json())["type"] == "welcome"
        yield session


def assert_refused(client: TestClient, first_frame: object | None, **kwargs) -> None:
    frame = first_frame if isinstance(first_frame, str) else json.dumps(first_frame)
    with (
        pytest.raises(WebSocketDisconnect) as refused,
        client.websocket_connect("/ws", **kwargs) as ws,
    ):
        if first_frame is not None:
            ws.send_text(frame)
        ws.receive_json()
    assert refused.value.code == server.POLICY_VIOLATION


def test_browser_origin_is_refused_even_with_a_valid_token(client: TestClient) -> None:
    assert_refused(client, example("hello.ide"), headers={"Origin": "https://evil.example"})


def test_wrong_token_is_refused(client: TestClient) -> None:
    assert_refused(client, example("hello.ide") | {"token": "x" * 64})


@pytest.mark.parametrize(
    "first_frame",
    ["not json", {"v": 0, "type": "hello", "role": "ide"}, example("trigger.question")],
    ids=["garbage", "hello-without-token", "trigger-before-hello"],
)
def test_anything_but_a_valid_hello_first_is_refused(client: TestClient, first_frame) -> None:
    assert_refused(client, first_frame)


class SilentSocket:
    """Accepted, then never says anything."""

    application_state = WebSocketState.CONNECTED

    def __init__(self) -> None:
        self.closed_with: int | None = None

    async def receive_text(self) -> str:
        await anyio.sleep_forever()
        raise AssertionError("unreachable")

    async def close(self, code: int) -> None:
        self.closed_with = code


@pytest.mark.anyio
async def test_silent_client_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "HELLO_TIMEOUT_S", 0.05)
    ws = SilentSocket()
    with anyio.fail_after(2):  # without the hello timeout this fails instead of hanging
        role = await server._handshake(ws, TOKEN)  # type: ignore[arg-type]
    assert role is None
    assert ws.closed_with == server.POLICY_VIOLATION


def receive_until_end(notch: WebSocketTestSession, answer_id: str) -> list[dict]:
    """Every message up to and including the answer_end (or error) of `answer_id`."""
    received = []
    while True:
        message = validate(notch.receive_json())
        received.append(message)
        if message["type"] in ("answer_end", "error") and message["id"] == answer_id:
            return received


def test_trigger_streams_the_answer_to_the_notch(client: TestClient, cloud: FakeModel) -> None:
    trigger = example("trigger.question")
    with connect(client, "notch") as notch, connect(client, "ide") as ide:
        ide.send_json(trigger)
        received = receive_until_end(notch, trigger["id"])
    assert [m["type"] for m in received] == [
        "answer_start",
        "answer_delta",
        "answer_delta",
        "answer_end",
    ]
    assert {m["id"] for m in received} == {trigger["id"]}
    assert "→    4 |     #? perché non chiude il file?" in cloud.prompts[0].user


def test_project_map_is_used_only_when_the_hash_matches(
    client: TestClient, cloud: FakeModel
) -> None:
    first = example("trigger.question")  # project a1b2c3
    stale = first | {"id": "second", "project": "stale"}
    with connect(client, "notch") as notch, connect(client, "ide") as ide:
        ide.send_json(example("project_map"))  # hash a1b2c3
        ide.send_json(first)
        receive_until_end(notch, first["id"])
        ide.send_json(stale)
        receive_until_end(notch, stale["id"])
    assert "- src/main.py" in cloud.prompts[0].user
    assert "Project files" not in cloud.prompts[1].user


def test_idle_never_reaches_the_cloud(client: TestClient, cloud: FakeModel) -> None:
    idle, theory = example("idle"), example("trigger.theory")
    with connect(client, "notch") as notch, connect(client, "ide") as ide:
        ide.send_json(idle)
        ide.send_json(theory)  # handled after idle, so it works as a barrier
        received = receive_until_end(notch, theory["id"])
    assert idle["id"] not in {m["id"] for m in received}
    assert len(cloud.prompts) == 1
    assert "theory of: **context manager**" in cloud.prompts[0].user


@pytest.mark.parametrize(
    "bad",
    ["{oops", example("answer_end"), example("trigger.question") | {"line": -1}],
    ids=["garbage", "wrong-direction", "invalid-field"],
)
def test_bad_ide_message_gets_an_error_and_the_connection_survives(client: TestClient, bad) -> None:
    with connect(client, "ide") as ide:
        ide.send_text(bad if isinstance(bad, str) else json.dumps(bad))
        error = validate(ide.receive_json())
        assert error["type"] == "error"
        assert error["id"] is None
        ide.send_text("{oops")  # still connected
        assert ide.receive_json()["type"] == "error"
