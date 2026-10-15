"""The shared behaviour scenarios (protocol/scenarios), also replayed by the Swift notch."""

import json
from pathlib import Path

import pytest
from conftest import SCENARIOS

from codebuddy_overlay.island import ManualScheduler
from codebuddy_overlay.model import Connection, OverlayModel
from codebuddy_overlay.protocol import decode

FILES = sorted(SCENARIOS.glob("*.json"))


def test_scenarios_are_found() -> None:
    assert len(FILES) >= 10


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_scenario(path: Path) -> None:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    delays = scenario.get("delays", {})
    clock = ManualScheduler()
    model = OverlayModel(clock, delays.get("expanded_to_peek", 20), delays.get("peek_to_hidden", 8))
    for index, step in enumerate(scenario["steps"]):
        at = f"{path.stem} step {index}"
        if "message" in step:
            model.handle(decode(json.dumps(step["message"])))
        elif "connection" in step:
            model.set_connection(Connection(step["connection"]))
        elif "pointer" in step:
            model.pointer(step["pointer"] == "enter")
        elif "click" in step:
            model.click()
        elif "close" in step:
            model.close()
        elif "advance" in step:
            clock.advance(step["advance"])
        elif "expect" in step:
            actual = {
                "state": model.state.value,
                "mood": model.mood.value,
                "peek_status": model.peek_status,
                "preview": model.peek_preview,
                "text": model.answers.current.text if model.answers.current else None,
            }
            for key, expected in step["expect"].items():
                assert key in actual, f"{at}: unknown expectation {key}"
                assert actual[key] == expected, f"{at}: {key}"
        else:
            pytest.fail(f"{at}: unknown step {step}")
