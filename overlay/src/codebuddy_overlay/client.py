"""The brain connection: one WebSocket, kept open on a background thread, reconnecting with
backoff (as `BrainClient.swift`). The brain may start after the overlay and the token may not
exist yet: both just mean "offline, retry". Nothing is ever shown as an error dialog."""

import contextlib
import os
import threading
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import platformdirs

from codebuddy_overlay.model import Connection
from codebuddy_overlay.protocol import BrainMessage, Welcome, decode, hello

MAX_BACKOFF_S = 15.0
CONNECT_TIMEOUT_S = 2.0


def buddy_home(env: Mapping[str, str] | None = None) -> Path:
    """Same rule as the brain (`brain/src/buddy/auth.py`): $BUDDY_HOME, else the per-user data
    folder (~/.local/share/CodeBuddy on Linux, CodeBuddy in %LOCALAPPDATA% on Windows)."""
    values: Mapping[str, str] = os.environ if env is None else env
    if home := values.get("BUDDY_HOME"):
        return Path(home)
    return Path(platformdirs.user_data_dir("CodeBuddy", appauthor=False, roaming=False))


@dataclass(frozen=True)
class Endpoint:
    url: str
    token_file: Path

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Endpoint:
        env = dict(os.environ) if env is None else env
        port = int(env.get("BUDDY_PORT", "8790"))
        return cls(f"ws://127.0.0.1:{port}/ws", buddy_home(env) / "token")

    def read_token(self) -> str | None:
        try:
            token = self.token_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return token if len(token) >= 32 else None


class Socket(Protocol):
    def send(self, message: str) -> None: ...
    def __iter__(self) -> Iterator[str | bytes]: ...
    def close(self) -> None: ...


type Connect = Callable[[str], Socket]


def websocket_connect(url: str) -> Socket:
    from websockets.sync.client import connect

    # No Origin header: the brain refuses browsers by that (SECURITY.md).
    return connect(url, open_timeout=CONNECT_TIMEOUT_S, max_size=None)  # type: ignore[return-value]


class ConnectionLoop:
    """The reconnect loop, without Qt or threads, so tests drive it step by step."""

    def __init__(
        self,
        endpoint: Endpoint,
        on_message: Callable[[BrainMessage], None],
        on_status: Callable[[Connection], None],
        connect: Connect = websocket_connect,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.on_message = on_message
        self.on_status = on_status
        self.connect = connect
        self.backoff = 1.0
        self.running = True
        self._stop = threading.Event()
        self._sleep = sleep or (lambda s: self._stop.wait(s))
        self._socket: Socket | None = None

    def run_once(self) -> None:
        """One connection attempt: returns when it fails or drops, after waiting the backoff."""
        self.on_status(Connection.CONNECTING)
        token = self.endpoint.read_token()
        if token is None:
            return self._retry()
        try:
            socket = self.connect(self.endpoint.url)
        except Exception:  # refused, timeout, DNS…: all mean "not there yet"
            return self._retry()
        self._socket = socket
        try:
            socket.send(hello(token))
            for frame in socket:
                message = decode(frame)
                if isinstance(message, Welcome):
                    self.backoff = 1.0
                    self.on_status(Connection.CONNECTED)
                self.on_message(message)
        except Exception:
            pass  # dropped: the brain stopped or refused the hello
        finally:
            self._socket = None
            with contextlib.suppress(Exception):
                socket.close()
        self._retry()

    def run(self) -> None:
        while self.running:
            self.run_once()

    def stop(self) -> None:
        self.running = False
        self._stop.set()
        if self._socket is not None:
            with contextlib.suppress(Exception):
                self._socket.close()

    def _retry(self) -> None:
        self.on_status(Connection.OFFLINE)
        if not self.running:
            return
        delay = self.backoff
        self.backoff = min(self.backoff * 2, MAX_BACKOFF_S)
        self._sleep(delay)


def start_in_background(loop: ConnectionLoop) -> threading.Thread:
    thread = threading.Thread(target=loop.run, name="codebuddy-brain", daemon=True)
    thread.start()
    return thread
