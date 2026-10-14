import stat
from pathlib import Path

from buddy.auth import load_or_create_token, token_matches


def test_token_is_created_private_and_reused(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "token"
    token = load_or_create_token(path)
    assert len(token) == 64
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_or_create_token(path) == token


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
