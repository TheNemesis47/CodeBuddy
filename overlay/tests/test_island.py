"""Ported from notch/Tests/CodeBuddyKitTests/IslandStateMachineTests.swift."""

from codebuddy_overlay.island import IslandStateMachine, ManualScheduler, State


def machine() -> tuple[IslandStateMachine, ManualScheduler]:
    clock = ManualScheduler()
    return IslandStateMachine(clock, expanded_to_peek_s=20, peek_to_hidden_s=8), clock


def test_hover_peeks_and_leaving_hides_after_the_delay() -> None:
    m, clock = machine()
    m.mouse_entered()
    assert m.state is State.PEEK
    m.mouse_left()
    clock.advance(7.9)
    assert m.state is State.PEEK
    clock.advance(0.2)
    assert m.state is State.HIDDEN


def test_explicit_answer_stays_open_while_streaming() -> None:
    m, clock = machine()
    m.answer_started(explicit=True)
    clock.advance(1000)
    assert m.state is State.EXPANDED
    m.answer_finished()
    clock.advance(20)
    assert m.state is State.PEEK
    clock.advance(8)
    assert m.state is State.HIDDEN


def test_hint_only_peeks() -> None:
    m, _ = machine()
    m.answer_started(explicit=False)
    assert m.state is State.PEEK


def test_transitions_are_reported_once_each() -> None:
    m, _ = machine()
    seen: list[tuple[State, State]] = []
    m.on_transition = lambda old, new: seen.append((old, new))
    m.click()
    m.click()
    m.collapse()
    assert seen == [(State.HIDDEN, State.EXPANDED), (State.EXPANDED, State.PEEK)]


def test_cancelled_timers_never_fire() -> None:
    _, clock = machine()
    fired: list[int] = []
    work = clock.schedule(5, lambda: fired.append(1))
    clock.schedule(6, lambda: fired.append(2))
    work.cancel()
    assert clock.pending == 1
    clock.advance(10)
    assert fired == [2]
    assert clock.now == 10
