import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import anyio
import pytest
from conftest import CODER, REPO, FakeModel
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


def test_idle_gets_a_hint_from_the_same_model(client: TestClient, cloud: FakeModel) -> None:
    idle = example("idle")
    with connect(client, "notch") as notch, connect(client, "ide") as ide:
        ide.send_json(idle)
        received = receive_until_end(notch, idle["id"])
    assert received[0]["type"] == "answer_start" and received[0]["kind"] == "hint"
    assert len(cloud.prompts) == 1
    assert "nudge" in cloud.prompts[0].system


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


def make_brain(model: FakeModel) -> tuple[server.Brain, RecordingSocket, Clock]:
    clock = Clock()
    brain = server.Brain(model, hints=HintGate(clock=clock))
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
async def test_idle_streams_a_hint_from_the_settings_model(cloud: FakeModel) -> None:
    brain, notch, _ = make_brain(cloud)
    await send(brain, idle_event(1))
    assert [m["type"] for m in notch.received] == [
        "answer_start",
        "answer_delta",
        "answer_delta",
        "answer_end",
    ]
    assert notch.received[0]["kind"] == "hint"
    assert notch.received[0]["title"] == "src/load.py:6"
    assert len(cloud.prompts) == 1
    assert "nudge" in cloud.prompts[0].system


@pytest.mark.anyio
async def test_hints_and_triggers_go_to_the_same_model(cloud: FakeModel) -> None:
    """One model does everything (docs/decisions.md): local or cloud, whatever the settings say."""
    local = FakeModel(("Guarda.",), is_local=True)
    for model in (cloud, local):
        brain, _, _ = make_brain(model)
        await send(brain, idle_event(1), example("trigger.question"))
        assert [("nudge" in p.system) for p in model.prompts] == [True, False]


@pytest.mark.anyio
async def test_a_failing_model_ends_the_hint_with_an_error(cloud: FakeModel) -> None:
    brain, notch, _ = make_brain(FakeModel(("half",), fail="engine crashed", is_local=True))
    await send(brain, idle_event(1))
    assert [m["type"] for m in notch.received][-1] == "error"
    assert notch.received[0]["kind"] == "hint"


@pytest.mark.anyio
async def test_one_hint_every_three_minutes_and_only_for_changed_code(cloud: FakeModel) -> None:
    brain, notch, clock = make_brain(cloud)
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
    assert len(cloud.prompts) == 2


@pytest.mark.anyio
async def test_no_hint_right_after_a_trigger(cloud: FakeModel) -> None:
    """`#?` + Enter, then 4 s of no typing: the idle hint must not replace the answer."""
    brain, notch, _ = make_brain(cloud)
    await send(brain, example("trigger.question"), idle_event(1))
    assert len(cloud.prompts) == 1
    assert {m["id"] for m in notch.received} == {example("trigger.question")["id"]}


@pytest.mark.anyio
async def test_every_answer_and_hint_is_logged_with_its_latency(
    cloud: FakeModel, tmp_path: Path
) -> None:
    path = tmp_path / "latency.jsonl"
    brain, _, _ = make_brain(cloud)
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
    brain, notch, _ = make_brain(FakeModel(fail="quota finita"))
    brain.latency = LatencyLog(path)
    await send(brain, example("trigger.question"))
    assert notch.received[-1]["type"] == "error"
    assert read_records(path) == []


# The settings page (settings_get / settings_set / models_get), over the IDE socket.


def settings_app(tmp_path: Path, cloud: FakeModel, engine_url: str = "http://127.0.0.1:9"):
    from test_providers import make_store

    store = make_store(tmp_path, openrouter_url=engine_url)
    return server.create_app(cloud, TOKEN, settings=store), store


def request(ide: WebSocketTestSession, message: dict) -> dict:
    ide.send_json(validate(message))
    reply = validate(ide.receive_json())
    assert reply["id"] == message["id"]
    return reply


def test_the_settings_page_reads_the_settings_without_keys(
    tmp_path: Path, cloud: FakeModel
) -> None:
    app, store = settings_app(tmp_path, cloud)
    store.keys.update({"openrouter": "sk-or-very-secret"})
    with TestClient(app) as test_client, connect(test_client, "ide") as ide:
        reply = request(ide, example("settings_get"))
    assert reply["type"] == "settings"
    assert reply["settings"]["answers"]["provider"] == "claude-code"
    assert reply["keys"] == {"openrouter": True, "answers_server": False}
    assert reply["path"] == str(tmp_path / "config.toml")
    assert "sk-or-very-secret" not in json.dumps(reply)


