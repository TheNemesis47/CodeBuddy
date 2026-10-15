import json

import pytest
from conftest import EXAMPLES

from codebuddy_overlay.protocol import (
    AnswerDelta,
    AnswerEnd,
    AnswerKind,
    AnswerStart,
    Error,
    Ignored,
    Welcome,
    decode,
    hello,
)


def example(name: str) -> str:
    return (EXAMPLES / f"{name}.json").read_text(encoding="utf-8")


def test_brain_examples_decode() -> None:
    assert isinstance(decode(example("welcome")), Welcome)
    start = decode(example("answer_start"))
    assert isinstance(start, AnswerStart) and start.kind is AnswerKind.QUESTION
    assert isinstance(decode(example("answer_delta")), AnswerDelta)
    end = decode(example("answer_end"))
    assert isinstance(end, AnswerEnd) and end.total_ms > 0
    assert isinstance(decode(example("error")), Error)


def test_hello_matches_the_notch_example() -> None:
    sent = json.loads(hello("t" * 64))
    shape = json.loads(example("hello.notch"))
    assert sent.keys() == shape.keys()
    assert (sent["v"], sent["type"], sent["role"]) == (0, "hello", "notch")


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[1]",
        '{"v": 1, "type": "welcome"}',
        '{"v": true, "type": "welcome"}',
        '{"v": 0, "type": "answer_start", "id": "a", "kind": "alt"}',
        '{"v": 0, "type": "answer_delta", "id": "a"}',
        '{"v": 0, "type": "answer_end"}',
        '{"v": 0, "type": "something_new", "id": "a"}',
    ],
)
def test_anything_else_is_ignored(raw: str) -> None:
    assert decode(raw) == Ignored()


def test_bytes_frames_decode_too() -> None:
    assert isinstance(decode(example("welcome").encode()), Welcome)


def test_error_without_id_is_a_notice() -> None:
    assert decode('{"v": 0, "type": "error", "id": null, "message": "bad"}') == Error(None, "bad")
