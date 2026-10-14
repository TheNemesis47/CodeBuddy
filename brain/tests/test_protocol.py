import json

import pytest
from conftest import REPO

from buddy.protocol import ProtocolError, validate, validators

EXAMPLES = sorted((REPO / "protocol" / "examples").glob("*.json"))


def test_schemas_are_valid_and_found() -> None:
    assert len(validators()) == 9


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_every_example_validates(path) -> None:
    validate(json.loads(path.read_text()))


def test_every_schema_has_an_example() -> None:
    covered = {json.loads(p.read_text())["type"] for p in EXAMPLES}
    assert covered == set(validators())


def _example(name: str) -> dict:
    return json.loads((REPO / "protocol" / "examples" / f"{name}.json").read_text())


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"v": 1}, "at v"),
        ({"extra": True}, "Additional properties"),
        ({"kind": "alt"}, "at kind"),
        ({"line": 0}, "at line"),
    ],
)
def test_invalid_trigger_is_rejected(change: dict, error: str) -> None:
    with pytest.raises(ProtocolError, match=error):
        validate(_example("trigger.question") | change)


@pytest.mark.parametrize("message", [[], "hello", {"type": "nope"}, {"v": 0}])
def test_non_messages_are_rejected(message: object) -> None:
    with pytest.raises(ProtocolError):
        validate(message)
