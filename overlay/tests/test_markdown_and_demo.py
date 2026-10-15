import pytest

from codebuddy_overlay import demo
from codebuddy_overlay.island import ManualScheduler, State
from codebuddy_overlay.markdown import preview
from codebuddy_overlay.model import Connection, Mood, OverlayModel
from codebuddy_overlay.protocol import AnswerKind


@pytest.mark.parametrize(
    ("text", "limit", "expected"),
    [
        ("", 70, None),
        ("   ", 70, None),
        ("```\n```", 70, None),
        ("**Ciao** `mondo`", 70, "Ciao mondo"),
        ("- uno\n- due", 70, "uno due"),
        ("parola" * 20, 70, "parola" * 11 + "paro…"),  # no space: cut mid-word
        ("Prima frase, seconda parte", 13, "Prima frase…"),  # trailing comma dropped
        ("esatto", 6, "esatto"),
    ],
)
def test_preview(text: str, limit: int, expected: str | None) -> None:
    assert preview(text, limit) == expected


def test_demo_plays_every_state_and_the_whole_answer() -> None:
    """Replays `--demo` on a manual clock with the demo's own delays (as DemoScriptTests.swift)."""
    clock = ManualScheduler()
    model = OverlayModel(clock, expanded_to_peek_s=6, peek_to_hidden_s=3)
    model.set_connection(Connection.CONNECTED)
    for at, step in demo.steps():
        clock.schedule(at, lambda step=step: _apply(model, step))
    states = [model.state]
    answer_before_hint = None
    t = 0.0
    while t < 40:
        clock.advance(0.05)
        t += 0.05
        if states[-1] is not model.state:
            states.append(model.state)
        if answer_before_hint is None and t >= 20:
            answer_before_hint = model.answers.current.text if model.answers.current else ""
        if abs(t - 23) < 0.01:
            assert (model.peek_preview or "").startswith("Alla riga 6")
    assert states == [
        State.HIDDEN, State.PEEK, State.EXPANDED, State.PEEK, State.HIDDEN,
        State.PEEK, State.EXPANDED, State.PEEK, State.HIDDEN,
    ]  # fmt: skip
    assert answer_before_hint == demo.ANSWER
    assert model.answers.current is not None
    assert model.answers.current.text == demo.HINT
    assert model.answers.current.kind is AnswerKind.HINT
    assert model.mood is Mood.HAPPY


def _apply(model: OverlayModel, step: demo.Step) -> None:
    match step:
        case demo.Hover(inside=inside):
            model.pointer(inside)
        case demo.Click():
            model.click()
        case message:
            model.handle(message)


def test_chunks_reassemble() -> None:
    assert demo.chunks("abcdefg", 3) == ["abc", "def", "g"]
