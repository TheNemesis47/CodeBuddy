import pytest

from buddy.hints import HINT_INTERVAL_S, HintGate, proactive_cloud_from_env, window_key


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def idle(code: str, file: str = "a.py") -> dict:
    return {"file": file, "window": {"start": 1, "code": code}}


def test_at_most_one_hint_every_three_minutes() -> None:
    clock = Clock()
    gate = HintGate(clock=clock)
    assert HINT_INTERVAL_S == 180
    assert gate.try_start(window_key(idle("x = 1")))
    clock.now += 179
    assert not gate.try_start(window_key(idle("x = 2")))  # changed, but too soon
    clock.now += 1
    assert gate.try_start(window_key(idle("x = 2")))


def test_unchanged_code_never_gets_a_second_hint() -> None:
    clock = Clock()
    gate = HintGate(clock=clock)
    assert gate.try_start(window_key(idle("x = 1")))
    clock.now += 3600
    assert not gate.try_start(window_key(idle("x = 1")))
    assert gate.try_start(window_key(idle("x = 1", file="b.py")))  # another file is new code


def test_undo_gives_the_slot_back() -> None:
    clock = Clock()
    gate = HintGate(clock=clock)
    assert gate.try_start(window_key(idle("x = 1")))
    clock.now += 200
    assert gate.try_start(window_key(idle("x = 2")))
    gate.undo()  # no engine answered for x = 2
    assert gate.try_start(window_key(idle("x = 3")))  # x = 1 is still the last real hint


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, False),
        ({"BUDDY_PROACTIVE_CLOUD": ""}, False),
        ({"BUDDY_PROACTIVE_CLOUD": "0"}, False),
        ({"BUDDY_PROACTIVE_CLOUD": "false"}, False),
        ({"BUDDY_PROACTIVE_CLOUD": "1"}, True),
        ({"BUDDY_PROACTIVE_CLOUD": " TRUE "}, True),
    ],
)
def test_proactive_cloud_is_off_unless_explicitly_set(env: dict, expected: bool) -> None:
    assert proactive_cloud_from_env(env) is expected
