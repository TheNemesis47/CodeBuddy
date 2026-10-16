"""The user's settings: the one model that answers everything (`#?`, `#!teoria`, proactive hints,
the review on save) and the network rule. One TOML file, written by the PyCharm settings page
through the brain, readable by hand.

    # ~/.config/CodeBuddy/config.toml (Linux); ~/Library/Application Support/CodeBuddy (macOS);
    # %LOCALAPPDATA%\\CodeBuddy (Windows). $BUDDY_CONFIG overrides the path.
    [answers]                       # every request: #?, #!teoria, hints, review on save
    provider = "claude-code"        # "claude-code" | "openrouter" | "openai-compatible"
    model = "sonnet"                # a Claude alias, an OpenRouter id, or the server's model
    url = ""                        # openai-compatible only, e.g. "http://10.0.0.2:8080"

    [network]
    allow_remote = false            # needed for any address that is not this computer

    [overlay]                       # Linux/Windows panel, read by the overlay at start
    top_offset = "auto"             # or the pixels to leave above it

A `[hints]` table from before 0.2 (a separate hint engine) is ignored: one model does everything
(docs/decisions.md). Precedence: command-line flags > this file > defaults. API keys never go in
this file: they live in `keys.json` next to the brain's token (buddy.keys), or in env vars.
"""

import os
import tomllib
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import platformdirs

from buddy.local import is_loopback, normalize_url

PROVIDERS = ("claude-code", "openrouter", "openai-compatible")
CLAUDE_MODELS = ("sonnet", "opus", "haiku")
DEFAULT_CLAUDE_MODEL = "sonnet"
OPENROUTER_URL = "https://openrouter.ai/api"


class SettingsError(ValueError):
    """The settings can't be used; the message names the field and is safe to show the user."""


@dataclass(frozen=True)
class Answers:
    provider: str = "claude-code"
    model: str = DEFAULT_CLAUDE_MODEL
    url: str = ""


@dataclass(frozen=True)
class Network:
    allow_remote: bool = False


@dataclass(frozen=True)
class Overlay:
    top_offset: int | None = None  # None = automatic


@dataclass(frozen=True)
class Settings:
    answers: Answers = field(default_factory=Answers)
    network: Network = field(default_factory=Network)
    overlay: Overlay = field(default_factory=Overlay)

    def remote_urls(self) -> list[str]:
        """Every address the code may be sent to that is not this computer (OpenRouter apart:
        picking it is the consent)."""
        url = self.answers.url if self.answers.provider == "openai-compatible" else ""
        return [url] if url and not is_loopback(url) else []


def config_path(env: Mapping[str, str] = os.environ) -> Path:
    if path := env.get("BUDDY_CONFIG"):
        return Path(path)
    folder = platformdirs.user_config_dir("CodeBuddy", appauthor=False, roaming=False)
    return Path(folder) / "config.toml"


# dict ⇄ Settings. The dict is both the TOML layout and the `settings` message's payload.


def _table(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    table = data.get(name, {})
    if not isinstance(table, Mapping):
        raise SettingsError(f"[{name}] must be a table")
    return table


def _str(table: Mapping[str, Any], section: str, key: str, default: str) -> str:
    value = table.get(key, default)
    if not isinstance(value, str):
        raise SettingsError(f"{section}.{key} must be text")
    return value.strip()


def _bool(table: Mapping[str, Any], section: str, key: str, default: bool) -> bool:
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise SettingsError(f"{section}.{key} must be true or false")
    return value


def _url(value: str, where: str) -> str:
    base = normalize_url(value)
    parts = urlsplit(base)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise SettingsError(f"{where}: {value!r} is not an http(s) address like http://host:8080")
    return base


def from_dict(data: Mapping[str, Any]) -> Settings:
    """Parse and check. Unknown keys are ignored (a newer file read by an older brain)."""
    answers_t = _table(data, "answers")
    network_t, overlay_t = _table(data, "network"), _table(data, "overlay")

    provider = _str(answers_t, "answers", "provider", Answers.provider)
    if provider not in PROVIDERS:
        raise SettingsError(f"answers.provider must be one of {', '.join(PROVIDERS)}")
    default_model = DEFAULT_CLAUDE_MODEL if provider == "claude-code" else ""
    model = _str(answers_t, "answers", "model", default_model) or default_model
    url = _str(answers_t, "answers", "url", "")
    if provider == "openrouter" and not model:
        raise SettingsError(
            "answers.model: pick an OpenRouter model, e.g. anthropic/claude-sonnet-4"
        )
    if provider == "openai-compatible":
        if not url:
            raise SettingsError("answers.url: the address of your OpenAI-compatible server")
        url = _url(url, "answers.url")
    else:
        url = ""

    top = overlay_t.get("top_offset", "auto")
    if top == "auto" or top is None:
        top_offset = None
    elif isinstance(top, int) and not isinstance(top, bool) and top >= 0:
        top_offset = top
    else:
        raise SettingsError('overlay.top_offset must be "auto" or a number of pixels ≥ 0')

    settings = Settings(
        Answers(provider, model, url),
        Network(_bool(network_t, "network", "allow_remote", False)),
        Overlay(top_offset),
    )
    check_network(settings)
    return settings


def check_network(settings: Settings) -> None:
    """Golden rule of the settings: the code never leaves this computer for an address the user
    didn't allow. OpenRouter is allowed by picking it; anything else needs `allow_remote`."""
    remote = settings.remote_urls()
    if remote and not settings.network.allow_remote:
        raise SettingsError(
            f"{remote[0]} is not this computer: turn on network.allow_remote "
            '("Allow servers on other machines") to send your code there'
        )


def to_dict(settings: Settings) -> dict[str, Any]:
    data = asdict(settings)
    top = settings.overlay.top_offset
    data["overlay"]["top_offset"] = "auto" if top is None else top
    return data


# TOML. tomllib reads; the writer below covers exactly what Settings holds.


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = "".join(
            {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}.get(c)
            or (f"\\u{ord(c):04x}" if ord(c) < 0x20 or ord(c) == 0x7F else c)
            for c in value
        )
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise TypeError(f"not a TOML value: {value!r}")


def dumps(settings: Settings) -> str:
    lines = [
        "# CodeBuddy settings. Written by PyCharm → Settings → Tools → CodeBuddy; you can edit it",
        "# by hand too (restart CodeBuddy after). API keys are never stored here.",
    ]
    for section, values in to_dict(settings).items():
        lines += ["", f"[{section}]"]
        lines += [f"{key} = {_toml_value(value)}" for key, value in values.items()]
    return "\n".join(lines) + "\n"


def load(path: Path) -> Settings:
    """The file's settings; the defaults when there is no file. Raises SettingsError."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Settings()
    except OSError as error:
        raise SettingsError(f"{path}: {error.strerror}") from error
    try:
        return from_dict(tomllib.loads(text))
    except tomllib.TOMLDecodeError as error:
        raise SettingsError(f"{path}: {error}") from error


def save(path: Path, settings: Settings) -> None:
    """Atomic: a crash mid-write leaves the old file, never half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(dumps(settings), encoding="utf-8")
    temporary.replace(path)
