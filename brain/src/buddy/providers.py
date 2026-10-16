"""Settings → the model. The brain asks this for the one model that answers every request
(`#?`, `#!teoria`, proactive hints, the review on save) and hands it the settings page's changes.

One model does everything (docs/decisions.md, 2026-10-16): the one picked here, local or cloud.
"""

from collections.abc import AsyncIterator, Callable, Mapping
from pathlib import Path
from typing import Any

from buddy.claude_cli import ClaudeCliModel
from buddy.keys import KeyStore
from buddy.local import ANSWER_MAX_TOKENS, ANSWER_TIMEOUT_S, OpenAIModel, list_models
from buddy.models import Model, ModelError, ModelEvent
from buddy.prompting import Prompt
from buddy.settings import (
    CLAUDE_MODELS,
    OPENROUTER_URL,
    Settings,
    from_dict,
    load,
    save,
    to_dict,
)

SETTINGS_PAGE = "PyCharm → Settings → Tools → CodeBuddy"


class MissingKeyModel:
    """Stands in for a provider whose API key isn't set: every answer fails with what to do."""

    is_local = False

    def __init__(self, name: str, message: str) -> None:
        self.name = name
        self._message = message

    async def stream(self, prompt: Prompt) -> AsyncIterator[ModelEvent]:
        raise ModelError(self._message)
        yield  # pragma: no cover  (makes this an async generator)


class SettingsStore:
    """The settings file + keys, and the model they describe.

    `answers_override` (from `buddy serve --stub` or `--model`) wins over the file for answers,
    as command-line flags win over everything else."""

    def __init__(
        self,
        path: Path,
        keys: KeyStore,
        *,
        answers_override: tuple[Model, str] | None = None,
        make_claude: Callable[[str], Model] = ClaudeCliModel,
        openrouter_url: str = OPENROUTER_URL,
    ) -> None:
        self.path = path
        self.keys = keys
        self._override = answers_override
        self._make_claude = make_claude
        self._openrouter_url = openrouter_url
        self.saved = load(path)  # raises SettingsError: the brain refuses to start on a bad file

    @property
    def effective(self) -> Settings:
        return self.saved

    @property
    def overrides(self) -> list[str]:
        return [f"answers → {self._override[1]}"] if self._override else []

    # Models

    def answers_model(self) -> Model:
        if self._override is not None:
            return self._override[0]
        answers = self.effective.answers
        match answers.provider:
            case "openrouter":
                key = self.keys.get("openrouter")
                if key is None:
                    return MissingKeyModel(
                        f"openrouter:{answers.model}",
                        f"OpenRouter needs an API key: set it in {SETTINGS_PAGE}",
                    )
                return OpenAIModel(
                    self._openrouter_url,
                    answers.model,
                    api_key=key,
                    max_tokens=ANSWER_MAX_TOKENS,
                    sampling=False,
                    timeout_s=ANSWER_TIMEOUT_S,
                    label="OpenRouter",
                    name_prefix="openrouter:",
                    headers={"X-Title": "CodeBuddy"},
                )
            case "openai-compatible":
                return OpenAIModel(
                    answers.url,
                    answers.model,
                    api_key=self.keys.get("answers_server"),
                    max_tokens=ANSWER_MAX_TOKENS,
                    sampling=False,
                    timeout_s=ANSWER_TIMEOUT_S,
                    label=f"server {answers.url}",
                )
            case _:
                return self._make_claude(answers.model)

    def describe(self) -> list[str]:
        """Startup log lines: where the code goes."""
        answers = self.effective.answers
        where = {
            "claude-code": f"Claude Code CLI ({answers.model})",
            "openrouter": f"OpenRouter ({answers.model})",
            "openai-compatible": f"your server {answers.url} ({answers.model or 'first model'})",
        }[answers.provider]
        if self._override:
            where = f"{self._override[1]} (command line)"
        lines = [f"settings: {self.path}", f"every request (#?, #!teoria, hints, review) → {where}"]
        lines += [f"override: {o}" for o in self.overrides]
        remote = self.effective.remote_urls()
        if remote:
            lines.append(f"remote engines allowed: your code may go to {', '.join(remote)}")
        return lines

    # The settings page

    def view(self) -> dict[str, Any]:
        """The `settings` message payload: the saved file, which keys are set, what overrides."""
        return {
            "settings": to_dict(self.saved),
            "keys": self.keys.status(),
            "path": str(self.path),
            "overrides": self.overrides,
        }

    def update(
        self, data: Mapping[str, Any], keys: Mapping[str, str | None] | None = None
    ) -> Settings:
        """Check, save, apply. Nothing is saved when anything is wrong (SettingsError)."""
        settings = from_dict(data)
        if keys:
            self.keys.update(keys)
        save(self.path, settings)
        self.saved = settings
        return settings

    async def models(self, provider: str, url: str = "", key: str | None = None) -> list[str]:
        """What the settings page's model list offers. Raises ModelError when the server can't
        be asked (the page shows the message)."""
        match provider:
            case "claude-code":
                return list(CLAUDE_MODELS)
            case "openrouter":
                ids = await list_models(self._openrouter_url, key or self.keys.get("openrouter"))
            case "openai-compatible":
                if not url:
                    raise ModelError("type the server's address first")
                ids = await list_models(url, key or self.keys.get("answers_server"))
            case _:
                raise ModelError(f"unknown provider {provider!r}")
        return sorted(ids, key=str.lower)


def answers_override_for(model: str | None, stub: str | None) -> tuple[Model, str] | None:
    """`buddy serve --stub TEXT` or `--model ALIAS`: the command line wins over the file."""
    if stub is not None:
        from buddy.stub import StubModel

        return StubModel(stub), "stub model (--stub)"
    if model is not None:
        return ClaudeCliModel(model), f"Claude Code CLI ({model}, --model)"
    return None
