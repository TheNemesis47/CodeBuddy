import os
import stat
from pathlib import Path

import pytest

from buddy import auth
from buddy.auth import load_or_create_token, token_matches

# Mode bits exist only on POSIX; on Windows the per-user data folder's ACL protects the token.
posix_only = pytest.mark.skipif(os.name != "posix", reason="no POSIX permission bits on Windows")


def test_token_is_created_and_reused(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "token"
    token = load_or_create_token(path)
    assert len(token) == 64
    assert load_or_create_token(path) == token


@posix_only
def test_token_is_created_private(tmp_path: Path) -> None:
    path = tmp_path / "token"
    load_or_create_token(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@posix_only
def test_loose_permissions_are_tightened(tmp_path: Path) -> None:
    path = tmp_path / "token"
    token = load_or_create_token(path)
    path.chmod(0o644)
    assert load_or_create_token(path) == token
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_weak_token_is_replaced(tmp_path: Path) -> None:
    path = tmp_path / "token"
    path.write_text("short\n")
    assert len(load_or_create_token(path)) == 64


def test_token_matches() -> None:
    assert token_matches("a" * 64, "a" * 64)
    assert not token_matches("a" * 64, "b" * 64)
    assert not token_matches("a" * 64, None)
    assert not token_matches("a" * 64, 123)


def test_buddy_home_env_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUDDY_HOME", str(tmp_path))
    assert auth.buddy_home() == tmp_path


def test_buddy_home_defaults_to_the_per_user_data_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BUDDY_HOME", raising=False)
    calls = []

    def data_dir(name: str, appauthor: object, roaming: bool) -> str:
        calls.append((name, appauthor, roaming))
        return str(Path("data") / name)

    monkeypatch.setattr(auth.platformdirs, "user_data_dir", data_dir)
    assert auth.buddy_home() == Path("data") / "CodeBuddy"
    assert calls == [("CodeBuddy", False, False)]
