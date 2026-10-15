import pytest

from buddy.triggers import ParsedTrigger, parse_trigger_line


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("#? perché non chiude il file?", ParsedTrigger("question", "perché non chiude il file?")),
        ("    #?   spazi intorno   ", ParsedTrigger("question", "spazi intorno")),
        ("#!teoria context manager", ParsedTrigger("theory", "context manager")),
        ("\t#!TEORIA decoratori", ParsedTrigger("theory", "decoratori")),
        ("#!theory generators", ParsedTrigger("theory", "generators")),
        ("#!teoria", ParsedTrigger("theory", "")),
        ("#! teoria context manager", ParsedTrigger("theory", "context manager")),
        ("#!   theory", ParsedTrigger("theory", "")),
    ],
)
def test_triggers_fire(line: str, expected: ParsedTrigger) -> None:
    assert parse_trigger_line(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "# teoria context manager",  # a normal comment
        "# ? not a trigger",
        "#?",  # a question with no text
        "#!   ",
        "#!alt",  # after the MVP
        "#!sconosciuto qualcosa",
        "#! sconosciuto qualcosa",
        "#!/usr/bin/env python3",  # a shebang
        "#! /usr/bin/env python3",
        "x = 1  #? why",  # only whole-line comments count
        'print("#? in a string")',
        "",
    ],
)
def test_non_triggers_do_not_fire(line: str) -> None:
    assert parse_trigger_line(line) is None
