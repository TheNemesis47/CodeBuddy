"""OpenAI-compatible engines: the local one for hints (llama.cpp `llama-server` :8080, MTPLX
:8000), and, when the user picks them in the settings, OpenRouter or their own server for answers.

The hint engine is found by asking `/v1/models`, as AIStatus does. By default only loopback
addresses are asked; any other address comes from the user's settings, and only when they set
`allow_remote` (buddy.settings, docs/decisions.md). Clients never read proxy settings from the
environment (`trust_env=False`), so nothing reroutes the code on its way.
"""

import asyncio
import ipaddress
import json
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

import httpx2

from buddy.models import Done, ModelError, ModelEvent, TextDelta
from buddy.prompting import Prompt

ENGINE_URLS = ("http://127.0.0.1:8080", "http://127.0.0.1:8000")  # llama.cpp, MTPLX
PREFERRED_MODEL = "qwen3-coder-30b-a3b"
DETECT_TIMEOUT_S = 0.5
CONNECT_TIMEOUT_S = 1.0
TIMEOUT_S = 30
HINT_MAX_TOKENS = 160  # ~3 short lines; a hint that runs longer is cut, not waited for
ANSWER_MAX_TOKENS = 1500  # `#?` / `#!teoria` on an OpenAI-compatible provider
ANSWER_TIMEOUT_S = 120
# Qwen's recommended sampling for code (~/Work/testM5/MODELS.md).
TEMPERATURE = 0.6
TOP_P = 0.95


def normalize_url(url: str) -> str:
    """`http://host:8080/v1/` and `http://host:8080` are the same engine: keep the base."""
    base = url.strip().rstrip("/")
    return base.removesuffix("/v1").rstrip("/")