def test_saving_switches_the_answering_model_at_once(
    tmp_path: Path, cloud: FakeModel, engine
) -> None:
    app, _ = settings_app(tmp_path, cloud, engine.url)
    new = example("settings_set") | {
        "settings": example("settings_set")["settings"]
        | {"answers": {"provider": "openrouter", "model": "z-ai/glm-4.6", "url": ""}},
        "keys": {"openrouter": "sk-or-1"},
    }
    with TestClient(app) as test_client:
        with connect(test_client, "ide") as ide:
            reply = request(ide, new)
            assert reply["type"] == "settings" and reply["keys"]["openrouter"] is True
            assert app.state.brain.model.name == "openrouter:z-ai/glm-4.6"
        with connect(test_client, "notch") as notch, connect(test_client, "ide") as ide:
            trigger = example("trigger.question")
            ide.send_json(trigger)
            received = receive_until_end(notch, trigger["id"])
    assert received[-1]["model"] == "openrouter:z-ai/glm-4.6"
    assert engine.requests[-1]["model"] == "z-ai/glm-4.6"
    assert cloud.prompts == []  # the model it started with is no longer asked
    assert 'provider = "openrouter"' in (tmp_path / "config.toml").read_text(encoding="utf-8")


def test_bad_settings_get_an_error_and_change_nothing(tmp_path: Path, cloud: FakeModel) -> None:
    app, store = settings_app(tmp_path, cloud)
    before = app.state.brain.model
    remote = example("settings_set") | {
        "settings": example("settings_set")["settings"] | {"network": {"allow_remote": False}}
    }
    with TestClient(app) as test_client, connect(test_client, "ide") as ide:
        reply = request(ide, remote)
    assert reply["type"] == "error" and "allow_remote" in reply["message"]
    assert not (tmp_path / "config.toml").exists()
    assert app.state.brain.model is before
    assert store.effective.answers.provider == "claude-code"


def test_the_settings_page_lists_models(tmp_path: Path, cloud: FakeModel, engine) -> None:
    app, _ = settings_app(tmp_path, cloud)
    with TestClient(app) as test_client, connect(test_client, "ide") as ide:
        claude = request(
            ide, {"v": 0, "type": "models_get", "id": "m-0", "provider": "claude-code"}
        )
        mine = request(ide, example("models_get") | {"url": engine.url})
        down = request(ide, example("models_get") | {"id": "m-2", "url": "http://127.0.0.1:9"})
    assert claude["models"] == ["sonnet", "opus", "haiku"] and claude["error"] is None
    assert mine["models"] == [CODER]
    assert down["models"] == [] and "not reachable" in down["error"]


def test_a_brain_without_settings_says_so(client: TestClient) -> None:
    with connect(client, "ide") as ide:
        reply = request(ide, example("settings_get"))
    assert reply["type"] == "error" and "without settings" in reply["message"]


@pytest.mark.anyio
async def test_hints_follow_the_model_the_settings_page_picks(tmp_path: Path, engine) -> None:
    """Pick OpenRouter on the page: from then on the idle hints go there too, like `#?`."""
    from test_providers import make_store

    from buddy.settings import Answers, Settings, to_dict

    first = FakeModel()
    store = make_store(tmp_path, keys={"openrouter": "sk-or-1"}, openrouter_url=engine.url)
    brain = server.Brain(first, settings=store)
    await send(brain, idle_event(1))
    assert len(first.prompts) == 1 and engine.requests == []
    store.update(to_dict(Settings(Answers("openrouter", "z-ai/glm-4.6", ""))))
    brain.apply_settings()
    brain.hints = HintGate()
    await send(brain, idle_event(2))
    assert len(engine.requests) == 1
    assert len(first.prompts) == 1


# Review on save (Ctrl+S): same model, its own gate.


def review_event(n: int, file: str = "src/shapes.py") -> dict:
    review = example("review")
    code = review["window"]["code"] + f"# v{n}\n"
    return review | {"id": f"review-{n}", "file": file, "window": {"start": 1, "code": code}}


@pytest.mark.anyio
async def test_a_save_streams_a_review_of_the_file(cloud: FakeModel) -> None:
    brain, notch, _ = make_brain(cloud)
    await send(brain, review_event(1))
    assert notch.received[0]["type"] == "answer_start"
    assert notch.received[0]["kind"] == "review"
    assert notch.received[0]["title"] == "src/shapes.py"
    assert notch.received[-1]["type"] == "answer_end"
    assert len(cloud.prompts) == 1
    assert "saved `src/shapes.py`" in cloud.prompts[0].user
    assert "self.w * self.h" in cloud.prompts[0].user


@pytest.mark.anyio
async def test_saving_an_unchanged_file_again_gets_no_second_review(cloud: FakeModel) -> None:
    brain, notch, clock = make_brain(cloud)
    brain.reviews = HintGate(30, clock=clock)
    await send(brain, review_event(1))
    clock.now += 600
    await send(brain, review_event(1) | {"id": "again"})
    assert [m["id"] for m in notch.received if m["type"] == "answer_start"] == ["review-1"]


@pytest.mark.anyio
async def test_at_most_one_review_every_30_seconds(cloud: FakeModel) -> None:
    brain, notch, clock = make_brain(cloud)
    brain.reviews = HintGate(30, clock=clock)
    await send(brain, review_event(1))
    clock.now += 10
    await send(brain, review_event(2))  # changed, but Ctrl+S again 10 s later
    clock.now += 20
    await send(brain, review_event(3))
    starts = [m["id"] for m in notch.received if m["type"] == "answer_start"]
    assert starts == ["review-1", "review-3"]


