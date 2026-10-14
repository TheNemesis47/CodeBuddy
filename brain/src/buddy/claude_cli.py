"""Claude through the user's own Claude Code subscription: `claude -p` in headless mode.

Personal use only (docs/decisions.md). `--bare` can't be used: it never reads the OAuth login.
Instead every other source of side effects is switched off: no tools, no settings, no MCP, no
slash commands, no saved session, and an empty working directory so no CLAUDE.md is picked up.
The prompt goes through stdin, never argv, so it doesn't show up in `ps`.
"""

import asyncio
import json
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

from buddy.models import Done, ModelError, ModelEvent, TextDelta
from buddy.prompting import Prompt

TIMEOUT_S = 120


def build_command(prompt: Prompt, model: str, executable: str = "claude") -> list[str]:
    return [
        executable,
        "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--system-prompt", prompt.system,
        "--tools", "",
        "--setting-sources", "",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--model", model,
    ]  # fmt: skip


def parse_line(line: str) -> ModelEvent | None:
    """One stream-json line → a TextDelta, a Done, or None for everything we don't need."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict):
        return None
    if event.get("type") == "stream_event":
        inner = event.get("event") or {}
        delta = inner.get("delta") or {}
        if inner.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
            return TextDelta(delta.get("text", ""))
        return None
    if event.get("type") == "result":
        if event.get("is_error"):
            raise ModelError(f"claude: {event.get('result') or event.get('subtype') or 'error'}")
        usage = event.get("usage") or {}
        input_tokens = (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
        models = list((event.get("modelUsage") or {}).keys())
        return Done(models[0] if models else "claude", input_tokens, usage.get("output_tokens", 0))
    return None


class ClaudeCliModel:
    is_local = False

    def __init__(self, model: str = "sonnet", executable: str = "claude") -> None:
        self.name = f"claude-cli:{model}"
        self._model = model
        self._executable = executable
        self._cwd = Path(tempfile.mkdtemp(prefix="codebuddy-claude-"))

    async def stream(self, prompt: Prompt) -> AsyncIterator[ModelEvent]:
        try:
            process = await asyncio.create_subprocess_exec(
                *build_command(prompt, self._model, self._executable),
                cwd=self._cwd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as error:
            raise ModelError("the `claude` CLI is not installed or not on PATH") from error
        assert process.stdin and process.stdout and process.stderr
        process.stdin.write(prompt.user.encode())
        await process.stdin.drain()
        process.stdin.close()

        done = False
        try:
            async with asyncio.timeout(TIMEOUT_S):
                async for raw in process.stdout:
                    event = parse_line(raw.decode(errors="replace"))
                    if event is not None:
                        done = done or isinstance(event, Done)
                        yield event
                await process.wait()
        except TimeoutError as error:
            raise ModelError(f"claude: no answer within {TIMEOUT_S}s") from error
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        if not done:
            stderr = (await process.stderr.read()).decode(errors="replace").strip()
            raise ModelError(f"claude exited with {process.returncode}: {stderr[-300:]}")
