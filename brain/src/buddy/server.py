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
from collections.abc import Awaitable
from dataclasses import replace
from typing import Any, Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from buddy import __version__
from buddy.answers import Message, run_answer
from buddy.auth import token_matches
from buddy.hints import REVIEW_INTERVAL_S, HintGate, window_key
from buddy.latency import LatencyLog
from buddy.models import Model, ModelError
from buddy.prompting import ProjectMap, Request, RequestKind, build_prompt
from buddy.protocol import ProtocolError, validate
from buddy.providers import SettingsStore
from buddy.settings import SettingsError

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
    """Routes IDE events to the one model in the settings, local or cloud (docs/decisions.md):
    triggers always, `idle` through the hint gate, `review` (a save) through the review gate."""

    def __init__(
        self,
        model: Model,
        answer_language: str = "italiano",
        *,
        hints: HintGate | None = None,
        reviews: HintGate | None = None,
        latency: LatencyLog | None = None,
        settings: SettingsStore | None = None,
    ) -> None:
        self.model = model
        self.answer_language = answer_language
        self.hints = hints or HintGate()
        self.reviews = reviews or HintGate(REVIEW_INTERVAL_S)
        self.latency = latency
        self.settings = settings
        self.notch = NotchHub()
        self.project: ProjectMap | None = None
        self.project_hash: str | None = None
        # The last theory the student read, for `#!approfondisci`: (topic, answer text).
        self.last_theory: tuple[str, str] | None = None
        self._tasks: set[asyncio.Task[Message | None]] = set()

    def apply_settings(self) -> None:
        """Take the model from the settings: at start and after the settings page saves."""
        if self.settings is None:
            return
        self.model = self.settings.answers_model()
        for line in self.settings.describe():
            log.info("%s", line)

    async def handle_ide_message(self, message: dict[str, Any]) -> Message | None:
        """Events start work and return None; the settings page's requests return the reply."""
        match message["type"]:
            case "settings_get" | "settings_set" | "models_get":
                return await self._settings_request(message)
            case "trigger":
                # A hint or a review must not replace the answer the student asked for.
                self.hints.pause()
                self.reviews.pause()
                self._spawn(self._answer(message))
            case "project_map":
                self.project = ProjectMap(message["tree"], message["symbols"])
                self.project_hash = message["hash"]
            case "idle":
                # Checked here, in order: two idle events can't both pass the gate.
                if self.hints.try_start(window_key(message)):
                    self._spawn(self._proactive(message, "hint"))
            case "review":
                if self.reviews.try_start(window_key(message)):
                    self.hints.pause()  # the review is on screen: no hint on top of it
                    self._spawn(self._proactive(message, "review"))
            case other:
                raise ProtocolError(f"{other} is not an ide → brain message")
        return None

    async def _settings_request(self, message: dict[str, Any]) -> Message:
        id_ = message["id"]
        if self.settings is None:
            return _error(id_, "this brain was started without settings")
        if message["type"] == "models_get":
            try:
                models = await self.settings.models(
                    message["provider"], message.get("url", ""), message.get("key")
                )
            except ModelError as error:
                return {"v": 0, "type": "models", "id": id_, "models": [], "error": str(error)}
            return {"v": 0, "type": "models", "id": id_, "models": models, "error": None}
        if message["type"] == "settings_set":
            try:
                self.settings.update(message["settings"], message.get("keys"))
            except SettingsError as error:
                return _error(id_, str(error))
            log.info("settings saved by the settings page")
            self.apply_settings()
        return {"v": 0, "type": "settings", "id": id_, **self.settings.view()}

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
        kind, text = trigger["kind"], trigger["text"]
        request = self._request(trigger, kind, text)
        topic = text or f"the concept at line {trigger['line']} of {trigger['file']}"
        title = text or trigger["file"]
        if kind == "deeper" and self.last_theory:
            topic = self.last_theory[0]
            request = replace(request, previous_topic=topic, previous_answer=self.last_theory[1])
            title = f"approfondimento: {text or topic}"
        prompt = build_prompt(request, self.answer_language)
        log.info(
            "trigger %s %s:%s ~%d tokens in",
            trigger["kind"],
            trigger["file"],
            trigger["line"],
            prompt.estimated_tokens(),
        )
        parts: list[str] = []

        async def emit(message: Message) -> None:
            if message["type"] == "answer_delta":
                parts.append(message["text"])
            await self.notch.broadcast(message)

        final = await run_answer(
            self.model,
            prompt,
            id=trigger["id"],
            kind="question" if kind == "question" else "theory",  # the panel shows deeper as theory
            title=title,
            emit=emit,
        )
        if kind != "question" and final["type"] == "answer_end":
            self.last_theory = (topic, "".join(parts))
        self._log_latency(final, kind)
        return final

    async def _proactive(self, event: dict[str, Any], kind: Literal["hint", "review"]) -> Message:
        """A hint (after `idle`) or a review (after a save): the student didn't ask in words."""
        started = time.monotonic()
        prompt = build_prompt(self._request(event, kind, ""), self.answer_language)
        log.info(
            "%s %s:%s → %s on %s ~%d tokens in",
            event["type"],
            event["file"],
            event["line"],
            kind,
            self.model.name,
            prompt.estimated_tokens(),
        )
        title = f"{event['file']}:{event['line']}" if kind == "hint" else event["file"]
        final = await run_answer(
            self.model, prompt, id=event["id"], kind=kind, title=title, emit=self.notch.broadcast
        )
        log.info("%s %s in %d ms", kind, final["type"], round((time.monotonic() - started) * 1000))
        self._log_latency(final, kind)
        return final

    def _log_latency(self, final: Message, kind: str) -> None:
        if final["type"] == "answer_end":
            log.info(
                "%s %s first token %s ms, total %s ms, %s tokens in",
                kind,
                final["model"],
                final["first_token_ms"],
                final["total_ms"],
                final["tokens"]["in"],
            )
        if self.latency:
            self.latency.record(final, kind)

    def _spawn(self, work: Awaitable[Message | None]) -> None:
        task: asyncio.Task[Message | None] = asyncio.ensure_future(work)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        """Wait for in-flight answers (tests, shutdown)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)


def _error(id_: str | None, message: str) -> Message:
    return {"v": 0, "type": "error", "id": id_, "message": message}


def create_app(
    model: Model,
    token: str,
    answer_language: str = "italiano",
    *,
    hints: HintGate | None = None,
    reviews: HintGate | None = None,
    latency: LatencyLog | None = None,
    settings: SettingsStore | None = None,
) -> FastAPI:
    app = FastAPI(
        title="CodeBuddy brain",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    brain = Brain(
        model,
        answer_language,
        hints=hints,
        reviews=reviews,
        latency=latency,
        settings=settings,
    )
    brain.apply_settings()
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
            reply = await brain.handle_ide_message(validate(json.loads(raw)))
        except ValueError as error:  # bad UTF-8, bad JSON, or a ProtocolError
            reply = _error(None, str(error))
        if reply is not None:
            await ws.send_json(reply)


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
