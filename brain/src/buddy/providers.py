"""Settings → models. The brain asks this for the model that answers `#?` / `#!teoria` and for
the function that finds the hint engine, and hands it the settings page's changes.

Routing stays the brain's (docs/decisions.md): answers go to the provider picked here; hints go
to the hint engines, and to the answers provider only with `proactive_cloud`.
"""

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from buddy.claude_cli import ClaudeCliModel
from buddy.keys import KeyStore
from buddy.local import (
    ANSWER_MAX_TOKENS,
    ANSWER_TIMEOUT_S,
    PREFERRED_MODEL,
    OpenAIModel,
    detect_local_model,
    list_models,
)
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
    with_env,
)

type DetectLocal = Callable[[], Awaitable[Model | None]]

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
    """The settings file + keys + environment, and the models they describe.

    `answers_override` (from `buddy serve --stub` or `--model`) wins over the file for answers,
    as command-line flags win over everything else."""

    def __init__(
        self,
        path: Path,
        keys: KeyStore,
        env: Mapping[str, str],
        *,
        answers_override: tuple[Model, str] | None = None,
        make_claude: Callable[[str], Model] = ClaudeCliModel,
        openrouter_url: str = OPENROUTER_URL,
    ) -> None:
        self.path = path
        self.keys = keys
        self._env = env
        self._override = answers_override
        self._make_claude = make_claude
        self._openrouter_url = openrouter_url
        self.saved = load(path)  # raises SettingsError: the brain refuses to start on a bad file
        self.effective, self.env_overrides = with_env(self.saved, env)

    @property
    def overrides(self) -> list[str]:
        flags = [f"answers → {self._override[1]}"] if self._override else []
        return flags + self.env_overrides

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

    def detect_hints(self) -> DetectLocal:
        hints = self.effective.hints
        key = self.keys.get("hints_server")

        async def detect() -> Model | None:
            if not hints.urls:
                return None
            return await detect_local_model(
                hints.urls, preferred=hints.model or PREFERRED_MODEL, api_key=key
            )

        return detect

    @property
    def proactive_cloud(self) -> bool:
        return self.effective.hints.proactive_cloud

    def describe(self) -> list[str]:
        """Startup log lines: where the code goes."""
        answers, hints = self.effective.answers, self.effective.hints
        where = {
            "claude-code": f"Claude Code CLI ({answers.model})",
            "openrouter": f"OpenRouter ({answers.model})",
            "openai-compatible": f"your server {answers.url} ({answers.model or 'first model'})",
        }[answers.provider]
        if self._override:
            where = f"{self._override[1]} (command line)"
        hint_where = ", ".join(hints.urls) or "nowhere (no hint engine set)"
        fallback = " else the answers provider" if hints.proactive_cloud else " only"
        lines = [
            f"settings: {self.path}",
            f"answers (#?, #!teoria) → {where}",
            f"proactive hints → {hint_where}{fallback}",
        ]
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
        self.effective, self.env_overrides = with_env(settings, self._env)
        return settings

    async def models(self, provider: str, url: str = "", key: str | None = None) -> list[str]:
        """What the settings page's model list offers. Raises ModelError when the server can't
        be asked (the page shows the message)."""
        match provider:
            case "claude-code":
                return list(CLAUDE_MODELS)
            case "openrouter":
                ids = await list_models(self._openrouter_url, key or self.keys.get("openrouter"))
            case "openai-compatible" | "hints":
                if not url:
                    raise ModelError("type the server's address first")
                name = "answers_server" if provider == "openai-compatible" else "hints_server"
                ids = await list_models(url, key or self.keys.get(name))
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
