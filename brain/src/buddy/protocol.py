"""Validate messages against the JSON Schemas in `<repo>/protocol/schemas` (the source of truth)."""

import json
import os
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

VERSION = 0


class ProtocolError(ValueError):
    pass


def schema_dir() -> Path:
    default = Path(__file__).resolve().parents[3] / "protocol" / "schemas"
    return Path(os.environ.get("BUDDY_PROTOCOL_DIR", default))


@cache
def validators() -> dict[str, Draft202012Validator]:
    found = {}
    for path in sorted(schema_dir().glob("*.json")):
        schema = json.loads(path.read_text())
        Draft202012Validator.check_schema(schema)
        found[path.stem] = Draft202012Validator(schema)
    if not found:
        raise RuntimeError(f"no protocol schemas in {schema_dir()}")
    return found


def validate(message: object) -> dict[str, Any]:
    if not isinstance(message, dict):
        raise ProtocolError("message must be a JSON object")
    kind = message.get("type")
    validator = validators().get(kind) if isinstance(kind, str) else None
    if validator is None:
        raise ProtocolError(f"unknown message type: {kind!r}")
    error = next(iter(validator.iter_errors(message)), None)
    if error is not None:
        where = "/".join(str(p) for p in error.absolute_path) or "(root)"
        raise ProtocolError(f"invalid {kind} at {where}: {error.message}")
    return message
