"""The local token every client must present in its hello (SECURITY.md)."""

import os
import secrets
from pathlib import Path

import platformdirs

TOKEN_BYTES = 32  # 64 hex chars


def buddy_home() -> Path:
    """$BUDDY_HOME, else the per-user data folder: ~/Library/Application Support/CodeBuddy on
    macOS, ~/.local/share/CodeBuddy on Linux, %LOCALAPPDATA%\\CodeBuddy on Windows."""
    if home := os.environ.get("BUDDY_HOME"):
        return Path(home)
    return Path(platformdirs.user_data_dir("CodeBuddy", appauthor=False, roaming=False))


def load_or_create_token(path: Path) -> str:
    """Read the token, creating it (mode 600) on first run and tightening loose permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # POSIX only: on Windows the mode bits don't exist (chmod only sets read-only); the
        # per-user data folder's ACL is what keeps the token private there.
        if os.name == "posix" and path.stat().st_mode & 0o077:
            path.chmod(0o600)
        token = path.read_text(encoding="utf-8").strip()
        if len(token) >= TOKEN_BYTES:
            return token
        # Empty or truncated file: replace it rather than accept a weak token.
        path.unlink()
        return load_or_create_token(path)
    token = secrets.token_hex(TOKEN_BYTES)
    with os.fdopen(fd, "w") as file:
        file.write(token + "\n")
    return token


def token_matches(expected: str, given: object) -> bool:
    return isinstance(given, str) and secrets.compare_digest(expected.encode(), given.encode())
