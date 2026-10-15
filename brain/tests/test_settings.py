"""The settings file, its rules, and where API keys live."""

import os
import stat
import tomllib
from pathlib import Path

import pytest

from buddy.keys import KeyStore
from buddy.local import ENGINE_URLS
from buddy.settings import (
    Answers,
    Hints,
    Network,
    Overlay,
    Settings,
    SettingsError,
    config_path,
    dumps,
    from_dict,
    load,
    save,
    to_dict,
    with_env,
)

WIREGUARD_MAC = "http://10.0.0.2:8080"


def test_no_file_means_todays_behaviour(tmp_path: Path) -> None:
    settings = load(tmp_path / "config.toml")
    assert settings == Settings()
    assert settings.answers == Answers("claude-code", "sonnet", "")
    assert settings.hints.urls == ENGINE_URLS
    assert settings.hints.proactive_cloud is False
    assert settings.network.allow_remote is False
    assert settings.overlay.top_offset is None


def test_the_file_round_trips_and_is_plain_toml(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "config.toml"
    settings = Settings(
        Answers("openai-compatible", "qwen3-coder", WIREGUARD_MAC),
        Hints((WIREGUARD_MAC,), "qwen3-coder", True),
        Network(allow_remote=True),
        Overlay(top_offset=30),
    )
    save(path, settings)
    assert load(path) == settings
    text = path.read_text(encoding="utf-8")
    assert tomllib.loads(text)["answers"]["url"] == WIREGUARD_MAC
    assert "key" not in text.lower().replace("api keys are never stored here", "")
    assert not (tmp_path / "sub" / "config.toml.tmp").exists()


def test_strings_with_quotes_and_backslashes_survive() -> None:
    settings = Settings(Answers("openrouter", 'od"d\\model\tx', ""))
    assert from_dict(tomllib.loads(dumps(settings))) == settings


def test_a_server_on_another_machine_needs_allow_remote() -> None:
    data = to_dict(Settings(Answers("openai-compatible", "", WIREGUARD_MAC)))
    with pytest.raises(SettingsError, match=r"10\.0\.0\.2.*allow_remote"):
        from_dict(data)
    data["network"]["allow_remote"] = True
    assert from_dict(data).answers.url == WIREGUARD_MAC


def test_a_remote_hint_engine_needs_allow_remote_too() -> None:
    data = to_dict(Settings())
    data["hints"]["urls"] = ["http://127.0.0.1:8080", WIREGUARD_MAC]
    with pytest.raises(SettingsError, match="allow_remote"):
        from_dict(data)


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:9000", "http://localhost:8080", "http://[::1]:8080"]
)
def test_this_computer_needs_no_permission(url: str) -> None:
    data = to_dict(Settings())
    data["answers"] = {"provider": "openai-compatible", "model": "", "url": url}
    assert from_dict(data).answers.url == url


def test_openrouter_is_allowed_by_picking_it_but_needs_a_model() -> None:
    data = to_dict(Settings(Answers("openrouter", "anthropic/claude-sonnet-4", "")))
    assert from_dict(data).answers.provider == "openrouter"
    data["answers"]["model"] = ""
    with pytest.raises(SettingsError, match="OpenRouter model"):
        from_dict(data)


def test_hints_never_go_to_openrouter_even_with_allow_remote() -> None:
    data = to_dict(Settings(network=Network(allow_remote=True)))
    data["hints"]["urls"] = ["https://openrouter.ai/api/v1"]
    with pytest.raises(SettingsError, match="never go to OpenRouter"):
        from_dict(data)


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"answers": {"provider": "gpt"}}, "answers.provider"),
        ({"answers": {"provider": "openai-compatible", "url": ""}}, "answers.url"),
        ({"answers": {"provider": "openai-compatible", "url": "10.0.0.2:8080"}}, "not an http"),
        ({"hints": {"urls": "http://127.0.0.1:8080"}}, "list"),
        ({"hints": {"urls": [8080]}}, r"hints.urls\[0\]"),
        ({"hints": {"proactive_cloud": "yes"}}, "true or false"),
        ({"network": {"allow_remote": 1}}, "true or false"),
        ({"overlay": {"top_offset": -1}}, "top_offset"),
        ({"overlay": {"top_offset": "big"}}, "top_offset"),
        ({"answers": "claude"}, "must be a table"),
    ],
)
def test_bad_values_name_the_field(change: dict, error: str) -> None:
    with pytest.raises(SettingsError, match=error):
        from_dict(change)


def test_urls_are_normalized_and_deduplicated() -> None:
    settings = from_dict(
        {"hints": {"urls": ["http://127.0.0.1:8080/v1/", " http://127.0.0.1:8080 ", ""]}}
    )
    assert settings.hints.urls == ("http://127.0.0.1:8080",)


def test_claude_code_keeps_a_default_model_and_drops_a_stray_url() -> None:
    settings = from_dict({"answers": {"provider": "claude-code", "model": "", "url": "x"}})
    assert settings.answers == Answers("claude-code", "sonnet", "")


def test_unknown_keys_from_a_newer_brain_are_ignored() -> None:
    assert (
        from_dict({"answers": {"provider": "claude-code", "future": 1}, "beta": {}}) == Settings()
    )


def test_a_broken_file_is_an_error_not_a_guess(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[answers\nprovider = ", encoding="utf-8")
    with pytest.raises(SettingsError, match=r"config\.toml"):
        load(path)


def test_env_var_wins_over_the_file_and_says_so() -> None:
    saved = Settings(hints=Hints(proactive_cloud=False))
    effective, overrides = with_env(saved, {"BUDDY_PROACTIVE_CLOUD": "1"})
    assert effective.hints.proactive_cloud is True and overrides
    effective, overrides = with_env(Settings(hints=Hints(proactive_cloud=True)), {})
    assert effective.hints.proactive_cloud is True and overrides == []
    effective, _ = with_env(
        Settings(hints=Hints(proactive_cloud=True)), {"BUDDY_PROACTIVE_CLOUD": "0"}
    )
    assert effective.hints.proactive_cloud is False


def test_config_path_follows_buddy_config(tmp_path: Path) -> None:
    assert config_path({"BUDDY_CONFIG": str(tmp_path / "c.toml")}) == tmp_path / "c.toml"
    assert config_path({}).name == "config.toml"
    assert "CodeBuddy" in str(config_path({}))


# Keys


def test_keys_are_stored_privately_and_only_reported_as_set(tmp_path: Path) -> None:
    store = KeyStore(tmp_path / "keys.json", env={})
    assert store.status() == {"openrouter": False, "answers_server": False, "hints_server": False}
    store.update({"openrouter": " sk-or-test "})
    assert store.get("openrouter") == "sk-or-test"
    assert store.status()["openrouter"] is True
    if os.name == "posix":
        assert stat.S_IMODE((tmp_path / "keys.json").stat().st_mode) == 0o600
    store.update({"openrouter": None})
    assert store.get("openrouter") is None


def test_the_env_var_wins_over_the_stored_key(tmp_path: Path) -> None:
    store = KeyStore(tmp_path / "keys.json", env={"OPENROUTER_API_KEY": "from-env"})
    store.update({"openrouter": "from-file"})
    assert store.get("openrouter") == "from-env"


def test_unknown_key_names_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown key"):
        KeyStore(tmp_path / "keys.json", env={}).update({"anthropic": "x"})


def test_a_damaged_keys_file_reads_as_no_keys(tmp_path: Path) -> None:
    (tmp_path / "keys.json").write_text("{not json", encoding="utf-8")
    assert KeyStore(tmp_path / "keys.json", env={}).get("openrouter") is None
