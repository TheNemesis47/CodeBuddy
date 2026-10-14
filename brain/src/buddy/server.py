"""WebSocket server on 127.0.0.1: the IDE sends events, the notch receives answers.

Every connection must (1) carry no `Origin` header, since browsers always send one and our clients
never do, and (2) send a valid `hello` with the local token as its first frame within
HELLO_TIMEOUT_S. Anything else is closed with 1008 (policy violation) and no reason, so nothing
leaks to whoever is probing.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from buddy import __version__
from buddy.answers import Message, run_answer
from buddy.auth import token_matches
from buddy.models import Model
from buddy.prompting import ProjectMap, Request, build_prompt
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


class Brain:
    def __init__(self, cloud: Model, answer_language: str = "italiano") -> None:
        self.cloud = cloud
        self.answer_language = answer_language
        self.notch = NotchHub()
        self.project: ProjectMap | None = None
        self.project_hash: str | None = None
        self._tasks: set[asyncio.Task[Message]] = set()

    async def handle_ide_message(self, message: dict[str, Any]) -> None:
        match message["type"]:
            case "trigger":
                self._start_answer(message)
            case "project_map":
                self.project = ProjectMap(message["tree"], message["symbols"])
                self.project_hash = message["hash"]
            case "idle":
                # Proactive hints run on the local model only (G6). Until then: nothing, and
                # never the cloud (docs/decisions.md, proactive_cloud = false).
                pass
            case other:
                raise ProtocolError(f"{other} is not an ide → brain message")

    def _start_answer(self, trigger: dict[str, Any]) -> None:
        project = self.project if trigger.get("project") == self.project_hash else None
        request = Request(
            kind=trigger["kind"],
            text=trigger["text"],
            file=trigger["file"],
            line=trigger["line"],
            language=trigger["language"],
            window_start=trigger["window"]["start"],
            window_code=trigger["window"]["code"],
            scope=trigger.get("scope"),
            project=project,
        )
        prompt = build_prompt(request, self.answer_language)
        log.info(
            "trigger %s %s:%s ~%d tokens in",
            trigger["kind"],
            trigger["file"],
            trigger["line"],
            prompt.estimated_tokens(),
        )
        task = asyncio.create_task(
            run_answer(
                self.cloud,
                prompt,
                id=trigger["id"],
                kind=trigger["kind"],
                title=trigger["text"] or trigger["file"],
                emit=self.notch.broadcast,
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        """Wait for in-flight answers (tests, shutdown)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)


def create_app(cloud: Model, token: str, answer_language: str = "italiano") -> FastAPI:
    app = FastAPI(
        title="CodeBuddy brain",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    brain = Brain(cloud, answer_language)
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
                    await ws.receive_text()
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
            hello = validate(json.loads(await ws.receive_text()))
    except TimeoutError, json.JSONDecodeError, ProtocolError, WebSocketDisconnect:
        await _close(ws)
        return None
    if hello["type"] != "hello" or not token_matches(token, hello["token"]):
        await _close(ws)
        return None
    await ws.send_json({"v": 0, "type": "welcome", "brain": __version__})
    return hello["role"]


async def _ide_loop(ws: WebSocket, brain: Brain) -> None:
    while True:
        raw = await ws.receive_text()
        try:
            await brain.handle_ide_message(validate(json.loads(raw)))
        except (json.JSONDecodeError, ProtocolError) as error:
            await ws.send_json({"v": 0, "type": "error", "id": None, "message": str(error)})


async def _close(ws: WebSocket) -> None:
    if ws.application_state != WebSocketState.DISCONNECTED:
        await ws.close(code=POLICY_VIOLATION)
