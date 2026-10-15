import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import anyio
import pytest
from conftest import REPO, FakeModel
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect, WebSocketState

from buddy import server
from buddy.hints import HintGate
from buddy.latency import LatencyLog, read_records
from buddy.protocol import validate

TOKEN = "t" * 64


def example(name: str) -> dict:
    message = json.loads(
        (REPO / "protocol" / "examples" / f"{name}.json").read_text(encoding="utf-8")
    )
    return message | ({"token": TOKEN} if message["type"] == "hello" else {})


@pytest.fixture
def cloud() -> FakeModel:
    return FakeModel(("Perché ", "manca `with`."))


async def no_local_engine() -> None:
    return None


@pytest.fixture
def client(cloud: FakeModel) -> Iterator[TestClient]:
    # Tests never look for a real engine on :8080/:8000.
    with TestClient(server.create_app(cloud, TOKEN, detect_local=no_local_engine)) as test_client:
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

    async def receive(self) -> dict:
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


def test_binary_frames_with_utf8_json_are_accepted(client: TestClient) -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_bytes(json.dumps(example("hello.notch")).encode())
        assert validate(ws.receive_json())["type"] == "welcome"


def test_binary_garbage_from_the_ide_gets_an_error(client: TestClient) -> None:
    with connect(client, "ide") as ide:
        ide.send_bytes(b"\xff\xfe not utf-8")
        assert validate(ide.receive_json())["type"] == "error"


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


# --- Proactive hints (G6) -------------------------------------------------------------------


class RecordingSocket:
    """Stands in for a connected notch."""

    def __init__(self) -> None:
        self.received: list[dict] = []

    async def send_json(self, message: dict) -> None:
        self.received.append(validate(message))


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_brain(
    cloud: FakeModel, local: FakeModel | None, *, proactive_cloud: bool = False
) -> tuple[server.Brain, RecordingSocket, Clock]:
    async def detect() -> FakeModel | None:
        return local

    clock = Clock()
    brain = server.Brain(
        cloud, detect_local=detect, proactive_cloud=proactive_cloud, hints=HintGate(clock=clock)
    )
    notch = RecordingSocket()
    brain.notch.add(notch)  # type: ignore[arg-type]
    return brain, notch, clock


def idle_event(n: int) -> dict:
    """The protocol example with a different id and window each time (the code changed)."""
    idle = example("idle")
    return idle | {"id": f"idle-{n}", "window": idle["window"] | {"code": f"x = {n}\n"}}


async def send(brain: server.Brain, *messages: dict) -> None:
    for message in messages:
        await brain.handle_ide_message(validate(message))
    await brain.drain()


@pytest.mark.anyio
async def test_idle_streams_a_hint_from_the_local_engine(cloud: FakeModel) -> None:
    local = FakeModel(("Guarda ", "`with`."), is_local=True)
    brain, notch, _ = make_brain(cloud, local)
    await send(brain, idle_event(1))
    assert [m["type"] for m in notch.received] == [
        "answer_start",
        "answer_delta",
        "answer_delta",
        "answer_end",
    ]
    assert notch.received[0]["kind"] == "hint"
    assert notch.received[0]["title"] == "src/load.py:6"
    assert len(local.prompts) == 1
    assert "nudge" in local.prompts[0].system
    assert cloud.prompts == []


@pytest.mark.anyio
async def test_no_local_engine_means_no_hint_and_nothing_to_the_cloud(cloud: FakeModel) -> None:
    brain, notch, clock = make_brain(cloud, None)
    for n in range(5):
        await send(brain, idle_event(n))
        clock.now += 1000
    assert notch.received == []
    assert cloud.prompts == []


@pytest.mark.anyio
async def test_idle_never_reaches_the_cloud_while_proactive_cloud_is_off(cloud: FakeModel) -> None:
    """Every path: engine up, engine down, engine failing. The cloud model sees only triggers."""
    for local in (
        FakeModel(is_local=True),
        None,
        FakeModel(("half",), fail="engine crashed", is_local=True),
    ):
        brain, _, clock = make_brain(cloud, local)
        for n in range(3):
            await send(brain, idle_event(n))
            clock.now += 1000
    assert cloud.prompts == []