@pytest.mark.anyio
async def test_a_review_never_replaces_the_answer_to_a_question(cloud: FakeModel) -> None:
    brain, notch, clock = make_brain(cloud)
    brain.reviews = HintGate(30, clock=clock)
    await send(brain, example("trigger.question"), review_event(1))
    assert {m["id"] for m in notch.received} == {example("trigger.question")["id"]}
    clock.now += 30
    await send(brain, review_event(2))
    assert notch.received[-1]["id"] == "review-2"


@pytest.mark.anyio
async def test_no_idle_hint_on_top_of_a_review(cloud: FakeModel) -> None:
    brain, notch, _ = make_brain(cloud)
    await send(brain, review_event(1), idle_event(1))
    assert {m["id"] for m in notch.received} == {"review-1"}


def test_a_review_over_the_socket_reaches_the_notch(client: TestClient) -> None:
    review = example("review")
    with connect(client, "notch") as notch, connect(client, "ide") as ide:
        ide.send_json(review)
        received = receive_until_end(notch, review["id"])
    assert all(validate(m) for m in received)
    assert received[0]["kind"] == "review"


@pytest.mark.anyio
async def test_a_failing_model_ends_the_review_with_an_error() -> None:
    brain, notch, _ = make_brain(FakeModel(("half",), fail="quota finita"))
    await send(brain, review_event(1))
    assert notch.received[0]["kind"] == "review"
    assert notch.received[-1]["type"] == "error"
    assert "quota finita" in notch.received[-1]["message"]


@pytest.mark.anyio
async def test_reviews_are_logged_with_their_latency(cloud: FakeModel, tmp_path: Path) -> None:
    brain, _, _ = make_brain(cloud)
    brain.latency = LatencyLog(tmp_path / "latency.jsonl")
    await send(brain, review_event(1))
    assert [(r["kind"], r["id"]) for r in read_records(tmp_path / "latency.jsonl")] == [
        ("review", "review-1")
    ]


@pytest.mark.anyio
async def test_reviews_go_to_your_own_server_when_the_settings_pick_it(
    tmp_path: Path, engine
) -> None:
    from test_providers import make_store

    from buddy.settings import Answers, Settings

    store = make_store(tmp_path, Settings(Answers("openai-compatible", CODER, engine.url)))
    brain = server.Brain(FakeModel(), settings=store)
    brain.apply_settings()
    await send(brain, review_event(1))
    assert len(engine.requests) == 1
    assert "saved `src/shapes.py`" in json.dumps(engine.requests[0], ensure_ascii=False)


# #!approfondisci: one level below the last theory.


def theory_then_deeper(text: str = "") -> tuple[dict, dict]:
    theory = example("trigger.theory")
    return theory, example("trigger.deeper") | {"text": text}


@pytest.mark.anyio
async def test_deeper_builds_on_the_last_theory_answer() -> None:
    model = FakeModel(("**In breve**: ", "gestisce una risorsa."))
    brain, notch, _ = make_brain(model)
    theory, deeper = theory_then_deeper("la matematica")
    await send(brain, theory, deeper)
    assert len(model.prompts) == 2
    assert "explanation of **context manager**" in model.prompts[1].user
    assert "**In breve**: gestisce una risorsa." in model.prompts[1].user
    starts = [m for m in notch.received if m["type"] == "answer_start"]
    assert starts[1]["kind"] == "theory"  # the panel shows it as theory
    assert starts[1]["title"] == "approfondimento: la matematica"


@pytest.mark.anyio
async def test_deeper_again_goes_below_the_previous_deeper(cloud: FakeModel) -> None:
    brain, _, _ = make_brain(cloud)
    theory, deeper = theory_then_deeper()
    await send(brain, theory, deeper, deeper | {"id": "deeper-2"})
    assert brain.last_theory is not None and brain.last_theory[0] == "context manager"
    assert "explanation of **context manager**" in cloud.prompts[2].user


@pytest.mark.anyio
async def test_deeper_with_no_theory_yet_is_a_theory_of_its_own_topic(cloud: FakeModel) -> None:
    brain, notch, _ = make_brain(cloud)
    await send(brain, example("trigger.deeper"))
    assert "theory of: **la matematica**" in cloud.prompts[0].user
    assert notch.received[0]["kind"] == "theory"


@pytest.mark.anyio
async def test_a_failed_theory_is_not_what_deeper_builds_on() -> None:
    brain, _, _ = make_brain(FakeModel(("mezza",), fail="quota finita"))
    await send(brain, example("trigger.theory"))
    assert brain.last_theory is None


@pytest.mark.anyio
async def test_a_question_does_not_replace_the_theory_to_go_deeper_on(cloud: FakeModel) -> None:
    brain, _, _ = make_brain(cloud)
    await send(brain, example("trigger.theory"), example("trigger.question"))
    assert brain.last_theory is not None and brain.last_theory[0] == "context manager"
