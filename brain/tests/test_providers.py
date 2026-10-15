"""Settings → models: Claude Code, OpenRouter and the user's own server, against a fake engine."""

import json
from pathlib import Path

import pytest
from conftest import CODER, FakeEngine, FakeModel

from buddy.keys import KeyStore
from buddy.local import ANSWER_MAX_TOKENS, OpenAIModel
from buddy.models import Done, ModelError, TextDelta
from buddy.prompting import Prompt
from buddy.providers import MissingKeyModel, SettingsStore, answers_override_for
from buddy.settings import Answers, Hints, Network, Settings, SettingsError, save, to_dict

PROMPT = Prompt("system", "user")


def make_store(
    tmp_path: Path,
    settings: Settings | None = None,
    *,
    keys: dict[str, str] | None = None,
    openrouter_url: str = "http://127.0.0.1:9",
    env: dict[str, str] | None = None,
) -> SettingsStore:
    if settings is not None:
        save(tmp_path / "config.toml", settings)
    key_store = KeyStore(tmp_path / "keys.json", env={})
    if keys:
        key_store.update(keys)
    return SettingsStore(
        tmp_path / "config.toml",
        key_store,
        env or {},
        make_claude=lambda model: FakeModel(("claude ", model)),
        openrouter_url=openrouter_url,
    )


async def collect(model) -> list:
    return [event async for event in model.stream(PROMPT)]


def test_default_settings_answer_with_claude_code(tmp_path: Path) -> None:
    model = make_store(tmp_path).answers_model()
    assert isinstance(model, FakeModel) and model.chunks == ("claude ", "sonnet")


@pytest.mark.anyio
async def test_openrouter_without_a_key_says_where_to_set_it(tmp_path: Path) -> None:
    store = make_store(tmp_path, Settings(Answers("openrouter", "anthropic/claude-sonnet-4", "")))
    model = store.answers_model()
    assert isinstance(model, MissingKeyModel)
    with pytest.raises(ModelError, match=r"API key.*Settings → Tools → CodeBuddy"):
        await collect(model)


@pytest.mark.anyio
async def test_openrouter_sends_the_key_and_no_local_sampling(
    tmp_path: Path, engine: FakeEngine
) -> None:
    store = make_store(
        tmp_path,
        Settings(Answers("openrouter", "anthropic/claude-sonnet-4", "")),
        keys={"openrouter": "sk-or-secret"},
        openrouter_url=engine.url,
    )
    events = await collect(store.answers_model())
    assert events[-1] == Done("openrouter:anthropic/claude-sonnet-4", 120, 9)
    request, headers = engine.requests[0], engine.headers_seen[-1]
    assert request["model"] == "anthropic/claude-sonnet-4"
    assert request["max_tokens"] == ANSWER_MAX_TOKENS
    assert "temperature" not in request and "top_p" not in request
    assert headers["Authorization"] == "Bearer sk-or-secret"
    assert headers["X-Title"] == "CodeBuddy"


@pytest.mark.anyio
async def test_your_own_server_with_no_model_uses_the_one_it_serves(
    tmp_path: Path, engine: FakeEngine
) -> None:
    store = make_store(tmp_path, Settings(Answers("openai-compatible", "", engine.url)))
    model = store.answers_model()
    events = await collect(model)
    assert TextDelta("Guarda ") in events
    assert engine.requests[0]["model"] == CODER
    assert "Authorization" not in engine.headers_seen[-1]


def test_a_remote_engine_shows_where_it_runs() -> None:
    assert OpenAIModel("http://10.0.0.2:8080", "qwen").name == "qwen @ 10.0.0.2:8080"
    assert not OpenAIModel("http://10.0.0.2:8080", "qwen").is_local
    assert OpenAIModel("http://127.0.0.1:8080/v1/", "qwen").name == "qwen"
    assert OpenAIModel("http://127.0.0.1:8080/v1/", "qwen").base_url == "http://127.0.0.1:8080"


@pytest.mark.anyio
async def test_hint_engines_come_from_the_settings(tmp_path: Path, engine: FakeEngine) -> None:
    store = make_store(tmp_path, Settings(hints=Hints((engine.url,), "qwen3-coder", False)))
    store.keys.update({"hints_server": "hint-key"})
    model = await store.detect_hints()()
    assert model is not None and model.name == CODER
    assert engine.headers_seen[-1]["Authorization"] == "Bearer hint-key"


@pytest.mark.anyio
async def test_no_hint_engine_set_means_no_hints(tmp_path: Path) -> None:
    assert await make_store(tmp_path, Settings(hints=Hints((), "", False))).detect_hints()() is None


@pytest.mark.anyio
async def test_models_for_the_settings_page(tmp_path: Path, engine: FakeEngine) -> None:
    store = make_store(tmp_path, openrouter_url=engine.url)
    assert await store.models("claude-code") == ["sonnet", "opus", "haiku"]
    assert await store.models("openrouter", key="sk-try") == [CODER]
    assert engine.headers_seen[-1]["Authorization"] == "Bearer sk-try"
    assert await store.models("openai-compatible", engine.url + "/v1") == [CODER]
    assert await store.models("hints", engine.url) == [CODER]


@pytest.mark.anyio
async def test_models_errors_are_messages_for_the_page(tmp_path: Path, closed_url: str) -> None:
    store = make_store(tmp_path)
    with pytest.raises(ModelError, match="address first"):
        await store.models("openai-compatible", "")
    with pytest.raises(ModelError, match="not reachable"):
        await store.models("hints", closed_url)


def test_saving_bad_settings_saves_nothing(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    bad = to_dict(Settings(Answers("openai-compatible", "", "http://10.0.0.2:8080")))
    with pytest.raises(SettingsError, match="allow_remote"):
        store.update(bad, {"answers_server": "k"})
    assert not (tmp_path / "config.toml").exists()
    assert store.keys.get("answers_server") is None


def test_saving_good_settings_writes_applies_and_never_echoes_keys(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    good = to_dict(
        Settings(Answers("openai-compatible", "", "http://10.0.0.2:8080"), network=Network(True))
    )
    store.update(good, {"answers_server": "super-secret"})
    assert (tmp_path / "config.toml").exists()
    assert store.effective.answers.url == "http://10.0.0.2:8080"
    assert isinstance(store.answers_model(), OpenAIModel)
    view = json.dumps(store.view())
    assert "super-secret" not in view
    assert store.view()["keys"]["answers_server"] is True
    assert any("10.0.0.2" in line for line in store.describe())


def test_a_broken_settings_file_stops_the_brain(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text('[answers]\nprovider = "gpt"\n', encoding="utf-8")
    with pytest.raises(SettingsError):
        make_store(tmp_path)


def test_command_line_wins_over_the_file(tmp_path: Path) -> None:
    override = answers_override_for(None, "risposta finta")
    assert override is not None
    store = SettingsStore(
        tmp_path / "config.toml",
        KeyStore(tmp_path / "keys.json", env={}),
        {"BUDDY_PROACTIVE_CLOUD": "1"},
        answers_override=override,
    )
    assert store.answers_model().name == "stub"
    assert store.proactive_cloud is True
    assert any("--stub" in o for o in store.overrides)
    assert any("BUDDY_PROACTIVE_CLOUD" in o for o in store.view()["overrides"])
    assert answers_override_for(None, None) is None