def is_loopback(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def pick_model(ids: Sequence[str], preferred: str = PREFERRED_MODEL) -> str:
    """The preferred model (a case-insensitive substring) when the engine serves it, otherwise
    the first one."""
    wanted = (preferred or PREFERRED_MODEL).lower()
    for model_id in ids:
        if wanted in model_id.lower():
            return model_id
    return ids[0]


def _auth(api_key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


async def _model_ids(client: httpx2.AsyncClient, url: str, api_key: str | None) -> list[str]:
    response = await client.get(f"{url}/v1/models", headers=_auth(api_key))
    response.raise_for_status()
    return [
        m["id"]
        for m in response.json()["data"]
        if isinstance(m, dict) and isinstance(m.get("id"), str)
    ]


async def list_models(url: str, api_key: str | None = None, timeout_s: float = 5.0) -> list[str]:
    """The models an engine serves, for the settings page. Raises ModelError with a message the
    user can act on."""
    async with httpx2.AsyncClient(timeout=timeout_s, trust_env=False) as client:
        try:
            return await _model_ids(client, normalize_url(url), api_key)
        except httpx2.HTTPStatusError as error:
            raise ModelError(f"{url}: HTTP {error.response.status_code}") from error
        except httpx2.HTTPError as error:
            raise ModelError(f"{url}: not reachable ({type(error).__name__})") from error
        except (ValueError, KeyError, TypeError) as error:
            raise ModelError(f"{url}: not an OpenAI-compatible server") from error


async def detect_local_model(
    urls: Sequence[str] = ENGINE_URLS,
    timeout_s: float = DETECT_TIMEOUT_S,
    *,
    preferred: str = PREFERRED_MODEL,
    api_key: str | None = None,
) -> OpenAIModel | None:
    """The first engine that answers `/v1/models` with at least one model, or None."""
    async with httpx2.AsyncClient(timeout=timeout_s, trust_env=False) as client:
        for url in urls:
            base = normalize_url(url)
            try:
                ids = await _model_ids(client, base, api_key)
            except httpx2.HTTPError, ValueError, KeyError, TypeError:
                continue  # down, not an OpenAI-compatible server, or no models
            if ids:
                return OpenAIModel(base, pick_model(ids, preferred), api_key=api_key)
    return None


def parse_sse_line(line: str) -> dict[str, Any] | None:
    """One server-sent-events line → the JSON chunk, or None (comments, `[DONE]`, garbage)."""
    if not line.startswith("data:"):
        return None
    data = line.removeprefix("data:").strip()
    if not data or data == "[DONE]":
        return None
    try:
        chunk = json.loads(data)
    except json.JSONDecodeError:
        return None
    return chunk if isinstance(chunk, dict) else None


def chunk_text(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    content = (choices[0].get("delta") or {}).get("content")
    return content if isinstance(content, str) else ""


class OpenAIModel:
    """`/v1/chat/completions` with streaming. Defaults fit a hint on the local engine; answers on
    OpenRouter or the user's server pass a bigger budget, a longer timeout and their own label.

    `model` may be empty: the engine's first model (or the preferred one) is asked for on the
    first answer. `is_local` is True only for loopback: the user's Mac over a VPN is theirs, but
    it is not this computer."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        max_tokens: int = HINT_MAX_TOKENS,
        api_key: str | None = None,
        sampling: bool = True,
        timeout_s: float = TIMEOUT_S,
        label: str = "local engine",
        name_prefix: str = "",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.base_url = normalize_url(base_url)
        self.is_local = is_loopback(self.base_url)
        self._model = model
        self._max_tokens = max_tokens
        self._api_key = api_key
        self._sampling = sampling
        self._timeout_s = timeout_s
        self._label = label
        self._prefix = name_prefix
        self._headers = {**(headers or {}), **_auth(api_key)}

    @property
    def model(self) -> str:
        return self._model

    @property
    def name(self) -> str:
        """What the notch's footer and the latency log show: the model, and where it runs when
        that is not this computer."""
        where = "" if self.is_local or self._prefix else f" @ {urlsplit(self.base_url).netloc}"
        return f"{self._prefix}{self._model or '?'}{where}"

    async def _resolve_model(self, client: httpx2.AsyncClient) -> None:
        if self._model:
            return
        try:
            ids = await _model_ids(client, self.base_url, self._api_key)
        except (httpx2.HTTPError, ValueError, KeyError, TypeError) as error:
            raise ModelError(f"{self._label}: can't list its models ({error})") from error
        if not ids:
            raise ModelError(f"{self._label}: serves no model")
        self._model = pick_model(ids)

    async def stream(self, prompt: Prompt) -> AsyncIterator[ModelEvent]:
        timeout = httpx2.Timeout(self._timeout_s, connect=CONNECT_TIMEOUT_S)
        usage: dict[str, Any] = {}
        try:
            async with (
                asyncio.timeout(self._timeout_s),
                httpx2.AsyncClient(timeout=timeout, trust_env=False) as client,
            ):
                await self._resolve_model(client)
                body: dict[str, Any] = {
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": prompt.system},
                        {"role": "user", "content": prompt.user},
                    ],
                    "stream": True,
                    "stream_options": {"include_usage": True},
                    "max_tokens": self._max_tokens,
                }
                if self._sampling:
                    body |= {"temperature": TEMPERATURE, "top_p": TOP_P}
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    json=body,
                    headers=self._headers,
                ) as response:
                    async for event in self._events(response, usage):
                        yield event
        except TimeoutError as error:
            raise ModelError(f"{self._label}: no answer within {self._timeout_s:g}s") from error
        except httpx2.HTTPError as error:
            raise ModelError(f"{self._label}: {error}") from error
        yield Done(
            self.name,
            usage.get("prompt_tokens") or prompt.estimated_tokens(),
            usage.get("completion_tokens") or 0,
        )

    async def _events(
        self, response: httpx2.Response, usage: dict[str, Any]
    ) -> AsyncIterator[ModelEvent]:
        if response.status_code != 200:
            detail = ""
            if response.status_code in (401, 403):
                detail = " (check the API key in the CodeBuddy settings)"
            raise ModelError(f"{self._label}: HTTP {response.status_code}{detail}")
        async for line in response.aiter_lines():
            chunk = parse_sse_line(line)
            if chunk is None:
                continue
            usage.update(chunk.get("usage") or {})
            if text := chunk_text(chunk):
                yield TextDelta(text)


LocalModel = OpenAIModel  # the hint engine; same client, hint defaults
