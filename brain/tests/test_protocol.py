import json

import pytest
from conftest import REPO

from buddy.protocol import ProtocolError, validate, validators

EXAMPLES = sorted((REPO / "protocol" / "examples").glob("*.json"))


def test_schemas_are_valid_and_found() -> None:
    assert len(validators()) == 14


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_every_example_validates(path) -> None:
    validate(json.loads(path.read_text(encoding="utf-8")))


def test_every_schema_has_an_example() -> None:
    covered = {json.loads(p.read_text(encoding="utf-8"))["type"] for p in EXAMPLES}
    assert covered == set(validators())


def _example(name: str) -> dict:
    return json.loads((REPO / "protocol" / "examples" / f"{name}.json").read_text(encoding="utf-8"))


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


def test_a_packaged_build_reads_its_bundled_schemas(monkeypatch, tmp_path) -> None:
    from buddy import protocol

    monkeypatch.delenv("BUDDY_PROTOCOL_DIR", raising=False)
    monkeypatch.setattr(protocol.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert protocol.schema_dir() == tmp_path / "protocol" / "schemas"
    monkeypatch.setenv("BUDDY_PROTOCOL_DIR", str(tmp_path / "x"))
    assert protocol.schema_dir() == tmp_path / "x"
