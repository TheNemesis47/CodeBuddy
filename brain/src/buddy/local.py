"""The local engine: llama.cpp `llama-server` (:8080) or MTPLX (:8000), both OpenAI-compatible.

Only proactive hints use it (docs/decisions.md). It's found by asking `/v1/models` on loopback,
as AIStatus does; nothing here ever talks to a non-local address.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx2

from buddy.models import Done, ModelError, ModelEvent, TextDelta
from buddy.prompting import Prompt

ENGINE_URLS = ("http://127.0.0.1:8080", "http://127.0.0.1:8000")  # llama.cpp, MTPLX
PREFERRED_MODEL = "qwen3-coder-30b-a3b"
DETECT_TIMEOUT_S = 0.5
CONNECT_TIMEOUT_S = 1.0
TIMEOUT_S = 30
HINT_MAX_TOKENS = 160  # ~3 short lines; a hint that runs longer is cut, not waited for
# Qwen's recommended sampling for code (~/Work/testM5/MODELS.md).
TEMPERATURE = 0.6
TOP_P = 0.95


def pick_model(ids: Sequence[str]) -> str:
    """The preferred model when the engine serves it, otherwise the first one."""
    for model_id in ids:
        if PREFERRED_MODEL in model_id.lower():
            return model_id
    return ids[0]


async def detect_local_model(
    urls: Sequence[str] = ENGINE_URLS, timeout_s: float = DETECT_TIMEOUT_S
) -> LocalModel | None:
    """The first engine that answers `/v1/models` with at least one model, or None."""
    async with httpx2.AsyncClient(timeout=timeout_s, trust_env=False) as client:
        for url in urls:
            try:
                response = await client.get(f"{url}/v1/models")
                response.raise_for_status()
                ids = [
                    m["id"]
                    for m in response.json()["data"]
                    if isinstance(m, dict) and isinstance(m.get("id"), str)
                ]
            except httpx2.HTTPError, ValueError, KeyError, TypeError:
                continue  # down, not an OpenAI-compatible server, or no models
            if ids:
                return LocalModel(url, pick_model(ids))
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


class LocalModel:
    is_local = True

    def __init__(self, base_url: str, model: str, *, max_tokens: int = HINT_MAX_TOKENS) -> None:
        self.name = model
        self.base_url = base_url
        self._max_tokens = max_tokens

    async def stream(self, prompt: Prompt) -> AsyncIterator[ModelEvent]:
        body = {
            "model": self.name,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.user},
            ],
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": self._max_tokens,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
        }
        timeout = httpx2.Timeout(TIMEOUT_S, connect=CONNECT_TIMEOUT_S)
        usage: dict[str, Any] = {}
        try:
            async with (
                asyncio.timeout(TIMEOUT_S),
                httpx2.AsyncClient(timeout=timeout, trust_env=False) as client,
                client.stream(
                    "POST", f"{self.base_url}/v1/chat/completions", json=body
                ) as response,
            ):
                if response.status_code != 200:
                    raise ModelError(f"local engine: HTTP {response.status_code}")
                async for line in response.aiter_lines():
                    chunk = parse_sse_line(line)
                    if chunk is None:
                        continue
                    usage = chunk.get("usage") or usage
                    if text := chunk_text(chunk):
                        yield TextDelta(text)
        except TimeoutError as error:
            raise ModelError(f"local engine: no answer within {TIMEOUT_S}s") from error
        except httpx2.HTTPError as error:
            raise ModelError(f"local engine: {error}") from error
        yield Done(
            self.name,
            usage.get("prompt_tokens") or prompt.estimated_tokens(),
            usage.get("completion_tokens") or 0,
        )
