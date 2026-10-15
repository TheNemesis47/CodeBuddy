"""WebSocket server on 127.0.0.1: the IDE sends events, the notch receives answers.

Every connection must (1) carry no `Origin` header, since browsers always send one and our clients
never do, and (2) send a valid `hello` with the local token as its first frame within
HELLO_TIMEOUT_S. Anything else is closed with 1008 (policy violation) and no reason, so nothing
leaks to whoever is probing.
"""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from buddy import __version__
from buddy.answers import Message, run_answer
from buddy.auth import token_matches
from buddy.hints import HintGate, window_key
from buddy.local import detect_local_model
from buddy.models import Model
from buddy.prompting import ProjectMap, Request, RequestKind, build_prompt
from buddy.protocol import ProtocolError, validate

log = logging.getLogger("buddy.server")

HELLO_TIMEOUT_S = 5.0
POLICY_VIOLATION = 1008


class NotchHub:
    """The connected notch clients. Answers are broadcast to all of them."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def discard(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, message: Message) -> None:
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except WebSocketDisconnect, RuntimeError:
                self._clients.discard(ws)


type DetectLocal = Callable[[], Awaitable[Model | None]]


class Brain:
    """Routes IDE events to models. Explicit triggers go to the cloud model; `idle` goes to the
    local engine, or to the cloud only when `proactive_cloud` is on (docs/decisions.md)."""

    def __init__(
        self,
        cloud: Model,
        answer_language: str = "italiano",
        *,
        detect_local: DetectLocal = detect_local_model,
        proactive_cloud: bool = False,
        hints: HintGate | None = None,
    ) -> None:
        self.cloud = cloud
        self.answer_language = answer_language
        self.detect_local = detect_local
        self.proactive_cloud = proactive_cloud
        self.hints = hints or HintGate()
        self.notch = NotchHub()
        self.project: ProjectMap | None = None
        self.project_hash: str | None = None
        self._tasks: set[asyncio.Task[Message | None]] = set()

    async def handle_ide_message(self, message: dict[str, Any]) -> None:
        match message["type"]:
            case "trigger":
                self.hints.pause()  # a hint must not replace the answer the student asked for
                self._spawn(self._answer(message))
            case "project_map":
                self.project = ProjectMap(message["tree"], message["symbols"])
                self.project_hash = message["hash"]
            case "idle":
                # Checked here, in order: two idle events can't both pass the gate.
                if self.hints.try_start(window_key(message)):
                    self._spawn(self._hint(message))
            case other:
                raise ProtocolError(f"{other} is not an ide → brain message")

    def _request(self, event: dict[str, Any], kind: RequestKind, text: str) -> Request:
        project = self.project if event.get("project") == self.project_hash else None
        return Request(
            kind=kind,
            text=text,
            file=event["file"],
            line=event["line"],
            language=event["language"],
            window_start=event["window"]["start"],
            window_code=event["window"]["code"],
            scope=event.get("scope"),
            project=project,
        )

    async def _answer(self, trigger: dict[str, Any]) -> Message:
        prompt = build_prompt(
            self._request(trigger, trigger["kind"], trigger["text"]), self.answer_language
        )
        log.info(
            "trigger %s %s:%s ~%d tokens in",
            trigger["kind"],
            trigger["file"],
            trigger["line"],
            prompt.estimated_tokens(),
        )
        return await run_answer(
            self.cloud,
            prompt,
            id=trigger["id"],
            kind=trigger["kind"],
            title=trigger["text"] or trigger["file"],
            emit=self.notch.broadcast,
        )

    async def _hint(self, idle: dict[str, Any]) -> Message | None:
        started = time.monotonic()
        model = await self.detect_local()
        if model is None and self.proactive_cloud:
            model = self.cloud
        if model is None:
            self.hints.undo()  # nothing was shown: the next changed window may try again
            log.info("idle %s:%s: no local engine, no hint", idle["file"], idle["line"])
            return None
        prompt = build_prompt(self._request(idle, "hint", ""), self.answer_language)
        log.info(
            "idle %s:%s → hint on %s ~%d tokens in",
            idle["file"],
            idle["line"],
            model.name,
            prompt.estimated_tokens(),
        )
        final = await run_answer(
            model,
            prompt,
            id=idle["id"],
            kind="hint",
            title=f"{idle['file']}:{idle['line']}",
            emit=self.notch.broadcast,
        )
        log.info("hint %s in %d ms", final["type"], round((time.monotonic() - started) * 1000))
        return final

    def _spawn(self, work: Awaitable[Message | None]) -> None:
        task: asyncio.Task[Message | None] = asyncio.ensure_future(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        """Wait for in-flight answers (tests, shutdown)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)


def create_app(
    cloud: Model,
    token: str,
    answer_language: str = "italiano",
    *,
    detect_local: DetectLocal = detect_local_model,
    proactive_cloud: bool = False,
    hints: HintGate | None = None,
) -> FastAPI:
    app = FastAPI(
        title="CodeBuddy brain",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    brain = Brain(
        cloud,
        answer_language,
        detect_local=detect_local,
        proactive_cloud=proactive_cloud,
        hints=hints,
    )
    app.state.brain = brain

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        if "origin" in ws.headers:
            await ws.close(code=POLICY_VIOLATION)
            return
        await ws.accept()
        role = await _handshake(ws, token)
        if role is None:
            return
        try:
            if role == "notch":
                brain.notch.add(ws)
                while True:  # v0: the notch only listens; keep reading to notice disconnects
                    await _receive_frame(ws)
            else:
                await _ide_loop(ws, brain)
        except WebSocketDisconnect:
            pass
        finally:
            brain.notch.discard(ws)

    return app


async def _handshake(ws: WebSocket, token: str) -> str | None:
    try:
        async with asyncio.timeout(HELLO_TIMEOUT_S):
            hello = validate(json.loads(await _receive_frame(ws)))
    except TimeoutError, ValueError, WebSocketDisconnect:  # ValueError: UTF-8, JSON, protocol
        await _close(ws)
        return None
    if hello["type"] != "hello" or not token_matches(token, hello["token"]):
        await _close(ws)
        return None
    await ws.send_json({"v": 0, "type": "welcome", "brain": __version__})
    return hello["role"]


async def _ide_loop(ws: WebSocket, brain: Brain) -> None:
    while True:
        try:
            raw = await _receive_frame(ws)
            await brain.handle_ide_message(validate(json.loads(raw)))
        except ValueError as error:  # bad UTF-8, bad JSON, or a ProtocolError
            await ws.send_json({"v": 0, "type": "error", "id": None, "message": str(error)})


async def _receive_frame(ws: WebSocket) -> str:
    """One frame as text. The protocol uses text frames, but UTF-8 JSON in a binary frame is
    accepted too (Foundation's WebSocket sends `Data` as binary)."""
    message = await ws.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    if message.get("text") is not None:
        return message["text"]
    return (message.get("bytes") or b"").decode("utf-8")


async def _close(ws: WebSocket) -> None:
    if ws.application_state != WebSocketState.DISCONNECTED:
        await ws.close(code=POLICY_VIOLATION)
