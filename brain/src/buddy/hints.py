"""When a proactive hint may be shown (SPEC.md US3, criterion 2). Pure logic, injectable clock."""

import hashlib
import time
from collections.abc import Callable, Mapping
from typing import Any

HINT_INTERVAL_S = 180.0
TRUE_VALUES = {"1", "true", "yes", "on"}


def proactive_cloud_from_env(env: Mapping[str, str]) -> bool:
    """`BUDDY_PROACTIVE_CLOUD=1` is the only way an `idle` event can reach Claude. Default off."""
    return env.get("BUDDY_PROACTIVE_CLOUD", "").strip().lower() in TRUE_VALUES


def window_key(idle: Mapping[str, Any]) -> str:
    """What "the code changed" means: the same file and window text give the same key."""
    text = f"{idle['file']}\0{idle['window']['start']}\0{idle['window']['code']}"
    return hashlib.sha256(text.encode()).hexdigest()


class HintGate:
    """At most one hint every `interval_s`, and only for code that changed since the last hint.

    `try_start` checks and records in one step, so two idle events can't both pass. `undo` gives
    the slot back when no hint was produced after all (no local engine).
    """

    def __init__(
        self, interval_s: float = HINT_INTERVAL_S, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.interval_s = interval_s
        self._clock = clock
        self._last: tuple[str, float] | None = None
        self._previous: tuple[str, float] | None = None

    def try_start(self, key: str) -> bool:
        now = self._clock()
        if self._last is not None:
            last_key, last_at = self._last
            if key == last_key or now - last_at < self.interval_s:
                return False
        self._previous, self._last = self._last, (key, now)
        return True

    def undo(self) -> None:
        self._last = self._previous

    def pause(self) -> None:
        """An explicit answer just started: no hint on top of it for the next interval."""
        key = self._last[0] if self._last else ""
        self._previous, self._last = self._last, (key, self._clock())
