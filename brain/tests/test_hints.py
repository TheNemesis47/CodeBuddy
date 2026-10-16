from buddy.hints import HINT_INTERVAL_S, REVIEW_INTERVAL_S, HintGate, window_key


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


def test_an_explicit_answer_pauses_hints_for_the_interval() -> None:
    clock = Clock()
    gate = HintGate(clock=clock)
    gate.pause()
    assert not gate.try_start(window_key(idle("x = 1")))
    clock.now += 180
    assert gate.try_start(window_key(idle("x = 1")))


def test_a_pause_does_not_count_as_a_hint_for_that_code() -> None:
    """After the pause, the code the student had before the trigger may still get its hint."""
    clock = Clock()
    gate = HintGate(clock=clock)
    assert gate.try_start(window_key(idle("x = 1")))
    clock.now += 200
    gate.pause()
    clock.now += 180
    assert not gate.try_start(window_key(idle("x = 1")))  # still the last hinted code
    assert gate.try_start(window_key(idle("x = 2")))


def test_a_review_gate_is_keyed_on_the_whole_saved_file() -> None:
    clock = Clock()
    gate = HintGate(REVIEW_INTERVAL_S, clock=clock)
    assert REVIEW_INTERVAL_S == 30
    assert gate.try_start(window_key(idle("class A: ...")))
    clock.now += 30
    assert not gate.try_start(window_key(idle("class A: ...")))  # saved again, nothing changed
    assert gate.try_start(window_key(idle("class A:\n    x = 1")))
