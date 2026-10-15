"""The reconnect loop with fake sockets: no network, no Qt, no threads."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from codebuddy_overlay.client import MAX_BACKOFF_S, ConnectionLoop, Endpoint, buddy_home
from codebuddy_overlay.model import Connection
from codebuddy_overlay.protocol import AnswerStart, BrainMessage, Welcome

TOKEN = "t" * 64


class FakeSocket:
    def __init__(self, frames: list[str], fail_after: bool = False) -> None:
        self.frames = frames
        self.sent: list[str] = []
        self.closed = False
        self.fail_after = fail_after

    def send(self, message: str) -> None:
        self.sent.append(message)

    def __iter__(self) -> Iterator[str]:
        yield from self.frames
        if self.fail_after:
            raise ConnectionError("brain stopped")

    def close(self) -> None:
        self.closed = True


def make_loop(tmp_path: Path, connect, token: str | None = TOKEN):
    if token is not None:
        (tmp_path / "token").write_text(token + "\n")
    messages: list[BrainMessage] = []
    statuses: list[Connection] = []
    sleeps: list[float] = []
    loop = ConnectionLoop(
        Endpoint("ws://127.0.0.1:1/ws", tmp_path / "token"),
        messages.append,
        statuses.append,
        connect=connect,
        sleep=sleeps.append,
    )
    return loop, messages, statuses, sleeps


def test_endpoint_reads_port_and_home_from_the_environment(tmp_path: Path) -> None:
    endpoint = Endpoint.from_env({"BUDDY_PORT": "8797", "BUDDY_HOME": str(tmp_path)})
    assert endpoint.url == "ws://127.0.0.1:8797/ws"
    assert endpoint.token_file == tmp_path / "token"
    assert buddy_home({}).name == "CodeBuddy"


def test_no_token_yet_means_offline_and_backoff(tmp_path: Path) -> None:
    def never(url: str):
        raise AssertionError("must not connect without a token")

    loop, _, statuses, sleeps = make_loop(tmp_path, never, token=None)
    for _ in range(6):
        loop.run_once()
    assert statuses[-1] is Connection.OFFLINE
    assert sleeps == [1, 2, 4, 8, MAX_BACKOFF_S, MAX_BACKOFF_S]


def test_refused_connections_retry_silently(tmp_path: Path) -> None:
    def refused(url: str):
        raise ConnectionRefusedError(url)

    loop, messages, statuses, sleeps = make_loop(tmp_path, refused)
    loop.run_once()
    loop.run_once()
    assert messages == []
    assert statuses == [Connection.CONNECTING, Connection.OFFLINE] * 2
    assert sleeps == [1, 2]


def test_hello_then_messages_then_reconnect_resets_the_backoff(tmp_path: Path) -> None:
    welcome = json.dumps({"v": 0, "type": "welcome", "brain": "0.1.0"})
    start = json.dumps(
        {"v": 0, "type": "answer_start", "id": "a", "kind": "question", "title": "q"}
    )
    sockets = [FakeSocket([welcome, start], fail_after=True)]
    loop, messages, statuses, sleeps = make_loop(tmp_path, lambda url: sockets[0])
    loop.backoff = 8
    loop.run_once()
    sent = json.loads(sockets[0].sent[0])
    assert (sent["type"], sent["role"], sent["token"]) == ("hello", "notch", TOKEN)
    assert messages == [Welcome("0.1.0"), AnswerStart("a", messages[1].kind, "q")]  # type: ignore[union-attr]
    assert statuses == [Connection.CONNECTING, Connection.CONNECTED, Connection.OFFLINE]
    assert sleeps == [1]  # the welcome reset the backoff
    assert sockets[0].closed


def test_stop_ends_the_loop(tmp_path: Path) -> None:
    calls = []

    def refused(url: str):
        calls.append(url)
        loop.stop()
        raise ConnectionRefusedError

    loop, _, _, sleeps = make_loop(tmp_path, refused)
    loop.run()
    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.parametrize("token", ["", "short"])
def test_weak_tokens_are_not_sent(tmp_path: Path, token: str) -> None:
    assert Endpoint("ws://x", tmp_path / "token").read_token() is None
    (tmp_path / "token").write_text(token)
    assert Endpoint("ws://x", tmp_path / "token").read_token() is None
