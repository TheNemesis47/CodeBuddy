"""API keys for the providers the user picks in the settings (OpenRouter, their own server).

Never in the config file, never in the repo, never in a message the brain sends: the settings
page only learns whether a key is set. They live in `keys.json` in the brain's per-user folder,
next to its token and with the same protection (mode 600 on POSIX, the user's folder ACL on
Windows). An env var, when set, wins over the file.
"""

import json
import os
from collections.abc import Mapping
from pathlib import Path

NAMES = ("openrouter", "answers_server")
ENV = {"openrouter": "OPENROUTER_API_KEY", "answers_server": "BUDDY_ANSWERS_API_KEY"}
LEGACY = {
    "hints_server"
}  # the hint engine's key before 0.2: an old settings page may still send it
FILE_NAME = "keys.json"


class KeyStore:
    def __init__(self, path: Path, env: Mapping[str, str] = os.environ) -> None:
        self.path = path
        self._env = env

    def _read(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError, ValueError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if k in NAMES and isinstance(v, str) and v}

    def get(self, name: str) -> str | None:
        return self._env.get(ENV[name]) or self._read().get(name)

    def status(self) -> dict[str, bool]:
        """Which keys are set: all the settings page ever sees."""
        return {name: self.get(name) is not None for name in NAMES}

    def update(self, changes: Mapping[str, str | None]) -> None:
        """Set (text) or clear (None or "") keys; unknown names are refused."""
        changes = {k: v for k, v in changes.items() if k not in LEGACY}
        unknown = set(changes) - set(NAMES)
        if unknown:
            raise ValueError(f"unknown key: {', '.join(sorted(unknown))}")
        keys = self._read()
        for name, value in changes.items():
            if value and value.strip():
                keys[name] = value.strip()
            else:
                keys.pop(name, None)
        self._write(keys)

    def _write(self, keys: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(keys, file)
        if os.name == "posix":
            temporary.chmod(0o600)  # O_CREAT's mode is ignored when the file already existed
        temporary.replace(self.path)