@pytest.mark.anyio
async def test_proactive_cloud_is_the_only_way_idle_reaches_claude(cloud: FakeModel) -> None:
    brain, notch, _ = make_brain(cloud, None, proactive_cloud=True)
    await send(brain, idle_event(1))
    assert len(cloud.prompts) == 1
    assert notch.received[0]["kind"] == "hint"


@pytest.mark.anyio
async def test_proactive_cloud_still_prefers_the_local_engine(cloud: FakeModel) -> None:
    local = FakeModel(is_local=True)
    brain, _, _ = make_brain(cloud, local, proactive_cloud=True)
    await send(brain, idle_event(1))
    assert len(local.prompts) == 1
    assert cloud.prompts == []


@pytest.mark.anyio
async def test_one_hint_every_three_minutes_and_only_for_changed_code(cloud: FakeModel) -> None:
    local = FakeModel(is_local=True)
    brain, notch, clock = make_brain(cloud, local)
    await send(brain, idle_event(1))  # t = 0: shown
    clock.now += 60
    await send(brain, idle_event(2))  # t = 60 s: changed, but too soon
    clock.now += 200
    await send(brain, idle_event(1) | {"id": "same-code"})  # t = 260 s: same code as the hint
    clock.now += 200
    await send(brain, idle_event(3))  # t = 460 s: changed and late enough: shown
    clock.now += 500
    await send(brain, idle_event(3) | {"id": "unchanged"})  # t = 960 s: unchanged since then
    starts = [m["id"] for m in notch.received if m["type"] == "answer_start"]
    assert starts == ["idle-1", "idle-3"]
    assert len(local.prompts) == 2


@pytest.mark.anyio
async def test_no_engine_does_not_use_up_the_rate_limit(cloud: FakeModel) -> None:
    local = FakeModel(is_local=True)
    brain, notch, _ = make_brain(cloud, None)
    await send(brain, idle_event(1))  # engine down: nothing shown
    brain.detect_local = lambda: _ready(local)
    await send(brain, idle_event(2))  # engine up a second later: the hint comes
    assert [m["id"] for m in notch.received if m["type"] == "answer_start"] == ["idle-2"]


async def _ready(model: FakeModel) -> FakeModel:
    return model


@pytest.mark.anyio
async def test_a_trigger_still_goes_to_the_cloud_with_a_local_engine_up(cloud: FakeModel) -> None:
    local = FakeModel(is_local=True)
    brain, _, _ = make_brain(cloud, local)
    await send(brain, example("trigger.question"))
    assert len(cloud.prompts) == 1
    assert local.prompts == []


@pytest.mark.anyio
async def test_no_hint_right_after_a_trigger(cloud: FakeModel) -> None:
    """`#?` + Enter, then 4 s of no typing: the idle hint must not replace the answer."""
    local = FakeModel(is_local=True)
    brain, notch, _ = make_brain(cloud, local)
    await send(brain, example("trigger.question"), idle_event(1))
    assert local.prompts == []
    assert {m["id"] for m in notch.received} == {example("trigger.question")["id"]}


@pytest.mark.anyio
async def test_every_answer_and_hint_is_logged_with_its_latency(
    cloud: FakeModel, tmp_path: Path
) -> None:
    path = tmp_path / "latency.jsonl"
    local = FakeModel(("Guarda.",), is_local=True)
    brain, _, _ = make_brain(cloud, local)
    brain.latency = LatencyLog(path)
    await send(brain, idle_event(1), example("trigger.question"))
    records = read_records(path)
    assert [(r["kind"], r["id"]) for r in records] == [
        ("hint", "idle-1"),
        ("question", example("trigger.question")["id"]),
    ]
    assert all(r["model"] == "fake-1" and r["input_tokens"] == 10 for r in records)
    assert all(0 <= r["first_token_ms"] <= r["total_ms"] for r in records)


@pytest.mark.anyio
async def test_a_failed_answer_is_not_logged(tmp_path: Path) -> None:
    path = tmp_path / "latency.jsonl"
    brain, notch, _ = make_brain(FakeModel(fail="quota finita"), None)
    brain.latency = LatencyLog(path)
    await send(brain, example("trigger.question"))
    assert notch.received[-1]["type"] == "error"
    assert read_records(path) == []
